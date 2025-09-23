"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
from fastapi import HTTPException
from utils.database import role_collection, user_collection
from utils.doorman_cache_util import doorman_cache

logger = logging.getLogger("doorman.gateway")

async def validate_platform_role(role_name, action):
    """
    Get the platform roles from the cache or database.
    """
    try:
        role = doorman_cache.get_cache("role_cache", role_name)
        if not role:
            role = role_collection.find_one({"role_name": role_name})
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            if role.get("_id"): del role["_id"]
            doorman_cache.set_cache("role_cache", role_name, role)
        if action == "manage_users" and role.get("manage_users"):
            return True
        elif action == "manage_apis" and role.get("manage_apis"):
            return True
        elif action == "manage_endpoints" and role.get("manage_endpoints"):
            return True
        elif action == "manage_groups" and role.get("manage_groups"):
            return True
        elif action == "manage_roles" and role.get("manage_roles"):
            return True
        elif action == "manage_routings" and role.get("manage_routings"):
            return True
        elif action == "manage_gateway" and role.get("manage_gateway"):
            return True
        elif action == "manage_subscriptions" and role.get("manage_subscriptions"):
            return True
        elif action == "manage_security" and role.get("manage_security"):
            return True
        elif action == "manage_credits" and role.get("manage_credits"):
            return True
        elif action == "manage_auth" and role.get("manage_auth"):
            return True
        elif action == "view_logs" and role.get("view_logs"):
            return True
        elif action == "export_logs" and role.get("export_logs"):
            return True
        return False
    except Exception as e:
        logger.error(f"validate_platform_role error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

async def platform_role_required_bool(username, action):
    try:
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not await validate_platform_role(user.get('role'), action):
            raise HTTPException(status_code=403, detail="You do not have the correct role for this")
        return True
    except HTTPException as e:
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
