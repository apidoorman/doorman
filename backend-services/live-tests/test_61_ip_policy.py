import pytest

from types import SimpleNamespace

from utils.ip_policy_util import _ip_in_list, _get_client_ip, enforce_api_ip_policy

# Override autouse integration fixture with a no-op so we don't require a live backend
@pytest.fixture(autouse=True, scope='session')
def ensure_session_and_relaxed_limits():
    yield


def make_request(host: str | None = None, headers: dict | None = None):
    client = SimpleNamespace(host=host, port=None)
    return SimpleNamespace(client=client, headers=headers or {}, url=SimpleNamespace(path='/'))


def test_ip_in_list_ipv4_exact_and_cidr():
    assert _ip_in_list('192.168.1.10', ['192.168.1.10'])
    assert _ip_in_list('10.1.2.3', ['10.0.0.0/8'])
    assert not _ip_in_list('11.1.2.3', ['10.0.0.0/8'])


def test_ip_in_list_ipv6_exact_and_cidr():
    # Exact
    assert _ip_in_list('2001:db8::1', ['2001:db8::1'])
    # CIDR /32 should include 2001:db8:0:0::/32 range
    assert _ip_in_list('2001:db8::abcd', ['2001:db8::/32'])
    assert not _ip_in_list('2001:db9::1', ['2001:db8::/32'])


def test_get_client_ip_trusted_proxy(monkeypatch):
    # Trust only 10.0.0.0/8 proxies
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'xff_trusted_proxies': ['10.0.0.0/8']
    })

    # From trusted proxy -> use XFF first IP
    req1 = make_request('10.1.2.3', {'X-Forwarded-For': '1.2.3.4, 10.1.2.3'})
    assert _get_client_ip(req1, True) == '1.2.3.4'

    # From untrusted source -> ignore XFF
    req2 = make_request('8.8.8.8', {'X-Forwarded-For': '1.2.3.4'})
    assert _get_client_ip(req2, True) == '8.8.8.8'


def test_enforce_api_policy_never_blocks_localhost(monkeypatch):
    # Configure settings to trust no proxies (to be explicit); bypass should still occur
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'trust_x_forwarded_for': False,
        'xff_trusted_proxies': [],
        'allow_localhost_bypass': True,
    })

    # Policy that would otherwise block due to whitelist
    api = {
        'api_ip_mode': 'whitelist',
        'api_ip_whitelist': ['203.0.113.0/24'],
        'api_ip_blacklist': ['0.0.0.0/0']
    }

    # Loopback IPv4 should bypass
    req_local_v4 = make_request('127.0.0.1', {})
    enforce_api_ip_policy(req_local_v4, api)  # should not raise

    # Loopback IPv6 should bypass
    req_local_v6 = make_request('::1', {})
    enforce_api_ip_policy(req_local_v6, api)  # should not raise


def test_get_client_ip_secure_default_no_trust_when_empty_list(monkeypatch):
    # trust_xff on but no trusted proxies configured => do not trust headers
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'trust_x_forwarded_for': True,
        'xff_trusted_proxies': []
    })
    req = make_request('10.0.0.5', {'X-Forwarded-For': '203.0.113.9'})
    assert _get_client_ip(req, True) == '10.0.0.5'


def test_get_client_ip_x_real_ip_and_cf_connecting(monkeypatch):
    # Trust headers when source matches trusted proxies
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'trust_x_forwarded_for': True,
        'xff_trusted_proxies': ['10.0.0.0/8']
    })
    # No XFF, X-Real-IP present
    req1 = make_request('10.2.3.4', {'X-Real-IP': '198.51.100.7'})
    assert _get_client_ip(req1, True) == '198.51.100.7'
    # CF-Connecting-IP present
    req2 = make_request('10.2.3.4', {'CF-Connecting-IP': '2001:db8::2'})
    assert _get_client_ip(req2, True) == '2001:db8::2'


def test_get_client_ip_ignores_headers_when_trust_disabled(monkeypatch):
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'trust_x_forwarded_for': False,
        'xff_trusted_proxies': ['10.0.0.0/8']
    })
    req = make_request('10.2.3.4', {'X-Forwarded-For': '198.51.100.7'})
    assert _get_client_ip(req, False) == '10.2.3.4'


def test_enforce_api_policy_whitelist_and_blacklist(monkeypatch):
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'trust_x_forwarded_for': False,
        'xff_trusted_proxies': []
    })
    # Whitelist mode denies when not in WL
    api = {'api_ip_mode': 'whitelist', 'api_ip_whitelist': ['203.0.113.0/24'], 'api_ip_blacklist': []}
    req = make_request('198.51.100.10', {})
    raised = False
    try:
        enforce_api_ip_policy(req, api)
    except Exception:
        raised = True
    assert raised

    # Blacklist denies when in BL
    api2 = {'api_ip_mode': 'allow_all', 'api_ip_whitelist': [], 'api_ip_blacklist': ['198.51.100.0/24']}
    req2 = make_request('198.51.100.10', {})
    raised2 = False
    try:
        enforce_api_ip_policy(req2, api2)
    except Exception:
        raised2 = True
    assert raised2


def test_localhost_bypass_requires_no_forwarding_headers(monkeypatch):
    # Bypass enabled
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'allow_localhost_bypass': True,
        'trust_x_forwarded_for': False,
        'xff_trusted_proxies': []
    })
    api = {'api_ip_mode': 'whitelist', 'api_ip_whitelist': ['203.0.113.0/24']}
    # Direct ::1 with header should NOT bypass
    req = make_request('::1', {'X-Forwarded-For': '1.2.3.4'})
    raised = False
    try:
        enforce_api_ip_policy(req, api)
    except Exception:
        raised = True
    assert raised, 'Expected enforcement when forwarding header present'


def test_env_overrides_localhost_bypass(monkeypatch):
    # Stored setting false, env says true
    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'true')
    monkeypatch.setattr('utils.ip_policy_util.get_cached_settings', lambda: {
        'allow_localhost_bypass': False,
        'trust_x_forwarded_for': False,
        'xff_trusted_proxies': []
    })
    api = {'api_ip_mode': 'whitelist', 'api_ip_whitelist': ['203.0.113.0/24']}
    req = make_request('127.0.0.1', {})
    # Should bypass due to env
    enforce_api_ip_policy(req, api)
