from datetime import UTC, datetime

from utils.async_db import db_find_one, db_update_one
from utils.database_async import credit_def_collection, user_credit_collection
from utils.encryption_util import decrypt_value


async def deduct_credit(api_credit_group, username):
    if not api_credit_group:
        return False
    doc = await db_find_one(user_credit_collection, {'username': username})
    if not doc:
        return False
    users_credits = doc.get('users_credits') or {}
    info = users_credits.get(api_credit_group)
    if not info or info.get('available_credits', 0) <= 0:
        return False
    available_credits = info.get('available_credits', 0) - 1
    await db_update_one(
        user_credit_collection,
        {'username': username},
        {'$set': {f'users_credits.{api_credit_group}.available_credits': available_credits}},
    )
    return True


async def get_user_api_key(api_credit_group, username):
    if not api_credit_group:
        return None
    doc = await db_find_one(user_credit_collection, {'username': username})
    if not doc:
        return None
    users_credits = doc.get('users_credits') or {}
    info = users_credits.get(api_credit_group)
    enc = info.get('user_api_key')
    dec = decrypt_value(enc)
    return dec if dec is not None else enc


async def get_credit_api_header(api_credit_group):
    """
    Get credit API header and key, supporting rotation.

    During rotation period:
    - Returns list of [header, [old_key, new_key]]
    - Both keys are accepted until rotation_expires

    After rotation expires:
    - Returns list of [header, new_key]
    - Only new key is accepted

    Returns:
        [header_name, key] or [header_name, [old_key, new_key]] or None
    """
    if not api_credit_group:
        return None
    credit_def = await db_find_one(credit_def_collection, {'api_credit_group': api_credit_group})
    if not credit_def:
        return None

    api_key_header = credit_def.get('api_key_header')
    api_key_encrypted = credit_def.get('api_key')
    api_key_new_encrypted = credit_def.get('api_key_new')
    rotation_expires = credit_def.get('api_key_rotation_expires')

    api_key = decrypt_value(api_key_encrypted)
    api_key = api_key if api_key is not None else api_key_encrypted

    if api_key_new_encrypted and rotation_expires:
        if isinstance(rotation_expires, str):
            try:
                rotation_expires_dt = datetime.fromisoformat(
                    rotation_expires.replace('Z', '+00:00')
                )
            except Exception:
                rotation_expires_dt = None
        elif isinstance(rotation_expires, datetime):
            rotation_expires_dt = rotation_expires
        else:
            rotation_expires_dt = None

        now = datetime.now(UTC)
        if rotation_expires_dt and now < rotation_expires_dt:
            api_key_new = decrypt_value(api_key_new_encrypted)
            api_key_new = api_key_new if api_key_new is not None else api_key_new_encrypted
            return [api_key_header, [api_key, api_key_new]]
        elif rotation_expires_dt and now >= rotation_expires_dt:
            api_key_new = decrypt_value(api_key_new_encrypted)
            api_key_new = api_key_new if api_key_new is not None else api_key_new_encrypted
            return [api_key_header, api_key_new]

    return [api_key_header, api_key]
