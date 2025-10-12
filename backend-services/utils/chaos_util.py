import threading
import time
import logging

_state = {
    'redis_outage': False,
    'mongo_outage': False,
    'error_budget_burn': 0,
}

_lock = threading.RLock()
_logger = logging.getLogger('doorman.chaos')

def enable(backend: str, on: bool):
    with _lock:
        key = _key_for(backend)
        if key:
            _state[key] = bool(on)
            _logger.warning(f'chaos: {backend} outage set to {on}')

def enable_for(backend: str, duration_ms: int):
    enable(backend, True)
    t = threading.Timer(duration_ms / 1000.0, lambda: enable(backend, False))
    t.daemon = True
    t.start()

def _key_for(backend: str):
    b = (backend or '').strip().lower()
    if b == 'redis':
        return 'redis_outage'
    if b == 'mongo':
        return 'mongo_outage'
    return None

def should_fail(backend: str) -> bool:
    key = _key_for(backend)
    if not key:
        return False
    with _lock:
        return bool(_state.get(key))

def burn_error_budget(backend: str):
    with _lock:
        _state['error_budget_burn'] += 1
        _logger.warning(f'chaos: error_budget_burn+1 backend={backend} total={_state["error_budget_burn"]}')

def stats() -> dict:
    with _lock:
        return dict(_state)

