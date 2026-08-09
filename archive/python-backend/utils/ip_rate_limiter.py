"""
IP-Based Rate Limiter

Handles IP extraction, IP-based rate limiting, whitelisting/blacklisting,
and IP reputation scoring.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from fastapi import Request

from utils.rate_limiter import RateLimiter, RateLimitResult
from utils.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class IPInfo:
    """Information about an IP address"""

    ip: str
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    reputation_score: int = 100  # 0-100, lower is worse
    request_count: int = 0
    last_seen: datetime | None = None
    countries: set[str] = None

    def __post_init__(self):
        if self.countries is None:
            self.countries = set()


class IPRateLimiter:
    """
    IP-based rate limiting with whitelist/blacklist and reputation scoring
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize IP rate limiter"""
        self.redis = redis_client or get_redis_client()
        self.rate_limiter = RateLimiter(redis_client)

        # Default IP rate limits (can be overridden per IP)
        self.default_ip_limit_per_minute = 60
        self.default_ip_limit_per_hour = 1000

        # Reputation thresholds
        self.suspicious_threshold = 50  # Below this is suspicious
        self.ban_threshold = 20  # Below this gets banned

    def extract_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request, handling proxy headers

        Priority order:
        1. X-Forwarded-For (first IP in chain)
        2. X-Real-IP
        3. request.client.host
        """
        # Check X-Forwarded-For (most common proxy header)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(',')[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()

        # Fallback to direct connection IP
        if request.client and request.client.host:
            return request.client.host

        return 'unknown'

    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        try:
            return bool(self.redis.sismember('ip:whitelist', ip))
        except Exception as e:
            logger.error(f'Error checking whitelist: {e}')
            return False

    def is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted"""
        try:
            return bool(self.redis.sismember('ip:blacklist', ip))
        except Exception as e:
            logger.error(f'Error checking blacklist: {e}')
            return False

    def add_to_whitelist(self, ip: str) -> bool:
        """Add IP to whitelist"""
        try:
            self.redis.sadd('ip:whitelist', ip)
            logger.info(f'Added IP to whitelist: {ip}')
            return True
        except Exception as e:
            logger.error(f'Error adding to whitelist: {e}')
            return False

    def add_to_blacklist(self, ip: str, duration_seconds: int | None = None) -> bool:
        """
        Add IP to blacklist

        Args:
            ip: IP address to blacklist
            duration_seconds: Optional duration for temporary ban
        """
        try:
            self.redis.sadd('ip:blacklist', ip)

            if duration_seconds:
                # Set expiration for temporary ban
                ban_key = f'ip:ban:{ip}'
                self.redis.setex(ban_key, duration_seconds, '1')
                logger.info(f'Temporarily banned IP for {duration_seconds}s: {ip}')
            else:
                logger.info(f'Permanently blacklisted IP: {ip}')

            return True
        except Exception as e:
            logger.error(f'Error adding to blacklist: {e}')
            return False

    def remove_from_whitelist(self, ip: str) -> bool:
        """Remove IP from whitelist"""
        try:
            self.redis.srem('ip:whitelist', ip)
            logger.info(f'Removed IP from whitelist: {ip}')
            return True
        except Exception as e:
            logger.error(f'Error removing from whitelist: {e}')
            return False

    def remove_from_blacklist(self, ip: str) -> bool:
        """Remove IP from blacklist"""
        try:
            self.redis.srem('ip:blacklist', ip)
            ban_key = f'ip:ban:{ip}'
            self.redis.delete(ban_key)
            logger.info(f'Removed IP from blacklist: {ip}')
            return True
        except Exception as e:
            logger.error(f'Error removing from blacklist: {e}')
            return False

    def get_reputation_score(self, ip: str) -> int:
        """
        Get reputation score for IP (0-100)

        Lower scores indicate worse reputation.
        """
        try:
            score_key = f'ip:reputation:{ip}'
            score = self.redis.get(score_key)
            return int(score) if score else 100
        except Exception as e:
            logger.error(f'Error getting reputation score: {e}')
            return 100

    def update_reputation_score(self, ip: str, delta: int) -> int:
        """
        Update reputation score for IP

        Args:
            ip: IP address
            delta: Change in score (positive or negative)

        Returns:
            New reputation score
        """
        try:
            score_key = f'ip:reputation:{ip}'
            current_score = self.get_reputation_score(ip)
            new_score = max(0, min(100, current_score + delta))

            self.redis.setex(score_key, 86400 * 7, str(new_score))  # 7 day TTL

            # Auto-ban if score too low
            if new_score <= self.ban_threshold:
                self.add_to_blacklist(ip, duration_seconds=3600)  # 1 hour ban
                logger.warning(f'Auto-banned IP due to low reputation: {ip} (score: {new_score})')

            return new_score
        except Exception as e:
            logger.error(f'Error updating reputation score: {e}')
            return 100

    def track_request(self, ip: str) -> None:
        """Track request from IP for analytics"""
        try:
            # Increment request counter
            counter_key = f'ip:requests:{ip}'
            self.redis.incr(counter_key)
            self.redis.expire(counter_key, 86400)  # 24 hour window

            # Update last seen
            last_seen_key = f'ip:last_seen:{ip}'
            self.redis.set(last_seen_key, datetime.now().isoformat())
            self.redis.expire(last_seen_key, 86400 * 7)  # 7 days

        except Exception as e:
            logger.error(f'Error tracking request: {e}')

    def get_ip_info(self, ip: str) -> IPInfo:
        """Get comprehensive information about an IP"""
        try:
            request_count_key = f'ip:requests:{ip}'
            request_count = int(self.redis.get(request_count_key) or 0)

            last_seen_key = f'ip:last_seen:{ip}'
            last_seen_str = self.redis.get(last_seen_key)
            last_seen = datetime.fromisoformat(last_seen_str) if last_seen_str else None

            return IPInfo(
                ip=ip,
                is_whitelisted=self.is_whitelisted(ip),
                is_blacklisted=self.is_blacklisted(ip),
                reputation_score=self.get_reputation_score(ip),
                request_count=request_count,
                last_seen=last_seen,
            )
        except Exception as e:
            logger.error(f'Error getting IP info: {e}')
            return IPInfo(ip=ip)

    def check_ip_rate_limit(
        self, ip: str, limit_per_minute: int | None = None, limit_per_hour: int | None = None
    ) -> RateLimitResult:
        """
        Check rate limit for specific IP

        Args:
            ip: IP address
            limit_per_minute: Override default per-minute limit
            limit_per_hour: Override default per-hour limit

        Returns:
            RateLimitResult indicating if request is allowed
        """
        # Check whitelist (always allow)
        if self.is_whitelisted(ip):
            return RateLimitResult(
                allowed=True, limit=999999, remaining=999999, reset_at=int(time.time()) + 60
            )

        # Check blacklist (always deny)
        if self.is_blacklisted(ip):
            return RateLimitResult(
                allowed=False, limit=0, remaining=0, reset_at=int(time.time()) + 60
            )

        # Check reputation score
        reputation = self.get_reputation_score(ip)
        if reputation < self.suspicious_threshold:
            # Reduce limits for suspicious IPs
            limit_per_minute = int((limit_per_minute or self.default_ip_limit_per_minute) * 0.5)
            limit_per_hour = int((limit_per_hour or self.default_ip_limit_per_hour) * 0.5)
            logger.warning(f'Reduced limits for suspicious IP: {ip} (reputation: {reputation})')

        # Use defaults if not specified
        limit_per_minute = limit_per_minute or self.default_ip_limit_per_minute
        limit_per_hour = limit_per_hour or self.default_ip_limit_per_hour

        # Check per-minute limit
        minute_key = f'ip:limit:minute:{ip}'
        minute_count = int(self.redis.get(minute_key) or 0)

        if minute_count >= limit_per_minute:
            # Decrease reputation for rate limit violations
            self.update_reputation_score(ip, -5)
            return RateLimitResult(
                allowed=False, limit=limit_per_minute, remaining=0, reset_at=int(time.time()) + 60
            )

        # Check per-hour limit
        hour_key = f'ip:limit:hour:{ip}'
        hour_count = int(self.redis.get(hour_key) or 0)

        if hour_count >= limit_per_hour:
            self.update_reputation_score(ip, -5)
            return RateLimitResult(
                allowed=False, limit=limit_per_hour, remaining=0, reset_at=int(time.time()) + 3600
            )

        # Increment counters
        pipe = self.redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        pipe.execute()

        # Track request
        self.track_request(ip)

        return RateLimitResult(
            allowed=True,
            limit=limit_per_minute,
            remaining=limit_per_minute - minute_count - 1,
            reset_at=int(time.time()) + 60,
        )

    def get_top_ips(self, limit: int = 10) -> list[tuple]:
        """
        Get top IPs by request volume

        Returns:
            List of (ip, request_count) tuples
        """
        try:
            # Scan for all IP request counters
            pattern = 'ip:requests:*'
            keys = []

            cursor = 0
            while True:
                cursor, batch = self.redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            # Get counts for each IP
            ip_counts = []
            for key in keys[:1000]:  # Limit to prevent overwhelming
                ip = key.replace('ip:requests:', '')
                count = int(self.redis.get(key) or 0)
                ip_counts.append((ip, count))

            # Sort by count and return top N
            ip_counts.sort(key=lambda x: x[1], reverse=True)
            return ip_counts[:limit]

        except Exception as e:
            logger.error(f'Error getting top IPs: {e}')
            return []

    def detect_suspicious_activity(self, ip: str) -> bool:
        """
        Detect suspicious activity patterns

        Returns:
            True if suspicious activity detected
        """
        try:
            # Check request rate
            minute_key = f'ip:limit:minute:{ip}'
            minute_count = int(self.redis.get(minute_key) or 0)

            # Suspicious if > 80% of limit
            if minute_count > self.default_ip_limit_per_minute * 0.8:
                logger.warning(f'Suspicious activity detected for IP: {ip} (high request rate)')
                self.update_reputation_score(ip, -10)
                return True

            # Check reputation
            reputation = self.get_reputation_score(ip)
            if reputation < self.suspicious_threshold:
                return True

            return False

        except Exception as e:
            logger.error(f'Error detecting suspicious activity: {e}')
            return False


# Global instance
_ip_rate_limiter: IPRateLimiter | None = None


def get_ip_rate_limiter() -> IPRateLimiter:
    """Get or create global IP rate limiter instance"""
    global _ip_rate_limiter
    if _ip_rate_limiter is None:
        _ip_rate_limiter = IPRateLimiter()
    return _ip_rate_limiter
