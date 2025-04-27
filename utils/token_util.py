from utils.database import user_token_collection, token_def_collection

async def deduct_ai_token(api_token_group, username):
    if not api_token_group:
        return False
    user_tokens_doc = await user_token_collection.find_one({'username': username})
    if not user_tokens_doc:
        return False
    user_tokens = user_tokens_doc.get('users_tokens') or {}
    token_info = user_tokens.get(api_token_group)
    if not token_info or token_info.get('available_tokens', 0) <= 0:
        return False
    available_tokens = token_info.get('available_tokens', 0) - 1
    await user_token_collection.update_one({'username': username}, {'$set': {f'users_tokens.{api_token_group}.available_tokens': available_tokens}})
    return True

async def get_user_api_key(api_token_group, username):
    if not api_token_group:
        return None
    user_tokens_doc = await user_token_collection.find_one({'username': username})
    if not user_tokens_doc:
        return None
    user_tokens = user_tokens_doc.get('users_tokens') or {}
    token_info = user_tokens.get(api_token_group)
    return token_info.get('user_api_key')

async def get_token_api_heaeder(api_token_group):
    token_def = await token_def_collection.find_one({'api_token_group': api_token_group})
    if not token_def:
        return None
    #TODO: encrypt/decrypt api key
    return [api_token_group.get('api_key_header'), api_token_group.get('api_key')]