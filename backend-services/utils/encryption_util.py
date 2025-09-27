from typing import Optional
import os
import base64
import hashlib
from cryptography.fernet import Fernet


def _get_cipher() -> Optional[Fernet]:
    """Return a Fernet cipher derived from TOKEN_ENCRYPTION_KEY or MEM_ENCRYPTION_KEY.
    If neither is set, returns None (plaintext compatibility mode).
    """
    key = os.getenv("TOKEN_ENCRYPTION_KEY") or os.getenv("MEM_ENCRYPTION_KEY")
    if not key:
        return None
    try:
        # Try to treat provided key as a valid Fernet key
        Fernet(key)
        fkey = key
    except Exception:
        # Derive a Fernet key from arbitrary secret
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        fkey = base64.urlsafe_b64encode(digest)
    return Fernet(fkey)


def encrypt_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cipher = _get_cipher()
    if not cipher:
        return value
    token = cipher.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"enc:{token}"


def decrypt_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    if not value.startswith("enc:"):
        return value
    cipher = _get_cipher()
    if not cipher:
        # Cannot decrypt without key
        return None
    try:
        raw = value[4:]
        return cipher.decrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return None

