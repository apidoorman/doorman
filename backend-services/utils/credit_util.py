from utils.database import user_credit_collection, credit_def_collection
from utils.encryption_util import decrypt_value

async def deduct_credit(api_credit_group, username):
    if not api_credit_group:
        return False
    doc = user_credit_collection.find_one({'username': username})
    if not doc:
        return False
    users_credits = doc.get('users_credits') or {}
    info = users_credits.get(api_credit_group)
    if not info or info.get('available_credits', 0) <= 0:
        return False
    available_credits = info.get('available_credits', 0) - 1
    user_credit_collection.update_one({'username': username}, {'$set': {f'users_credits.{api_credit_group}.available_credits': available_credits}})
    return True

async def get_user_api_key(api_credit_group, username):
    if not api_credit_group:
        return None
    doc = user_credit_collection.find_one({'username': username})
    if not doc:
        return None
    users_credits = doc.get('users_credits') or {}
    info = users_credits.get(api_credit_group)
    enc = info.get('user_api_key')
    dec = decrypt_value(enc)
    return dec if dec is not None else enc

async def get_credit_api_header(api_credit_group):
    if not api_credit_group:
        return None
    credit_def = credit_def_collection.find_one({'api_credit_group': api_credit_group})
    if not credit_def:
        return None
    api_key = credit_def.get('api_key')
    dec = decrypt_value(api_key)
    return [credit_def.get('api_key_header'), (dec if dec is not None else api_key)]
