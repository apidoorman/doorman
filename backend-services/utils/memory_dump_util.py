"""
Utilities to dump and restore in-memory database state with encryption.
"""

# External imports
import os
import json
import base64
from typing import Optional, Any
from datetime import datetime, timezone
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Internal imports
from .database import database

DEFAULT_DUMP_PATH = os.getenv('MEM_DUMP_PATH', 'generated/memory_dump.bin')

def _derive_key(key_material: str, salt: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b'doorman-mem-dump-v1',
    )
    return hkdf.derive(key_material.encode('utf-8'))

def _encrypt_blob(plaintext: bytes, key_str: str) -> bytes:
    if not key_str or len(key_str) < 8:
        raise ValueError('MEM_ENCRYPTION_KEY must be set and at least 8 characters')
    salt = os.urandom(16)
    key = _derive_key(key_str, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, None)

    return b'DMP1' + salt + nonce + ct

def _decrypt_blob(blob: bytes, key_str: str) -> bytes:
    if not key_str or len(key_str) < 8:
        raise ValueError('MEM_ENCRYPTION_KEY must be set and at least 8 characters')
    if len(blob) < 4 + 16 + 12:
        raise ValueError('Invalid dump file')
    if blob[:4] != b'DMP1':
        raise ValueError('Unsupported dump format')
    salt = blob[4:20]
    nonce = blob[20:32]
    ct = blob[32:]
    key = _derive_key(key_str, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)

def _split_dir_and_stem(path_hint: Optional[str]) -> tuple[str, str]:
    """Return (directory, stem) for naming timestamped dump files.

    - If hint is a directory (or endswith '/'), use it and default stem 'memory_dump'.
    - If hint is a file path, use its directory and basename without extension as stem.
    - If hint is None, use DEFAULT_DUMP_PATH and derive as above.
    """
    hint = path_hint or DEFAULT_DUMP_PATH

    if hint.endswith(os.sep):
        dump_dir = hint
        stem = 'memory_dump'
    elif os.path.isdir(hint):
        dump_dir = hint
        stem = 'memory_dump'
    else:
        dump_dir = os.path.dirname(hint) or '.'
        base = os.path.basename(hint)
        stem, _ext = os.path.splitext(base)
        stem = stem or 'memory_dump'
    return dump_dir, stem

BYTES_KEY_PREFIX = '__byteskey__:'

def _to_jsonable(obj: Any) -> Any:
    """Recursively convert arbitrary objects to JSON-serializable structures.

    - bytes -> {"__type__": "bytes", "data": base64}
    - set/tuple -> list
    - dict/list recurse
    - other unknown types -> str(obj)
    """
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, bytes):
        return {'__type__': 'bytes', 'data': base64.b64encode(obj).decode('ascii')}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():

            if isinstance(k, bytes):
                sk = BYTES_KEY_PREFIX + base64.b64encode(k).decode('ascii')
            elif isinstance(k, (str, int, float, bool)) or k is None:
                sk = str(k)
            else:
                try:
                    sk = str(k)
                except Exception:
                    sk = '__invalid_key__'
            out[sk] = _to_jsonable(v)
        return out
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, tuple) or isinstance(obj, set):
        return [_to_jsonable(v) for v in obj]

    try:
        return str(obj)
    except Exception:
        return None

def _json_default(o: Any) -> Any:
    if isinstance(o, bytes):
        return {'__type__': 'bytes', 'data': base64.b64encode(o).decode('ascii')}
    try:

        return str(o)
    except Exception:
        return None

def _from_jsonable(obj: Any) -> Any:
    """Inverse of _to_jsonable for the specific encodings we apply."""
    if isinstance(obj, dict):
        if obj.get('__type__') == 'bytes' and isinstance(obj.get('data'), str):
            try:
                return base64.b64decode(obj['data'])
            except Exception:
                return b''
        restored: dict[str, Any] = {}
        for k, v in obj.items():
            rk: Any = k
            if isinstance(k, str) and k.startswith(BYTES_KEY_PREFIX):
                b64 = k[len(BYTES_KEY_PREFIX):]
                try:
                    rk = base64.b64decode(b64)
                except Exception:
                    rk = k
            restored[rk] = _from_jsonable(v)
        return restored
    if isinstance(obj, list):
        return [_from_jsonable(v) for v in obj]
    return obj

def _sanitize_for_dump(data: Any) -> Any:
    """
    Remove sensitive data before dumping to prevent secret exposure.
    """
    SENSITIVE_KEYS = {
        'password', 'secret', 'token', 'key', 'api_key',
        'access_token', 'refresh_token', 'jwt', 'jwt_secret',
        'csrf_token', 'session', 'cookie',
        'credential', 'auth', 'authorization',
        'ssn', 'credit_card', 'cvv', 'private_key',
        'encryption_key', 'signing_key'
    }
    def should_redact(key: str) -> bool:
        if not isinstance(key, str):
            return False
        key_lower = key.lower()
        return any(s in key_lower for s in SENSITIVE_KEYS)
    def redact_value(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: '[REDACTED]' if should_redact(str(k)) else redact_value(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [redact_value(item) for item in obj]
        elif isinstance(obj, str):
            if len(obj) > 32:
                cleaned = obj.replace('-', '').replace('_', '').replace('.', '')
                if cleaned.isalnum():
                    return '[REDACTED-TOKEN]'
        return obj
    return redact_value(data)

def dump_memory_to_file(path: Optional[str] = None) -> str:
    if not database.memory_only:
        raise RuntimeError('Memory dump is only available in memory-only mode')
    dump_dir, stem = _split_dir_and_stem(path)
    os.makedirs(dump_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dump_path = os.path.join(dump_dir, f'{stem}-{ts}.bin')
    raw_data = database.db.dump_data()
    sanitized_data = _sanitize_for_dump(_to_jsonable(raw_data))
    payload = {
        'version': 1,
        'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'sanitized': True,
        'note': 'Sensitive fields (passwords, tokens, secrets) have been redacted',
        'data': sanitized_data,
    }
    plaintext = json.dumps(payload, separators=(',', ':'), default=_json_default).encode('utf-8')
    key = os.getenv('MEM_ENCRYPTION_KEY', '')
    blob = _encrypt_blob(plaintext, key)
    with open(dump_path, 'wb') as f:
        f.write(blob)
    return dump_path

def restore_memory_from_file(path: Optional[str] = None) -> dict:
    if not database.memory_only:
        raise RuntimeError('Memory restore is only available in memory-only mode')
    dump_path = path or DEFAULT_DUMP_PATH
    if not os.path.exists(dump_path):
        raise FileNotFoundError('Dump file not found')
    key = os.getenv('MEM_ENCRYPTION_KEY', '')
    with open(dump_path, 'rb') as f:
        blob = f.read()
    plaintext = _decrypt_blob(blob, key)
    payload = json.loads(plaintext.decode('utf-8'))

    data = _from_jsonable(payload.get('data', {}))
    database.db.load_data(data)
    try:
        from utils.database import user_collection
        from utils import password_util as _pw
        import os as _os
        admin = user_collection.find_one({'username': 'admin'})
        if admin is not None and not isinstance(admin.get('password'), (bytes, bytearray)):
            pwd = _os.getenv('STARTUP_ADMIN_PASSWORD') or 'password1'
            user_collection.update_one({'username': 'admin'}, {'$set': {'password': _pw.hash_password(pwd)}})
    except Exception:
        pass
    return {'version': payload.get('version', 1), 'created_at': payload.get('created_at')}

def find_latest_dump_path(path_hint: Optional[str] = None) -> Optional[str]:
    """Return the most recent dump file path based on a hint.

    - If `path_hint` is a file and exists, return it.
    - If `path_hint` is a directory, search for .bin files and pick the newest.
    - If no hint or not found, try DEFAULT_DUMP_PATH, or its directory for .bin files.
    """
    def newest_bin_in_dir(d: str, stem: Optional[str] = None) -> Optional[str]:
        try:
            if not os.path.isdir(d):
                return None
            candidates = [
                os.path.join(d, f)
                for f in os.listdir(d)
                if f.lower().endswith('.bin') and os.path.isfile(os.path.join(d, f))
                and (stem is None or f.startswith(stem + '-'))
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return candidates[0]
        except Exception:
            return None

    dump_dir, stem = _split_dir_and_stem(path_hint)

    latest = newest_bin_in_dir(dump_dir, stem)
    if latest:
        return latest

    def_dir, def_stem = _split_dir_and_stem(DEFAULT_DUMP_PATH)
    latest = newest_bin_in_dir(def_dir, def_stem)
    if latest:
        return latest

    latest = newest_bin_in_dir(def_dir)
    return latest
