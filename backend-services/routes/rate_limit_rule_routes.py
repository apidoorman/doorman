"""
Rate Limit Rule API Routes

FastAPI routes for managing rate limit rules.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field

from models.rate_limit_models import RateLimitRule, RuleType, TimeWindow
from services.rate_limit_rule_service import RateLimitRuleService, get_rate_limit_rule_service
from utils.database_async import async_database

logger = logging.getLogger(__name__)

rate_limit_rule_router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RuleCreateRequest(BaseModel):
    """Request model for creating a rule"""
    rule_id: str = Field(..., description="Unique rule identifier")
    rule_type: str = Field(..., description="Rule type (per_user, per_api, per_endpoint, per_ip, global)")
    time_window: str = Field(..., description="Time window (second, minute, hour, day, month)")
    limit: int = Field(..., gt=0, description="Maximum requests allowed")
    target_identifier: Optional[str] = Field(None, description="Target (user ID, API name, endpoint, IP)")
    burst_allowance: int = Field(0, ge=0, description="Additional burst requests")
    priority: int = Field(0, description="Rule priority (higher = checked first)")
    enabled: bool = Field(True, description="Whether rule is enabled")
    description: Optional[str] = Field(None, description="Rule description")


class RuleUpdateRequest(BaseModel):
    """Request model for updating a rule"""
    limit: Optional[int] = Field(None, gt=0)
    target_identifier: Optional[str] = None
    burst_allowance: Optional[int] = Field(None, ge=0)
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class BulkRuleRequest(BaseModel):
    """Request model for bulk operations"""
    rule_ids: List[str]


class RuleDuplicateRequest(BaseModel):
    """Request model for duplicating a rule"""
    new_rule_id: str


class RuleResponse(BaseModel):
    """Response model for rule"""
    rule_id: str
    rule_type: str
    time_window: str
    limit: int
    target_identifier: Optional[str]
    burst_allowance: int
    priority: int
    enabled: bool
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_rule_service_dep() -> RateLimitRuleService:
    """Dependency to get rule service"""
    return get_rate_limit_rule_service(async_database.db)


# ============================================================================
# RULE CRUD ENDPOINTS
# ============================================================================

@rate_limit_rule_router.post("/", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: RuleCreateRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Create a new rate limit rule"""
    try:
        rule = RateLimitRule(
            rule_id=request.rule_id,
            rule_type=RuleType(request.rule_type),
            time_window=TimeWindow(request.time_window),
            limit=request.limit,
            target_identifier=request.target_identifier,
            burst_allowance=request.burst_allowance,
            priority=request.priority,
            enabled=request.enabled,
            description=request.description
        )
        
        # Validate rule
        errors = rule_service.validate_rule(rule)
        if errors:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errors})
        
        created_rule = await rule_service.create_rule(rule)
        
        return RuleResponse(**created_rule.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create rule")


@rate_limit_rule_router.get("/", response_model=List[RuleResponse])
async def list_rules(
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    enabled_only: bool = Query(False, description="Only return enabled rules"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """List all rate limit rules"""
    try:
        rule_type_enum = RuleType(rule_type) if rule_type else None
        rules = await rule_service.list_rules(
            rule_type=rule_type_enum,
            enabled_only=enabled_only,
            skip=skip,
            limit=limit
        )
        
        return [RuleResponse(**rule.to_dict()) for rule in rules]
        
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list rules")


@rate_limit_rule_router.get("/search")
async def search_rules(
    q: str = Query(..., description="Search term"),
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Search rules by ID, description, or target"""
    try:
        rules = await rule_service.search_rules(q)
        return [RuleResponse(**rule.to_dict()) for rule in rules]
        
    except Exception as e:
        logger.error(f"Error searching rules: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search rules")


@rate_limit_rule_router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Get a specific rule by ID"""
    try:
        rule = await rule_service.get_rule(rule_id)
        
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
        
        return RuleResponse(**rule.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get rule")


@rate_limit_rule_router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    request: RuleUpdateRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Update a rate limit rule"""
    try:
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        updated_rule = await rule_service.update_rule(rule_id, updates)
        
        if not updated_rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
        
        return RuleResponse(**updated_rule.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update rule")


@rate_limit_rule_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Delete a rate limit rule"""
    try:
        deleted = await rule_service.delete_rule(rule_id)
        
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete rule")


@rate_limit_rule_router.post("/{rule_id}/enable", response_model=RuleResponse)
async def enable_rule(
    rule_id: str,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Enable a rule"""
    try:
        rule = await rule_service.enable_rule(rule_id)
        
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
        
        return RuleResponse(**rule.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable rule")


@rate_limit_rule_router.post("/{rule_id}/disable", response_model=RuleResponse)
async def disable_rule(
    rule_id: str,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Disable a rule"""
    try:
        rule = await rule_service.disable_rule(rule_id)
        
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")
        
        return RuleResponse(**rule.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable rule")


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@rate_limit_rule_router.post("/bulk/delete")
async def bulk_delete_rules(
    request: BulkRuleRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Delete multiple rules at once"""
    try:
        count = await rule_service.bulk_delete_rules(request.rule_ids)
        return {"deleted_count": count}
        
    except Exception as e:
        logger.error(f"Error bulk deleting rules: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete rules")


@rate_limit_rule_router.post("/bulk/enable")
async def bulk_enable_rules(
    request: BulkRuleRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Enable multiple rules at once"""
    try:
        count = await rule_service.bulk_enable_rules(request.rule_ids)
        return {"enabled_count": count}
        
    except Exception as e:
        logger.error(f"Error bulk enabling rules: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable rules")


@rate_limit_rule_router.post("/bulk/disable")
async def bulk_disable_rules(
    request: BulkRuleRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Disable multiple rules at once"""
    try:
        count = await rule_service.bulk_disable_rules(request.rule_ids)
        return {"disabled_count": count}
        
    except Exception as e:
        logger.error(f"Error bulk disabling rules: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable rules")


# ============================================================================
# RULE DUPLICATION
# ============================================================================

@rate_limit_rule_router.post("/{rule_id}/duplicate", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_rule(
    rule_id: str,
    request: RuleDuplicateRequest,
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Duplicate an existing rule"""
    try:
        new_rule = await rule_service.duplicate_rule(rule_id, request.new_rule_id)
        return RuleResponse(**new_rule.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error duplicating rule: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to duplicate rule")


# ============================================================================
# STATISTICS
# ============================================================================

@rate_limit_rule_router.get("/statistics/summary")
async def get_rule_statistics(
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """Get statistics about rate limit rules"""
    try:
        stats = await rule_service.get_rule_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting rule statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get statistics")


# ============================================================================
# RATE LIMIT STATUS ENDPOINT (User-facing)
# ============================================================================

@rate_limit_rule_router.get("/status")
async def get_rate_limit_status(
    rule_service: RateLimitRuleService = Depends(get_rule_service_dep)
):
    """
    Get current rate limit status for the authenticated user
    
    Returns applicable rate limit rules and current usage.
    This is a user-facing endpoint showing their current limits.
    """
    try:
        # TODO: Get user_id from auth middleware
        user_id = "current_user"
        
        # Get applicable rules for user
        rules = await rule_service.get_applicable_rules(user_id=user_id)
        
        # Format response
        status_info = {
            'user_id': user_id,
            'applicable_rules': [
                {
                    'rule_id': rule.rule_id,
                    'rule_type': rule.rule_type.value,
                    'time_window': rule.time_window.value,
                    'limit': rule.limit,
                    'burst_allowance': rule.burst_allowance,
                    'description': rule.description
                }
                for rule in rules
            ],
            'note': 'Use /platform/quota/status for detailed usage information'
        }
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get rate limit status"
        )

