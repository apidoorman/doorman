"""
Analytics aggregation utilities.

Provides multi-level time-series aggregation (5-minute, hourly, daily)
for efficient historical queries without scanning all minute-level data.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from models.analytics_models import (
    AggregatedMetrics,
    AggregationLevel,
    EnhancedMinuteBucket,
    PercentileMetrics,
)


class AnalyticsAggregator:
    """
    Multi-level time-series aggregator.

    Aggregates minute-level buckets into:
    - 5-minute buckets (for 24-hour views)
    - Hourly buckets (for 7-day views)
    - Daily buckets (for 30-day+ views)

    Retention policy:
    - Minute-level: 24 hours
    - 5-minute level: 7 days
    - Hourly level: 30 days
    - Daily level: 90 days
    """

    def __init__(self):
        self.five_minute_buckets: deque[AggregatedMetrics] = deque(
            maxlen=2016
        )  # 7 days * 288 buckets/day
        self.hourly_buckets: deque[AggregatedMetrics] = deque(maxlen=720)  # 30 days * 24 hours
        self.daily_buckets: deque[AggregatedMetrics] = deque(maxlen=90)  # 90 days

        self._last_5min_aggregation = 0
        self._last_hourly_aggregation = 0
        self._last_daily_aggregation = 0

    @staticmethod
    def _floor_timestamp(ts: int, seconds: int) -> int:
        """Floor timestamp to nearest interval."""
        return (ts // seconds) * seconds

    def aggregate_to_5minute(self, minute_buckets: list[EnhancedMinuteBucket]) -> None:
        """
        Aggregate minute-level buckets into 5-minute buckets.

        Should be called every 5 minutes with the last 5 minutes of data.
        """
        if not minute_buckets:
            return

        # Group by 5-minute intervals
        five_min_groups: dict[int, list[EnhancedMinuteBucket]] = defaultdict(list)
        for bucket in minute_buckets:
            five_min_start = self._floor_timestamp(bucket.start_ts, 300)  # 300 seconds = 5 minutes
            five_min_groups[five_min_start].append(bucket)

        # Create aggregated buckets
        for five_min_start, buckets in five_min_groups.items():
            agg = self._aggregate_buckets(
                buckets,
                start_ts=five_min_start,
                end_ts=five_min_start + 300,
                level=AggregationLevel.FIVE_MINUTE,
            )
            self.five_minute_buckets.append(agg)

        self._last_5min_aggregation = int(time.time())

    def aggregate_to_hourly(
        self, five_minute_buckets: list[AggregatedMetrics] | None = None
    ) -> None:
        """
        Aggregate 5-minute buckets into hourly buckets.

        Should be called every hour.
        """
        # Use provided buckets or last 12 from deque (1 hour = 12 * 5-minute buckets)
        if five_minute_buckets is None:
            five_minute_buckets = list(self.five_minute_buckets)[-12:]

        if not five_minute_buckets:
            return

        # Group by hour
        hourly_groups: dict[int, list[AggregatedMetrics]] = defaultdict(list)
        for bucket in five_minute_buckets:
            hour_start = self._floor_timestamp(bucket.start_ts, 3600)  # 3600 seconds = 1 hour
            hourly_groups[hour_start].append(bucket)

        # Create aggregated buckets
        for hour_start, buckets in hourly_groups.items():
            agg = self._aggregate_aggregated_buckets(
                buckets, start_ts=hour_start, end_ts=hour_start + 3600, level=AggregationLevel.HOUR
            )
            self.hourly_buckets.append(agg)

        self._last_hourly_aggregation = int(time.time())

    def aggregate_to_daily(self, hourly_buckets: list[AggregatedMetrics] | None = None) -> None:
        """
        Aggregate hourly buckets into daily buckets.

        Should be called once per day.
        """
        # Use provided buckets or last 24 from deque (1 day = 24 hourly buckets)
        if hourly_buckets is None:
            hourly_buckets = list(self.hourly_buckets)[-24:]

        if not hourly_buckets:
            return

        # Group by day
        daily_groups: dict[int, list[AggregatedMetrics]] = defaultdict(list)
        for bucket in hourly_buckets:
            day_start = self._floor_timestamp(bucket.start_ts, 86400)  # 86400 seconds = 1 day
            daily_groups[day_start].append(bucket)

        # Create aggregated buckets
        for day_start, buckets in daily_groups.items():
            agg = self._aggregate_aggregated_buckets(
                buckets, start_ts=day_start, end_ts=day_start + 86400, level=AggregationLevel.DAY
            )
            self.daily_buckets.append(agg)

        self._last_daily_aggregation = int(time.time())

    def _aggregate_buckets(
        self,
        buckets: list[EnhancedMinuteBucket],
        start_ts: int,
        end_ts: int,
        level: AggregationLevel,
    ) -> AggregatedMetrics:
        """Aggregate minute-level buckets into a single aggregated bucket."""
        total_count = sum(b.count for b in buckets)
        total_errors = sum(b.error_count for b in buckets)
        total_ms = sum(b.total_ms for b in buckets)
        total_bytes_in = sum(b.bytes_in for b in buckets)
        total_bytes_out = sum(b.bytes_out for b in buckets)

        # Merge status counts
        status_counts: dict[int, int] = defaultdict(int)
        for bucket in buckets:
            for status, count in bucket.status_counts.items():
                status_counts[status] += count

        # Merge API counts
        api_counts: dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for api, count in bucket.api_counts.items():
                api_counts[api] += count

        # Collect all latencies for percentile calculation
        all_latencies: list[float] = []
        for bucket in buckets:
            all_latencies.extend(list(bucket.latencies))

        percentiles = PercentileMetrics.calculate(all_latencies) if all_latencies else None

        # Count unique users across all buckets
        unique_users = set()
        for bucket in buckets:
            unique_users.update(bucket.unique_users)

        return AggregatedMetrics(
            start_ts=start_ts,
            end_ts=end_ts,
            level=level,
            count=total_count,
            error_count=total_errors,
            total_ms=total_ms,
            bytes_in=total_bytes_in,
            bytes_out=total_bytes_out,
            unique_users=len(unique_users),
            status_counts=dict(status_counts),
            api_counts=dict(api_counts),
            percentiles=percentiles,
        )

    def _aggregate_aggregated_buckets(
        self, buckets: list[AggregatedMetrics], start_ts: int, end_ts: int, level: AggregationLevel
    ) -> AggregatedMetrics:
        """Aggregate already-aggregated buckets (5-min → hourly, hourly → daily)."""
        total_count = sum(b.count for b in buckets)
        total_errors = sum(b.error_count for b in buckets)
        total_ms = sum(b.total_ms for b in buckets)
        total_bytes_in = sum(b.bytes_in for b in buckets)
        total_bytes_out = sum(b.bytes_out for b in buckets)

        # Merge status counts
        status_counts: dict[int, int] = defaultdict(int)
        for bucket in buckets:
            for status, count in bucket.status_counts.items():
                status_counts[status] += count

        # Merge API counts
        api_counts: dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for api, count in bucket.api_counts.items():
                api_counts[api] += count

        # For percentiles, we'll use weighted average (not perfect, but acceptable)
        # Ideally, we'd re-calculate from raw latencies, but those aren't stored in aggregated buckets
        weighted_percentiles = self._weighted_average_percentiles(buckets)

        # Unique users: sum (may overcount, but acceptable for aggregated data)
        unique_users = sum(b.unique_users for b in buckets)

        return AggregatedMetrics(
            start_ts=start_ts,
            end_ts=end_ts,
            level=level,
            count=total_count,
            error_count=total_errors,
            total_ms=total_ms,
            bytes_in=total_bytes_in,
            bytes_out=total_bytes_out,
            unique_users=unique_users,
            status_counts=dict(status_counts),
            api_counts=dict(api_counts),
            percentiles=weighted_percentiles,
        )

    def _weighted_average_percentiles(
        self, buckets: list[AggregatedMetrics]
    ) -> PercentileMetrics | None:
        """Calculate weighted average of percentiles from aggregated buckets."""
        if not buckets:
            return None

        total_count = sum(b.count for b in buckets if b.count > 0)
        if total_count == 0:
            return None

        # Weighted average of each percentile
        p50_sum = sum(b.percentiles.p50 * b.count for b in buckets if b.percentiles and b.count > 0)
        p75_sum = sum(b.percentiles.p75 * b.count for b in buckets if b.percentiles and b.count > 0)
        p90_sum = sum(b.percentiles.p90 * b.count for b in buckets if b.percentiles and b.count > 0)
        p95_sum = sum(b.percentiles.p95 * b.count for b in buckets if b.percentiles and b.count > 0)
        p99_sum = sum(b.percentiles.p99 * b.count for b in buckets if b.percentiles and b.count > 0)

        min_val = min(b.percentiles.min for b in buckets if b.percentiles)
        max_val = max(b.percentiles.max for b in buckets if b.percentiles)

        return PercentileMetrics(
            p50=p50_sum / total_count,
            p75=p75_sum / total_count,
            p90=p90_sum / total_count,
            p95=p95_sum / total_count,
            p99=p99_sum / total_count,
            min=min_val,
            max=max_val,
        )

    def get_buckets_for_range(
        self, start_ts: int, end_ts: int, preferred_level: AggregationLevel | None = None
    ) -> list[AggregatedMetrics]:
        """
        Get the most appropriate aggregation level for a time range.

        Automatically selects:
        - 5-minute buckets for ranges < 24 hours
        - Hourly buckets for ranges < 7 days
        - Daily buckets for ranges >= 7 days
        """
        range_seconds = end_ts - start_ts

        # Determine best aggregation level
        if preferred_level:
            level = preferred_level
        elif range_seconds <= 86400:  # <= 24 hours
            level = AggregationLevel.FIVE_MINUTE
        elif range_seconds <= 604800:  # <= 7 days
            level = AggregationLevel.HOUR
        else:
            level = AggregationLevel.DAY

        # Select appropriate bucket collection
        if level == AggregationLevel.FIVE_MINUTE:
            buckets = list(self.five_minute_buckets)
        elif level == AggregationLevel.HOUR:
            buckets = list(self.hourly_buckets)
        else:
            buckets = list(self.daily_buckets)

        # Filter to time range
        return [b for b in buckets if b.start_ts >= start_ts and b.end_ts <= end_ts]

    def should_aggregate(self) -> dict[str, bool]:
        """Check if any aggregation jobs should run."""
        now = int(time.time())

        return {
            '5minute': (now - self._last_5min_aggregation) >= 300,  # Every 5 minutes
            'hourly': (now - self._last_hourly_aggregation) >= 3600,  # Every hour
            'daily': (now - self._last_daily_aggregation) >= 86400,  # Every day
        }

    def to_dict(self) -> dict:
        """Serialize aggregator state for persistence."""
        return {
            'five_minute_buckets': [b.to_dict() for b in self.five_minute_buckets],
            'hourly_buckets': [b.to_dict() for b in self.hourly_buckets],
            'daily_buckets': [b.to_dict() for b in self.daily_buckets],
            'last_5min_aggregation': self._last_5min_aggregation,
            'last_hourly_aggregation': self._last_hourly_aggregation,
            'last_daily_aggregation': self._last_daily_aggregation,
        }

    def load_dict(self, data: dict) -> None:
        """Load aggregator state from persistence."""
        # Note: This is a simplified version. Full implementation would
        # reconstruct AggregatedMetrics objects from dictionaries
        self._last_5min_aggregation = data.get('last_5min_aggregation', 0)
        self._last_hourly_aggregation = data.get('last_hourly_aggregation', 0)
        self._last_daily_aggregation = data.get('last_daily_aggregation', 0)


# Global aggregator instance
analytics_aggregator = AnalyticsAggregator()
