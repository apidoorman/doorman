"""
Geographic IP Lookup

Handles IP geolocation, country-based rate limiting, and geographic analytics.
Uses MaxMind GeoLite2 database (free) or can be extended to use commercial services.
"""

import logging
from dataclasses import dataclass

from utils.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class GeoLocation:
    """Geographic location information"""

    ip: str
    country_code: str | None = None
    country_name: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class GeoLookup:
    """
    Geographic IP lookup and country-based rate limiting

    Note: This is a simplified implementation. In production, integrate with:
    - MaxMind GeoLite2 (free): https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
    - MaxMind GeoIP2 (paid): More accurate
    - IP2Location: Alternative service
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize geo lookup"""
        self.redis = redis_client or get_redis_client()

        # Cache TTL for geo lookups (24 hours)
        self.cache_ttl = 86400

    def lookup_ip(self, ip: str) -> GeoLocation:
        """
        Lookup geographic information for IP

        In production, this would use MaxMind GeoIP2 or similar service.
        For now, returns cached data or placeholder.
        """
        try:
            # Check cache first
            cache_key = f'geo:cache:{ip}'
            cached = self.redis.hgetall(cache_key)

            if cached:
                return GeoLocation(
                    ip=ip,
                    country_code=cached.get('country_code'),
                    country_name=cached.get('country_name'),
                    region=cached.get('region'),
                    city=cached.get('city'),
                    latitude=float(cached['latitude']) if cached.get('latitude') else None,
                    longitude=float(cached['longitude']) if cached.get('longitude') else None,
                    timezone=cached.get('timezone'),
                )

            # TODO: Integrate with MaxMind GeoIP2
            # Example integration:
            # import geoip2.database
            # reader = geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
            # response = reader.city(ip)
            # country_code = response.country.iso_code
            # country_name = response.country.name
            # city = response.city.name
            # latitude = response.location.latitude
            # longitude = response.location.longitude

            # For now, return placeholder with unknown location
            geo = GeoLocation(ip=ip, country_code='UNKNOWN')

            # Cache the result
            self._cache_geo_data(ip, geo)

            return geo

        except Exception as e:
            logger.error(f'Error looking up IP geolocation: {e}')
            return GeoLocation(ip=ip)

    def _cache_geo_data(self, ip: str, geo: GeoLocation) -> None:
        """Cache geo data in Redis"""
        try:
            cache_key = f'geo:cache:{ip}'
            data = {
                'country_code': geo.country_code or '',
                'country_name': geo.country_name or '',
                'region': geo.region or '',
                'city': geo.city or '',
                'latitude': str(geo.latitude) if geo.latitude else '',
                'longitude': str(geo.longitude) if geo.longitude else '',
                'timezone': geo.timezone or '',
            }
            self.redis.hmset(cache_key, data)
            self.redis.expire(cache_key, self.cache_ttl)
        except Exception as e:
            logger.error(f'Error caching geo data: {e}')

    def is_country_blocked(self, country_code: str) -> bool:
        """Check if country is blocked"""
        try:
            return bool(self.redis.sismember('geo:blocked_countries', country_code))
        except Exception as e:
            logger.error(f'Error checking blocked country: {e}')
            return False

    def is_country_allowed(self, country_code: str) -> bool:
        """
        Check if country is in allowlist

        If allowlist is empty, all countries are allowed.
        If allowlist has entries, only those countries are allowed.
        """
        try:
            # Get allowlist
            allowed = self.redis.smembers('geo:allowed_countries')

            # If no allowlist, all countries allowed
            if not allowed:
                return True

            # Check if country in allowlist
            return country_code in allowed
        except Exception as e:
            logger.error(f'Error checking allowed country: {e}')
            return True

    def block_country(self, country_code: str) -> bool:
        """Add country to blocklist"""
        try:
            self.redis.sadd('geo:blocked_countries', country_code)
            logger.info(f'Blocked country: {country_code}')
            return True
        except Exception as e:
            logger.error(f'Error blocking country: {e}')
            return False

    def unblock_country(self, country_code: str) -> bool:
        """Remove country from blocklist"""
        try:
            self.redis.srem('geo:blocked_countries', country_code)
            logger.info(f'Unblocked country: {country_code}')
            return True
        except Exception as e:
            logger.error(f'Error unblocking country: {e}')
            return False

    def add_to_allowlist(self, country_code: str) -> bool:
        """Add country to allowlist"""
        try:
            self.redis.sadd('geo:allowed_countries', country_code)
            logger.info(f'Added country to allowlist: {country_code}')
            return True
        except Exception as e:
            logger.error(f'Error adding to allowlist: {e}')
            return False

    def remove_from_allowlist(self, country_code: str) -> bool:
        """Remove country from allowlist"""
        try:
            self.redis.srem('geo:allowed_countries', country_code)
            logger.info(f'Removed country from allowlist: {country_code}')
            return True
        except Exception as e:
            logger.error(f'Error removing from allowlist: {e}')
            return False

    def get_country_rate_limit(self, country_code: str) -> int | None:
        """
        Get custom rate limit for country

        Returns None if no custom limit set.
        """
        try:
            limit_key = f'geo:rate_limit:{country_code}'
            limit = self.redis.get(limit_key)
            return int(limit) if limit else None
        except Exception as e:
            logger.error(f'Error getting country rate limit: {e}')
            return None

    def set_country_rate_limit(self, country_code: str, limit: int) -> bool:
        """Set custom rate limit for country"""
        try:
            limit_key = f'geo:rate_limit:{country_code}'
            self.redis.set(limit_key, str(limit))
            logger.info(f'Set rate limit for {country_code}: {limit}')
            return True
        except Exception as e:
            logger.error(f'Error setting country rate limit: {e}')
            return False

    def check_geographic_access(self, ip: str) -> tuple[bool, str | None]:
        """
        Check if IP's geographic location is allowed

        Returns:
            (allowed, reason) tuple
        """
        try:
            geo = self.lookup_ip(ip)

            if not geo.country_code or geo.country_code == 'UNKNOWN':
                # Allow unknown locations by default
                return True, None

            # Check blocklist
            if self.is_country_blocked(geo.country_code):
                return False, f'Country {geo.country_code} is blocked'

            # Check allowlist
            if not self.is_country_allowed(geo.country_code):
                return False, f'Country {geo.country_code} is not in allowlist'

            return True, None

        except Exception as e:
            logger.error(f'Error checking geographic access: {e}')
            # Allow by default on error
            return True, None

    def track_country_request(self, country_code: str) -> None:
        """Track request from country for analytics"""
        try:
            counter_key = f'geo:requests:{country_code}'
            self.redis.incr(counter_key)
            self.redis.expire(counter_key, 86400)  # 24 hour window
        except Exception as e:
            logger.error(f'Error tracking country request: {e}')

    def get_geographic_distribution(self) -> list[tuple]:
        """
        Get request distribution by country

        Returns:
            List of (country_code, request_count) tuples
        """
        try:
            pattern = 'geo:requests:*'
            keys = []

            cursor = 0
            while True:
                cursor, batch = self.redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            # Get counts for each country
            country_counts = []
            for key in keys:
                country_code = key.replace('geo:requests:', '')
                count = int(self.redis.get(key) or 0)
                country_counts.append((country_code, count))

            # Sort by count
            country_counts.sort(key=lambda x: x[1], reverse=True)
            return country_counts

        except Exception as e:
            logger.error(f'Error getting geographic distribution: {e}')
            return []

    def get_blocked_countries(self) -> set[str]:
        """Get list of blocked countries"""
        try:
            return self.redis.smembers('geo:blocked_countries')
        except Exception as e:
            logger.error(f'Error getting blocked countries: {e}')
            return set()

    def get_allowed_countries(self) -> set[str]:
        """Get list of allowed countries"""
        try:
            return self.redis.smembers('geo:allowed_countries')
        except Exception as e:
            logger.error(f'Error getting allowed countries: {e}')
            return set()


# Global instance
_geo_lookup: GeoLookup | None = None


def get_geo_lookup() -> GeoLookup:
    """Get or create global geo lookup instance"""
    global _geo_lookup
    if _geo_lookup is None:
        _geo_lookup = GeoLookup()
    return _geo_lookup
