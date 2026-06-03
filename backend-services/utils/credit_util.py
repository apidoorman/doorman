import os
from datetime import UTC, datetime

from utils.async_db import db_find_one, db_update_one
from utils.database_async import credit_def_collection, user_credit_collection
from utils.encryption_util import decrypt_value


async def ensure_anonymous_credits(credit_group: str, username: str) -> bool:
    """Initialise a credit document for an anonymous (IP-keyed) identity if one does not exist.

    Called before every anonymous gateway request. The function is a no-op when
    the credit document already contains the requested group.

    The default credit allowance is controlled by the ANON_DEFAULT_CREDITS
    environment variable (default: 100).

    Returns:
        True  — the credit document is known to exist (already present or just created).
        False — a transient error prevented initialisation; the caller should allow the
                request through without deducting credits rather than returning a
                spurious 401.

    Args:
        credit_group: The credit group name configured on the API.
        username:     Anonymous identity string, e.g. "anon:192.168.1.1".
    """
    if not credit_group or not username:
        return False
    try:
        default_credits = int(os.getenv('ANON_DEFAULT_CREDITS', '100'))
        credit_entry = {
            'tier_name': 'anonymous',
            'available_credits': default_credits,
            'user_api_key': None,
        }
        doc = await db_find_one(user_credit_collection, {'username': username})
        if doc is None:
            # First request from this IP — create the credit document.
            # Ignore duplicate-key errors from concurrent first-requests (race condition).
            from utils.async_db import db_insert_one
            try:
                await db_insert_one(
                    user_credit_collection,
                    {'username': username, 'users_credits': {credit_group: credit_entry}},
                )
            except Exception:
                # Likely a duplicate-key from a concurrent request — the doc now exists.
                pass
        elif (doc.get('users_credits') or {}).get(credit_group) is None:
            # Doc exists but this credit group is new (e.g., API reconfigured)
            await db_update_one(
                user_credit_collection,
                {'username': username},
                {'$set': {f'users_credits.{credit_group}': credit_entry}},
            )
        return True
    except Exception:
        # Transient DB error — caller should allow the request through rather than
        # returning a misleading 401 due to an infrastructure failure.
        return False


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
    if not info:
        return None
    # Expiry check — None means no expiry (backward-compatible with pre-existing records)
    expires_at_raw = info.get('user_api_key_expires_at')
    if expires_at_raw is not None:
        try:
            from datetime import timezone
            if isinstance(expires_at_raw, str):
                expires_dt = datetime.fromisoformat(expires_at_raw.replace('Z', '+00:00'))
            elif isinstance(expires_at_raw, datetime):
                expires_dt = expires_at_raw
            else:
                expires_dt = None
            if expires_dt is not None:
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if datetime.now(UTC) >= expires_dt:
                    return None  # Key has expired
        except Exception:
            pass  # Malformed expiry — treat as non-expiring
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
