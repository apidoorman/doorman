import argparse
import getpass
import json
import os
import sys
from urllib.parse import urljoin

import requests

def base_url() -> str:
    return os.getenv('BASE_URL', 'http://localhost:5001').rstrip('/') + '/'

def _csrf(sess: requests.Session) -> str | None:
    for c in sess.cookies:
        if c.name == 'csrf_token':
            return c.value
    return None

def _headers(sess: requests.Session, headers: dict | None = None) -> dict:
    out = {'Accept': 'application/json'}
    if headers:
        out.update(headers)
    csrf = _csrf(sess)
    if csrf and 'X-CSRF-Token' not in out:
        out['X-CSRF-Token'] = csrf
    return out

def login(sess: requests.Session, email: str, password: str) -> dict:
    url = urljoin(base_url(), '/platform/authorization'.lstrip('/'))
    r = sess.post(url, json={'email': email, 'password': password}, headers=_headers(sess))
    if r.status_code != 200:
        raise SystemExit(f'Login failed: {r.status_code} {r.text}')
    body = r.json()
    if 'access_token' in body:
        sess.cookies.set('access_token_cookie', body['access_token'], domain=os.getenv('COOKIE_DOMAIN') or None, path='/')
    return body

def confirm(prompt: str, assume_yes: bool = False) -> None:
    if assume_yes:
        return
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    if ans not in ('y', 'yes'):
        raise SystemExit('Aborted.')

def do_metrics(sess: requests.Session, args):
    url = urljoin(base_url(), '/platform/monitor/metrics')
    r = sess.get(url, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)

def do_dump(sess: requests.Session, args):
    confirm('Proceed with memory dump?', args.yes)
    url = urljoin(base_url(), '/platform/memory/dump')
    payload = {'path': args.path} if args.path else {}
    r = sess.post(url, json=payload, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_restore(sess: requests.Session, args):
    confirm('DANGER: Restore will overwrite in-memory DB. Continue?', args.yes)
    url = urljoin(base_url(), '/platform/memory/restore')
    payload = {'path': args.path} if args.path else {}
    r = sess.post(url, json=payload, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_chaos(sess: requests.Session, args):
    confirm(f"Set chaos outage: backend={args.backend} enabled={args.enabled} duration_ms={args.duration_ms}?", args.yes)
    url = urljoin(base_url(), '/platform/tools/chaos/toggle')
    payload = {'backend': args.backend, 'enabled': bool(args.enabled)}
    if args.duration_ms:
        payload['duration_ms'] = int(args.duration_ms)
    r = sess.post(url, json=payload, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_chaos_stats(sess: requests.Session, args):
    url = urljoin(base_url(), '/platform/tools/chaos/stats')
    r = sess.get(url, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_revoke(sess: requests.Session, args):
    confirm(f'Revoke all tokens for {args.username}?', args.yes)
    url = urljoin(base_url(), f'/platform/authorization/admin/revoke/{args.username}')
    r = sess.post(url, json={}, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_enable_user(sess: requests.Session, args):
    confirm(f'Enable user {args.username}?', args.yes)
    url = urljoin(base_url(), f'/platform/authorization/admin/enable/{args.username}')
    r = sess.post(url, json={}, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_disable_user(sess: requests.Session, args):
    confirm(f'Disable user {args.username} and revoke all tokens?', args.yes)
    url = urljoin(base_url(), f'/platform/authorization/admin/disable/{args.username}')
    r = sess.post(url, json={}, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def do_rotate_admin(sess: requests.Session, args):
    username = 'admin'
    new_pwd = args.password or getpass.getpass('New admin password: ')
    confirm('Rotate admin password now?', args.yes)
    url = urljoin(base_url(), f'/platform/user/{username}/update-password')
    payload = {'password': new_pwd}
    r = sess.put(url, json=payload, headers=_headers(sess))
    print(f'HTTP {r.status_code}')
    print(r.text)

def main():
    p = argparse.ArgumentParser(description='Doorman admin CLI')
    p.add_argument('--base-url', default=os.getenv('BASE_URL'), help='Override base URL (default env BASE_URL or http://localhost:5001)')
    p.add_argument('--email', default=os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'))
    p.add_argument('--password', default=os.getenv('DOORMAN_ADMIN_PASSWORD'))
    p.add_argument('-y', '--yes', action='store_true', help='Assume yes for safety prompts')
    sub = p.add_subparsers(dest='cmd', required=True)

    sub.add_parser('metrics', help='Show metrics snapshot')

    dmp = sub.add_parser('dump', help='Dump in-memory DB to encrypted file')
    dmp.add_argument('--path', help='Optional target path')

    rst = sub.add_parser('restore', help='Restore in-memory DB from encrypted file')
    rst.add_argument('--path', help='Path to dump file')

    ch = sub.add_parser('chaos', help='Toggle backend outages (redis|mongo)')
    ch.add_argument('backend', choices=['redis', 'mongo'])
    ch.add_argument('--enabled', action='store_true')
    ch.add_argument('--duration-ms', type=int, help='Auto-disable after milliseconds')

    sub.add_parser('chaos-stats', help='Show chaos stats and error budget burn')

    rvk = sub.add_parser('revoke', help='Revoke all tokens for a user')
    rvk.add_argument('username')

    enu = sub.add_parser('enable-user', help='Enable a user')
    enu.add_argument('username')

    du = sub.add_parser('disable-user', help='Disable a user (and revoke tokens)')
    du.add_argument('username')

    ra = sub.add_parser('rotate-admin', help='Rotate admin password')
    ra.add_argument('--password', help='New password (prompted if omitted)')

    args = p.parse_args()
    if args.base_url:
        os.environ['BASE_URL'] = args.base_url

    sess = requests.Session()
    if not any(c.name == 'access_token_cookie' for c in sess.cookies):
        email = args.email
        pwd = args.password or os.getenv('DOORMAN_ADMIN_PASSWORD')
        if not pwd:
            pwd = getpass.getpass('Admin password: ')
        login(sess, email, pwd)

    if args.cmd == 'metrics':
        do_metrics(sess, args)
    elif args.cmd == 'dump':
        do_dump(sess, args)
    elif args.cmd == 'restore':
        do_restore(sess, args)
    elif args.cmd == 'chaos':
        do_chaos(sess, args)
    elif args.cmd == 'chaos-stats':
        do_chaos_stats(sess, args)
    elif args.cmd == 'revoke':
        do_revoke(sess, args)
    elif args.cmd == 'enable-user':
        do_enable_user(sess, args)
    elif args.cmd == 'disable-user':
        do_disable_user(sess, args)
    elif args.cmd == 'rotate-admin':
        do_rotate_admin(sess, args)
    else:
        p.print_help()
        return 2

if __name__ == '__main__':
    sys.exit(main())

