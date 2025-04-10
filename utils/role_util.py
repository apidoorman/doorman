"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

import logging
from fastapi import HTTPException
from fastapi_jwt_auth.exceptions import MissingTokenError
from utils.database import role_collection
from utils.pygate_cache_util import pygate_cache
from services.user_service import UserService

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@staticmethod
async def validate_platform_role(role_name, action):
    """
    Get the platform roles from the cache or database.
    """
    try:
        role = pygate_cache.get_cache("role_cache", role_name)
        if not role:
            role = role_collection.find_one({"role_name": role_name})
            if not role:
                raise ValueError("Role not found")
            if role.get("_id"): del role["_id"]
            pygate_cache.set_cache("role_cache", role_name, role)
        if not role:
            raise ValueError("No roles found for validation")
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
        return False
    except Exception as e:
        logger.error(f"Error getting platform roles: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

async def platform_role_required_bool(username, action):
    try:
        user = await UserService.get_user_by_username_helper(username)
        if not await validate_platform_role(user.get('role'), action):
            raise HTTPException(status_code=403, detail="You do not have the correct role for this")
        return True
    except MissingTokenError:
        raise HTTPException(status_code=401, detail="Missing token")
    except HTTPException as e:
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False