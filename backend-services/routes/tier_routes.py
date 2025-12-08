"""
Tier Management API Routes

FastAPI routes for managing tiers, plans, and user assignments.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from pydantic import BaseModel, Field
import uuid
import time

from models.rate_limit_models import Tier, TierLimits, TierName, UserTierAssignment
from models.response_model import ResponseModel
from services.tier_service import TierService, get_tier_service
from utils.database_async import async_database
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.response_util import respond_rest

logger = logging.getLogger(__name__)

tier_router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TierLimitsRequest(BaseModel):
    """Request model for tier limits"""
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    requests_per_month: Optional[int] = None
    burst_per_second: int = 0
    burst_per_minute: int = 0
    burst_per_hour: int = 0
    monthly_request_quota: Optional[int] = None
    daily_request_quota: Optional[int] = None
    monthly_bandwidth_quota: Optional[int] = None
    enable_throttling: bool = False
    max_queue_time_ms: int = 5000


class TierCreateRequest(BaseModel):
    """Request model for creating a tier"""
    tier_id: str = Field(..., description="Unique tier identifier")
    name: str = Field(..., description="Tier name (free, pro, enterprise, custom)")
    display_name: str = Field(..., description="Display name for tier")
    description: Optional[str] = None
    limits: TierLimitsRequest
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    features: List[str] = []
    is_default: bool = False
    enabled: bool = True


class TierUpdateRequest(BaseModel):
    """Request model for updating a tier"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    limits: Optional[TierLimitsRequest] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    features: Optional[List[str]] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None


class UserAssignmentRequest(BaseModel):
    """Request model for assigning user to tier"""
    user_id: str
    tier_id: str
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    override_limits: Optional[TierLimitsRequest] = None
    notes: Optional[str] = None


class TierUpgradeRequest(BaseModel):
    """Request model for tier upgrade"""
    user_id: str
    new_tier_id: str
    immediate: bool = True
    scheduled_date: Optional[datetime] = None


class TierDowngradeRequest(BaseModel):
    """Request model for tier downgrade"""
    user_id: str
    new_tier_id: str
    grace_period_days: int = 0


class TemporaryUpgradeRequest(BaseModel):
    """Request model for temporary tier upgrade"""
    user_id: str
    temp_tier_id: str
    duration_days: int


class TierResponse(BaseModel):
    """Response model for tier"""
    tier_id: str
    name: str
    display_name: str
    description: Optional[str]
    limits: dict
    price_monthly: Optional[float]
    price_yearly: Optional[float]
    features: List[str]
    is_default: bool
    enabled: bool
    created_at: Optional[str]
    updated_at: Optional[str]


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_tier_service_dep() -> TierService:
    """Dependency to get tier service"""
    return get_tier_service(async_database.db)


# ============================================================================
# TIER CRUD ENDPOINTS
# ============================================================================

@tier_router.post("/", response_model=TierResponse, status_code=status.HTTP_201_CREATED)
async def create_tier(
    request: TierCreateRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Create a new tier
    
    Requires admin permissions.
    """
    try:
        # Convert request to Tier object
        tier = Tier(
            tier_id=request.tier_id,
            name=TierName(request.name),
            display_name=request.display_name,
            description=request.description,
            limits=TierLimits(**request.limits.dict()),
            price_monthly=request.price_monthly,
            price_yearly=request.price_yearly,
            features=request.features,
            is_default=request.is_default,
            enabled=request.enabled
        )
        
        created_tier = await tier_service.create_tier(tier)
        
        return TierResponse(
            **created_tier.to_dict(),
            created_at=created_tier.created_at.isoformat() if created_tier.created_at else None,
            updated_at=created_tier.updated_at.isoformat() if created_tier.updated_at else None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tier")


@tier_router.get("/")
async def list_tiers(
    request: Request,
    enabled_only: bool = Query(False, description="Only return enabled tiers"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    List all tiers
    
    Can filter by enabled status and paginate results.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        
        if not await platform_role_required_bool(username, 'manage_tiers'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='TIER001',
                error_message='You do not have permission to manage tiers'
            ))
        
        tiers = await tier_service.list_tiers(enabled_only=enabled_only, skip=skip, limit=limit)
        
        tier_list = [
            TierResponse(
                **tier.to_dict(),
                created_at=tier.created_at.isoformat() if tier.created_at else None,
                updated_at=tier.updated_at.isoformat() if tier.updated_at else None
            ).dict()
            for tier in tiers
        ]
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=tier_list
        ))
        
    except Exception as e:
        logger.error(f'{request_id} | Error listing tiers: {e}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='TIER999',
            error_message='Failed to list tiers'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


@tier_router.get("/{tier_id}", response_model=TierResponse)
async def get_tier(
    tier_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get a specific tier by ID
    """
    try:
        tier = await tier_service.get_tier(tier_id)
        
        if not tier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tier {tier_id} not found")
        
        return TierResponse(
            **tier.to_dict(),
            created_at=tier.created_at.isoformat() if tier.created_at else None,
            updated_at=tier.updated_at.isoformat() if tier.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tier")


@tier_router.put("/{tier_id}", response_model=TierResponse)
async def update_tier(
    tier_id: str,
    request: TierUpdateRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Update a tier
    
    Requires admin permissions.
    """
    try:
        # Build updates dictionary
        updates = {}
        if request.display_name is not None:
            updates['display_name'] = request.display_name
        if request.description is not None:
            updates['description'] = request.description
        if request.limits is not None:
            updates['limits'] = request.limits.dict()
        if request.price_monthly is not None:
            updates['price_monthly'] = request.price_monthly
        if request.price_yearly is not None:
            updates['price_yearly'] = request.price_yearly
        if request.features is not None:
            updates['features'] = request.features
        if request.is_default is not None:
            updates['is_default'] = request.is_default
        if request.enabled is not None:
            updates['enabled'] = request.enabled
        
        updated_tier = await tier_service.update_tier(tier_id, updates)
        
        if not updated_tier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tier {tier_id} not found")
        
        return TierResponse(
            **updated_tier.to_dict(),
            created_at=updated_tier.created_at.isoformat() if updated_tier.created_at else None,
            updated_at=updated_tier.updated_at.isoformat() if updated_tier.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update tier")


@tier_router.delete("/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tier(
    tier_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Delete a tier
    
    Requires admin permissions.
    Cannot delete tier if users are assigned to it.
    """
    try:
        deleted = await tier_service.delete_tier(tier_id)
        
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tier {tier_id} not found")
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tier")


# ============================================================================
# USER ASSIGNMENT ENDPOINTS
# ============================================================================

@tier_router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def assign_user_to_tier(
    request: UserAssignmentRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Assign a user to a tier
    
    Requires admin permissions.
    """
    try:
        # Convert override limits if provided
        override_limits = None
        if request.override_limits:
            override_limits = TierLimits(**request.override_limits.dict())
        
        assignment = await tier_service.assign_user_to_tier(
            user_id=request.user_id,
            tier_id=request.tier_id,
            effective_from=request.effective_from,
            effective_until=request.effective_until,
            override_limits=override_limits,
            notes=request.notes
        )
        
        return assignment.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning user to tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to assign user")


@tier_router.get("/assignments/{user_id}")
async def get_user_assignment(
    user_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get a user's tier assignment
    """
    try:
        assignment = await tier_service.get_user_assignment(user_id)
        
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No assignment found for user {user_id}")
        
        return assignment.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user assignment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get assignment")


@tier_router.get("/assignments/{user_id}/tier", response_model=TierResponse)
async def get_user_tier(
    user_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get the effective tier for a user
    
    Considers effective dates and returns current tier.
    """
    try:
        tier = await tier_service.get_user_tier(user_id)
        
        if not tier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No tier found for user {user_id}")
        
        return TierResponse(
            **tier.to_dict(),
            created_at=tier.created_at.isoformat() if tier.created_at else None,
            updated_at=tier.updated_at.isoformat() if tier.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get user tier")


@tier_router.delete("/assignments/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_assignment(
    user_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Remove a user's tier assignment
    
    Requires admin permissions.
    """
    try:
        removed = await tier_service.remove_user_assignment(user_id)
        
        if not removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No assignment found for user {user_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user assignment: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove assignment")


@tier_router.get("/{tier_id}/users")
async def list_users_in_tier(
    tier_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    List all users assigned to a tier
    
    Requires admin permissions.
    """
    try:
        assignments = await tier_service.list_users_in_tier(tier_id, skip=skip, limit=limit)
        
        return [assignment.to_dict() for assignment in assignments]
        
    except Exception as e:
        logger.error(f"Error listing users in tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list users")


# ============================================================================
# TIER UPGRADE/DOWNGRADE ENDPOINTS
# ============================================================================

@tier_router.post("/upgrade")
async def upgrade_user_tier(
    request: TierUpgradeRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Upgrade a user to a higher tier
    
    Requires admin permissions.
    """
    try:
        assignment = await tier_service.upgrade_user_tier(
            user_id=request.user_id,
            new_tier_id=request.new_tier_id,
            immediate=request.immediate,
            scheduled_date=request.scheduled_date
        )
        
        return assignment.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error upgrading user tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upgrade tier")


@tier_router.post("/downgrade")
async def downgrade_user_tier(
    request: TierDowngradeRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Downgrade a user to a lower tier
    
    Requires admin permissions.
    """
    try:
        assignment = await tier_service.downgrade_user_tier(
            user_id=request.user_id,
            new_tier_id=request.new_tier_id,
            grace_period_days=request.grace_period_days
        )
        
        return assignment.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error downgrading user tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to downgrade tier")


@tier_router.post("/temporary-upgrade")
async def temporary_tier_upgrade(
    request: TemporaryUpgradeRequest,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Temporarily upgrade a user to a higher tier
    
    Requires admin permissions.
    """
    try:
        assignment = await tier_service.temporary_tier_upgrade(
            user_id=request.user_id,
            temp_tier_id=request.temp_tier_id,
            duration_days=request.duration_days
        )
        
        return assignment.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating temporary upgrade: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create temporary upgrade")


# ============================================================================
# TIER COMPARISON & ANALYTICS ENDPOINTS
# ============================================================================

@tier_router.post("/compare")
async def compare_tiers(
    tier_ids: List[str],
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Compare multiple tiers side-by-side
    """
    try:
        comparison = await tier_service.compare_tiers(tier_ids)
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing tiers: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to compare tiers")


@tier_router.get("/statistics/all")
async def get_all_tier_statistics(
    request: Request,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get statistics for all tiers
    
    Requires admin permissions.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        
        if not await platform_role_required_bool(username, 'manage_tiers'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='TIER001',
                error_message='You do not have permission to manage tiers'
            ))
        
        stats = await tier_service.get_all_tier_statistics()
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=stats
        ))
        
    except Exception as e:
        logger.error(f'{request_id} | Error getting all tier statistics: {e}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='TIER999',
            error_message='Failed to get statistics'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')


@tier_router.get("/{tier_id}/statistics")
async def get_tier_statistics(
    request: Request,
    tier_id: str,
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get statistics for a tier
    
    Requires admin permissions.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        
        if not await platform_role_required_bool(username, 'manage_tiers'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='TIER001',
                error_message='You do not have permission to manage tiers'
            ))
        
        stats = await tier_service.get_tier_statistics(tier_id)
        
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=stats
        ))
        
    except Exception as e:
        logger.error(f'{request_id} | Error getting tier statistics: {e}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='TIER999',
            error_message='Failed to get statistics'
        ))
    
    finally:
        end_time = time.time()
        logger.info(f'{request_id} | Total time: {(end_time - start_time) * 1000:.2f}ms')
