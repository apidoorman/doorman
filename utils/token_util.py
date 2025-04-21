from utils.database import user_token_collection

async def deduct_ai_token(api, username):
    token_group = api.get('api_token_group')
    if not token_group:
        return False
    user_tokens_doc = await user_token_collection.find_one({'username': username})
    if not user_tokens_doc:
        return False
    user_tokens = user_tokens_doc.get('users_tokens') or {}
    token_info = user_tokens.get(token_group)
    if not token_info or token_info.get('available_tokens', 0) <= 0:
        return False
    available_tokens = token_info.get('available_tokens', 0) - 1
    await user_token_collection.update_one({'username': username}, {'$set': {f'users_tokens.{token_group}.available_tokens': available_tokens}})
    return True