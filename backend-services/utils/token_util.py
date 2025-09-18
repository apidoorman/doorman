from utils.database import user_token_collection, token_def_collection
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

async def deduct_ai_token(api_token_group, username):
    if not api_token_group:
        return False
    user_tokens_doc = user_token_collection.find_one({'username': username})
    if not user_tokens_doc:
        return False
    user_tokens = user_tokens_doc.get('users_tokens') or {}
    token_info = user_tokens.get(api_token_group)
    if not token_info or token_info.get('available_tokens', 0) <= 0:
        return False
    available_tokens = token_info.get('available_tokens', 0) - 1
    user_token_collection.update_one({'username': username}, {'$set': {f'users_tokens.{api_token_group}.available_tokens': available_tokens}})
    return True

async def get_user_api_key(api_token_group, username):
    if not api_token_group:
        return None
    user_tokens_doc = user_token_collection.find_one({'username': username})
    if not user_tokens_doc:
        return None
    user_tokens = user_tokens_doc.get('users_tokens') or {}
    token_info = user_tokens.get(api_token_group)
    enc = token_info.get('user_api_key')
    dec = decrypt_value(enc)
    return dec if dec is not None else enc

async def get_token_api_header(api_token_group):
    if not api_token_group:
        return None
    token_def = token_def_collection.find_one({'api_token_group': api_token_group})
    if not token_def:
        return None
    api_key = token_def.get('api_key')
    dec = decrypt_value(api_key)
    return [token_def.get('api_key_header'), (dec if dec is not None else api_key)]
