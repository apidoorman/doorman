"""
Rate Limiting Data Models

This module defines the data structures for the rate limiting system including:
- Rate limit rules
- Quota tracking
- Tier/plan definitions
- Usage counters
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum
from datetime import datetime


# ============================================================================
# ENUMS
# ============================================================================

class RuleType(Enum):
    """Types of rate limit rules"""
    PER_USER = "per_user"
    PER_API = "per_api"
    PER_ENDPOINT = "per_endpoint"
    PER_IP = "per_ip"
    PER_USER_API = "per_user_api"  # Combined: specific user on specific API
    PER_USER_ENDPOINT = "per_user_endpoint"  # Combined: specific user on specific endpoint
    GLOBAL = "global"  # Global rate limit for all requests


class TimeWindow(Enum):
    """Time windows for rate limiting"""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"


class TierName(Enum):
    """Predefined tier names"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class QuotaType(Enum):
    """Types of quotas"""
    REQUESTS = "requests"
    BANDWIDTH = "bandwidth"
    COMPUTE_TIME = "compute_time"


# ============================================================================
# RATE LIMIT RULE MODELS
# ============================================================================

@dataclass
class RateLimitRule:
    """
    Defines a rate limiting rule
    
    Examples:
        # Per-user rule: 100 requests per minute
        RateLimitRule(
            rule_id="rule_001",
            rule_type=RuleType.PER_USER,
            time_window=TimeWindow.MINUTE,
            limit=100,
            burst_allowance=20
        )
        
        # Per-API rule: 1000 requests per hour
        RateLimitRule(
            rule_id="rule_002",
            rule_type=RuleType.PER_API,
            target_identifier="rest:customer",
            time_window=TimeWindow.HOUR,
            limit=1000
        )
    """
    rule_id: str
    rule_type: RuleType
    time_window: TimeWindow
    limit: int  # Maximum requests allowed in time window
    
    # Optional fields
    target_identifier: Optional[str] = None  # User ID, API name, endpoint URI, or IP
    burst_allowance: int = 0  # Additional requests allowed for bursts
    priority: int = 0  # Higher priority rules are checked first
    enabled: bool = True
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'rule_id': self.rule_id,
            'rule_type': self.rule_type.value,
            'time_window': self.time_window.value,
            'limit': self.limit,
            'target_identifier': self.target_identifier,
            'burst_allowance': self.burst_allowance,
            'priority': self.priority,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RateLimitRule':
        """Create from dictionary"""
        return cls(
            rule_id=data['rule_id'],
            rule_type=RuleType(data['rule_type']),
            time_window=TimeWindow(data['time_window']),
            limit=data['limit'],
            target_identifier=data.get('target_identifier'),
            burst_allowance=data.get('burst_allowance', 0),
            priority=data.get('priority', 0),
            enabled=data.get('enabled', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            created_by=data.get('created_by'),
            description=data.get('description')
        )


# ============================================================================
# TIER/PLAN MODELS
# ============================================================================

@dataclass
class TierLimits:
    """Rate limits and quotas for a specific tier"""
    # Rate limits (requests per time window)
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    requests_per_month: Optional[int] = None
    
    # Burst allowances
    burst_per_second: int = 0
    burst_per_minute: int = 0
    burst_per_hour: int = 0
    
    # Quotas
    monthly_request_quota: Optional[int] = None
    daily_request_quota: Optional[int] = None
    monthly_bandwidth_quota: Optional[int] = None  # In bytes
    
    # Throttling configuration
    enable_throttling: bool = False  # If true, queue/delay requests; if false, hard reject (429)
    max_queue_time_ms: int = 5000  # Maximum time to queue a request before rejecting (milliseconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'requests_per_second': self.requests_per_second,
            'requests_per_minute': self.requests_per_minute,
            'requests_per_hour': self.requests_per_hour,
            'requests_per_day': self.requests_per_day,
            'requests_per_month': self.requests_per_month,
            'burst_per_second': self.burst_per_second,
            'burst_per_minute': self.burst_per_minute,
            'burst_per_hour': self.burst_per_hour,
            'monthly_request_quota': self.monthly_request_quota,
            'daily_request_quota': self.daily_request_quota,
            'monthly_bandwidth_quota': self.monthly_bandwidth_quota,
            'enable_throttling': self.enable_throttling,
            'max_queue_time_ms': self.max_queue_time_ms
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TierLimits':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class Tier:
    """
    Defines a tier/plan with associated rate limits and quotas
    
    Examples:
        # Free tier
        Tier(
            tier_id="tier_free",
            name=TierName.FREE,
            display_name="Free Plan",
            limits=TierLimits(
                requests_per_minute=60,
                requests_per_hour=1000,
                daily_request_quota=10000
            )
        )
        
        # Pro tier
        Tier(
            tier_id="tier_pro",
            name=TierName.PRO,
            display_name="Pro Plan",
            limits=TierLimits(
                requests_per_minute=600,
                requests_per_hour=10000,
                burst_per_minute=100,
                monthly_request_quota=1000000
            ),
            price_monthly=49.99
        )
    """
    tier_id: str
    name: TierName
    display_name: str
    limits: TierLimits
    
    # Optional fields
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    features: List[str] = field(default_factory=list)
    is_default: bool = False
    enabled: bool = True
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'tier_id': self.tier_id,
            'name': self.name.value,
            'display_name': self.display_name,
            'limits': self.limits.to_dict(),
            'description': self.description,
            'price_monthly': self.price_monthly,
            'price_yearly': self.price_yearly,
            'features': self.features,
            'is_default': self.is_default,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tier':
        """Create from dictionary"""
        return cls(
            tier_id=data['tier_id'],
            name=TierName(data['name']),
            display_name=data['display_name'],
            limits=TierLimits.from_dict(data['limits']),
            description=data.get('description'),
            price_monthly=data.get('price_monthly'),
            price_yearly=data.get('price_yearly'),
            features=data.get('features', []),
            is_default=data.get('is_default', False),
            enabled=data.get('enabled', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )


@dataclass
class UserTierAssignment:
    """Assigns a user to a tier with optional overrides"""
    user_id: str
    tier_id: str
    
    # Optional overrides (override tier defaults for this specific user)
    override_limits: Optional[TierLimits] = None
    
    # Scheduling
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    
    # Metadata
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'tier_id': self.tier_id,
            'override_limits': self.override_limits.to_dict() if self.override_limits else None,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_until': self.effective_until.isoformat() if self.effective_until else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'assigned_by': self.assigned_by,
            'notes': self.notes
        }


# ============================================================================
# QUOTA TRACKING MODELS
# ============================================================================

@dataclass
class QuotaUsage:
    """
    Tracks current quota usage for a user/API/endpoint
    
    This is stored in Redis for real-time tracking
    """
    key: str  # Redis key (e.g., "quota:user:john_doe:month:2025-12")
    quota_type: QuotaType
    current_usage: int
    limit: int
    reset_at: datetime  # When the quota resets
    
    # Optional fields
    burst_usage: int = 0  # Burst tokens used
    burst_limit: int = 0
    
    @property
    def remaining(self) -> int:
        """Calculate remaining quota"""
        return max(0, self.limit - self.current_usage)
    
    @property
    def percentage_used(self) -> float:
        """Calculate percentage of quota used"""
        if self.limit == 0:
            return 0.0
        return (self.current_usage / self.limit) * 100
    
    @property
    def is_exhausted(self) -> bool:
        """Check if quota is exhausted"""
        return self.current_usage >= self.limit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'key': self.key,
            'quota_type': self.quota_type.value,
            'current_usage': self.current_usage,
            'limit': self.limit,
            'remaining': self.remaining,
            'percentage_used': self.percentage_used,
            'reset_at': self.reset_at.isoformat(),
            'burst_usage': self.burst_usage,
            'burst_limit': self.burst_limit,
            'is_exhausted': self.is_exhausted
        }


@dataclass
class RateLimitCounter:
    """
    Real-time counter for rate limiting (stored in Redis)
    
    Uses sliding window counter algorithm
    """
    key: str  # Redis key (e.g., "ratelimit:user:john_doe:minute:1701504000")
    window_start: int  # Unix timestamp
    window_size: int  # Window size in seconds
    count: int  # Current request count
    limit: int  # Maximum allowed requests
    burst_count: int = 0  # Burst tokens used
    burst_limit: int = 0
    
    @property
    def remaining(self) -> int:
        """Calculate remaining requests"""
        return max(0, self.limit - self.count)
    
    @property
    def is_limited(self) -> bool:
        """Check if rate limit is exceeded"""
        return self.count >= self.limit
    
    @property
    def reset_at(self) -> int:
        """Calculate when the window resets (Unix timestamp)"""
        return self.window_start + self.window_size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'key': self.key,
            'window_start': self.window_start,
            'window_size': self.window_size,
            'count': self.count,
            'limit': self.limit,
            'remaining': self.remaining,
            'reset_at': self.reset_at,
            'burst_count': self.burst_count,
            'burst_limit': self.burst_limit,
            'is_limited': self.is_limited
        }


# ============================================================================
# HISTORICAL TRACKING MODELS
# ============================================================================

@dataclass
class UsageHistoryRecord:
    """
    Historical usage record for analytics
    
    Stored in time-series database or MongoDB
    """
    timestamp: datetime
    user_id: Optional[str] = None
    api_name: Optional[str] = None
    endpoint_uri: Optional[str] = None
    ip_address: Optional[str] = None
    
    # Metrics
    request_count: int = 0
    blocked_count: int = 0  # Requests blocked by rate limit
    burst_used: int = 0
    
    # Aggregation period
    period: str = "minute"  # minute, hour, day
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'api_name': self.api_name,
            'endpoint_uri': self.endpoint_uri,
            'ip_address': self.ip_address,
            'request_count': self.request_count,
            'blocked_count': self.blocked_count,
            'burst_used': self.burst_used,
            'period': self.period
        }


# ============================================================================
# RESPONSE MODELS
# ============================================================================

@dataclass
class RateLimitInfo:
    """
    Information about current rate limit status
    
    Returned in API responses and headers
    """
    limit: int
    remaining: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry (when limited)
    
    # Additional info
    burst_limit: int = 0
    burst_remaining: int = 0
    tier: Optional[str] = None
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers"""
        headers = {
            'X-RateLimit-Limit': str(self.limit),
            'X-RateLimit-Remaining': str(self.remaining),
            'X-RateLimit-Reset': str(self.reset_at)
        }
        
        if self.retry_after is not None:
            headers['X-RateLimit-Retry-After'] = str(self.retry_after)
            headers['Retry-After'] = str(self.retry_after)
        
        if self.burst_limit > 0:
            headers['X-RateLimit-Burst-Limit'] = str(self.burst_limit)
            headers['X-RateLimit-Burst-Remaining'] = str(self.burst_remaining)
        
        return headers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'limit': self.limit,
            'remaining': self.remaining,
            'reset_at': self.reset_at,
            'retry_after': self.retry_after,
            'burst_limit': self.burst_limit,
            'burst_remaining': self.burst_remaining,
            'tier': self.tier
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_time_window_seconds(window: TimeWindow) -> int:
    """Convert time window enum to seconds"""
    mapping = {
        TimeWindow.SECOND: 1,
        TimeWindow.MINUTE: 60,
        TimeWindow.HOUR: 3600,
        TimeWindow.DAY: 86400,
        TimeWindow.MONTH: 2592000  # 30 days
    }
    return mapping[window]


def generate_redis_key(
    rule_type: RuleType,
    identifier: str,
    window: TimeWindow,
    window_start: int
) -> str:
    """
    Generate Redis key for rate limit counter
    
    Examples:
        generate_redis_key(RuleType.PER_USER, "john_doe", TimeWindow.MINUTE, 1701504000)
        # Returns: "ratelimit:user:john_doe:minute:1701504000"
    """
    type_prefix = rule_type.value.replace('per_', '')
    window_name = window.value
    return f"ratelimit:{type_prefix}:{identifier}:{window_name}:{window_start}"


def generate_quota_key(
    user_id: str,
    quota_type: QuotaType,
    period: str
) -> str:
    """
    Generate Redis key for quota tracking
    
    Examples:
        generate_quota_key("john_doe", QuotaType.REQUESTS, "2025-12")
        # Returns: "quota:user:john_doe:requests:month:2025-12"
    """
    return f"quota:user:{user_id}:{quota_type.value}:month:{period}"
