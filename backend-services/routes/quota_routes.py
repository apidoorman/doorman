"""
Quota Status API Routes

FastAPI routes for quota tracking and status information.
User-facing endpoints for checking current usage and limits.
"""

import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from models.rate_limit_models import QuotaType, TierLimits
from services.tier_service import TierService, get_tier_service
from utils.quota_tracker import QuotaTracker, get_quota_tracker
from utils.database_async import async_database

logger = logging.getLogger(__name__)

quota_router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class QuotaStatusResponse(BaseModel):
    """Response model for quota status"""
    quota_type: str
    current_usage: int
    limit: int
    remaining: int
    percentage_used: float
    reset_at: str
    is_warning: bool
    is_critical: bool
    is_exhausted: bool
    burst_used: int = 0
    burst_limit: int = 0
    burst_percentage: float = 0.0


class TierInfoResponse(BaseModel):
    """Response model for tier information"""
    tier_id: str
    tier_name: str
    display_name: str
    limits: dict
    price_monthly: Optional[float]
    features: list


class QuotaDashboardResponse(BaseModel):
    """Complete quota dashboard response"""
    user_id: str
    tier_info: TierInfoResponse
    quotas: list
    usage_summary: dict


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_quota_tracker_dep() -> QuotaTracker:
    """Dependency to get quota tracker"""
    return get_quota_tracker()


async def get_tier_service_dep() -> TierService:
    """Dependency to get tier service"""
    db = async_database.db
    return get_tier_service(db)


def get_current_user_id() -> str:
    """
    Get current user ID from request context
    
    In production, this should extract from JWT token or session.
    For now, returns a placeholder.
    """
    # TODO: Extract from auth middleware
    return "current_user"


# ============================================================================
# QUOTA STATUS ENDPOINTS
# ============================================================================

@quota_router.get("/status", response_model=QuotaDashboardResponse)
async def get_quota_status(
    user_id: str = Depends(get_current_user_id),
    quota_tracker: QuotaTracker = Depends(get_quota_tracker_dep),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get complete quota status for current user
    
    Returns:
    - Current tier information
    - All quota usages
    - Usage summary
    """
    try:
        # Get user's tier
        tier = await tier_service.get_user_tier(user_id)
        
        if not tier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tier assigned to user"
            )
        
        # Get user's effective limits (including overrides)
        limits = await tier_service.get_user_limits(user_id)
        
        if not limits:
            limits = tier.limits
        
        # Check all quotas
        quotas = []
        
        # Monthly request quota
        if limits.monthly_request_quota:
            result = quota_tracker.check_quota(
                user_id,
                QuotaType.REQUESTS,
                limits.monthly_request_quota,
                'month'
            )
            quotas.append(QuotaStatusResponse(
                quota_type='monthly_requests',
                current_usage=result.current_usage,
                limit=result.limit,
                remaining=result.remaining,
                percentage_used=result.percentage_used,
                reset_at=result.reset_at.isoformat(),
                is_warning=result.is_warning,
                is_critical=result.is_critical,
                is_exhausted=result.is_exhausted
            ))
        
        # Daily request quota
        if limits.daily_request_quota:
            result = quota_tracker.check_quota(
                user_id,
                QuotaType.REQUESTS,
                limits.daily_request_quota,
                'day'
            )
            quotas.append(QuotaStatusResponse(
                quota_type='daily_requests',
                current_usage=result.current_usage,
                limit=result.limit,
                remaining=result.remaining,
                percentage_used=result.percentage_used,
                reset_at=result.reset_at.isoformat(),
                is_warning=result.is_warning,
                is_critical=result.is_critical,
                is_exhausted=result.is_exhausted
            ))
        
        # Monthly bandwidth quota
        if limits.monthly_bandwidth_quota:
            result = quota_tracker.check_quota(
                user_id,
                QuotaType.BANDWIDTH,
                limits.monthly_bandwidth_quota,
                'month'
            )
            quotas.append(QuotaStatusResponse(
                quota_type='monthly_bandwidth',
                current_usage=result.current_usage,
                limit=result.limit,
                remaining=result.remaining,
                percentage_used=result.percentage_used,
                reset_at=result.reset_at.isoformat(),
                is_warning=result.is_warning,
                is_critical=result.is_critical,
                is_exhausted=result.is_exhausted
            ))
        
        # Build tier info
        tier_info = TierInfoResponse(
            tier_id=tier.tier_id,
            tier_name=tier.name.value,
            display_name=tier.display_name,
            limits=limits.to_dict(),
            price_monthly=tier.price_monthly,
            features=tier.features
        )
        
        # Build usage summary
        total_usage = sum(q.current_usage for q in quotas if 'requests' in q.quota_type)
        total_limit = sum(q.limit for q in quotas if 'requests' in q.quota_type)
        
        usage_summary = {
            'total_requests_used': total_usage,
            'total_requests_limit': total_limit,
            'has_warnings': any(q.is_warning for q in quotas),
            'has_critical': any(q.is_critical for q in quotas),
            'has_exhausted': any(q.is_exhausted for q in quotas)
        }
        
        return QuotaDashboardResponse(
            user_id=user_id,
            tier_info=tier_info,
            quotas=quotas,
            usage_summary=usage_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quota status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quota status"
        )


@quota_router.get("/status/{quota_type}")
async def get_specific_quota_status(
    quota_type: str,
    user_id: str = Depends(get_current_user_id),
    quota_tracker: QuotaTracker = Depends(get_quota_tracker_dep),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get status for a specific quota type
    
    Args:
        quota_type: Type of quota (monthly_requests, daily_requests, monthly_bandwidth)
    """
    try:
        # Get user's limits
        limits = await tier_service.get_user_limits(user_id)
        
        if not limits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No limits found for user"
            )
        
        # Map quota type to limit and period
        quota_mapping = {
            'monthly_requests': (QuotaType.REQUESTS, limits.monthly_request_quota, 'month'),
            'daily_requests': (QuotaType.REQUESTS, limits.daily_request_quota, 'day'),
            'monthly_bandwidth': (QuotaType.BANDWIDTH, limits.monthly_bandwidth_quota, 'month')
        }
        
        if quota_type not in quota_mapping:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quota type: {quota_type}"
            )
        
        q_type, limit, period = quota_mapping[quota_type]
        
        if not limit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quota {quota_type} not configured for user"
            )
        
        # Check quota
        result = quota_tracker.check_quota(user_id, q_type, limit, period)
        
        return QuotaStatusResponse(
            quota_type=quota_type,
            current_usage=result.current_usage,
            limit=result.limit,
            remaining=result.remaining,
            percentage_used=result.percentage_used,
            reset_at=result.reset_at.isoformat(),
            is_warning=result.is_warning,
            is_critical=result.is_critical,
            is_exhausted=result.is_exhausted
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quota status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quota status"
        )


@quota_router.get("/usage/history")
async def get_usage_history(
    user_id: str = Depends(get_current_user_id),
    quota_tracker: QuotaTracker = Depends(get_quota_tracker_dep)
):
    """
    Get historical usage data
    
    Returns usage history for the past 6 months.
    """
    try:
        # Get history from quota tracker
        history = quota_tracker.get_quota_history(
            user_id,
            QuotaType.REQUESTS,
            months=6
        )
        
        return {
            'user_id': user_id,
            'history': history,
            'note': 'Historical tracking not yet fully implemented'
        }
        
    except Exception as e:
        logger.error(f"Error getting usage history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage history"
        )


@quota_router.post("/usage/export")
async def export_usage_data(
    format: str = 'json',
    user_id: str = Depends(get_current_user_id),
    quota_tracker: QuotaTracker = Depends(get_quota_tracker_dep),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Export usage data in JSON or CSV format
    
    Args:
        format: Export format ('json' or 'csv')
    """
    try:
        # Get current quota status
        limits = await tier_service.get_user_limits(user_id)
        
        if not limits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No limits found for user"
            )
        
        # Collect all quota data
        export_data = {
            'user_id': user_id,
            'export_date': datetime.now().isoformat(),
            'quotas': []
        }
        
        # Add monthly requests
        if limits.monthly_request_quota:
            result = quota_tracker.check_quota(
                user_id,
                QuotaType.REQUESTS,
                limits.monthly_request_quota,
                'month'
            )
            export_data['quotas'].append({
                'type': 'monthly_requests',
                'current_usage': result.current_usage,
                'limit': result.limit,
                'remaining': result.remaining,
                'percentage_used': result.percentage_used,
                'reset_at': result.reset_at.isoformat()
            })
        
        # Add daily requests
        if limits.daily_request_quota:
            result = quota_tracker.check_quota(
                user_id,
                QuotaType.REQUESTS,
                limits.daily_request_quota,
                'day'
            )
            export_data['quotas'].append({
                'type': 'daily_requests',
                'current_usage': result.current_usage,
                'limit': result.limit,
                'remaining': result.remaining,
                'percentage_used': result.percentage_used,
                'reset_at': result.reset_at.isoformat()
            })
        
        if format == 'csv':
            # Convert to CSV format
            csv_lines = ['Type,Current Usage,Limit,Remaining,Percentage Used,Reset At']
            for quota in export_data['quotas']:
                csv_lines.append(
                    f"{quota['type']},{quota['current_usage']},{quota['limit']},"
                    f"{quota['remaining']},{quota['percentage_used']:.2f},{quota['reset_at']}"
                )
            
            return {
                'format': 'csv',
                'data': '\n'.join(csv_lines)
            }
        else:
            # Return JSON
            return {
                'format': 'json',
                'data': export_data
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting usage data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export usage data"
        )


@quota_router.get("/tier/info")
async def get_tier_info(
    user_id: str = Depends(get_current_user_id),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get current tier information for user
    
    Returns tier details, benefits, and upgrade options.
    """
    try:
        # Get user's tier
        tier = await tier_service.get_user_tier(user_id)
        
        if not tier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tier assigned to user"
            )
        
        # Get all available tiers for upgrade options
        all_tiers = await tier_service.list_tiers(enabled_only=True)
        
        # Filter tiers higher than current (for upgrades)
        upgrade_options = [
            {
                'tier_id': t.tier_id,
                'display_name': t.display_name,
                'price_monthly': t.price_monthly,
                'features': t.features
            }
            for t in all_tiers
            if t.tier_id != tier.tier_id
        ]
        
        return {
            'current_tier': TierInfoResponse(
                tier_id=tier.tier_id,
                tier_name=tier.name.value,
                display_name=tier.display_name,
                limits=tier.limits.to_dict(),
                price_monthly=tier.price_monthly,
                features=tier.features
            ),
            'upgrade_options': upgrade_options
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tier info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tier info"
        )


@quota_router.get("/burst/status")
async def get_burst_status(
    user_id: str = Depends(get_current_user_id),
    tier_service: TierService = Depends(get_tier_service_dep)
):
    """
    Get burst usage status for current user
    
    Returns burst token consumption across different time windows.
    """
    try:
        # Get user's tier and limits
        tier = await tier_service.get_user_tier(user_id)
        
        if not tier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tier assigned to user"
            )
        
        limits = await tier_service.get_user_limits(user_id)
        if not limits:
            limits = tier.limits
        
        # TODO: Get actual burst usage from Redis
        # For now, return structure with placeholder data
        burst_status = {
            'user_id': user_id,
            'burst_limits': {
                'per_minute': limits.burst_per_minute,
                'per_hour': limits.burst_per_hour,
                'per_second': limits.burst_per_second
            },
            'burst_usage': {
                'per_minute': 0,  # TODO: Get from Redis
                'per_hour': 0,
                'per_second': 0
            },
            'note': 'Burst tracking requires rate limiter integration'
        }
        
        return burst_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting burst status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get burst status"
        )
