"""
Background scheduler for analytics aggregation jobs.

Runs periodic tasks to:
- Aggregate minute-level data into 5-minute buckets
- Aggregate 5-minute data into hourly buckets
- Aggregate hourly data into daily buckets
- Clean up old data beyond retention policy
- Persist metrics to disk
"""

import asyncio
import logging
import time

from utils.analytics_aggregator import analytics_aggregator
from utils.enhanced_metrics_util import enhanced_metrics_store

logger = logging.getLogger('doorman.analytics')


class AnalyticsScheduler:
    """
    Background task scheduler for analytics aggregation.

    Runs aggregation jobs at appropriate intervals:
    - 5-minute aggregation: Every 5 minutes
    - Hourly aggregation: Every hour
    - Daily aggregation: Once per day
    - Persistence: Every 5 minutes
    - Cleanup: Once per day
    """

    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None
        self._last_5min = 0
        self._last_hourly = 0
        self._last_daily = 0
        self._last_persist = 0
        self._last_cleanup = 0

    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning('Analytics scheduler already running')
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info('Analytics scheduler started')

    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return

        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info('Analytics scheduler stopped')

    async def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                await self._check_and_run_jobs()
                # Check every minute
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f'Error in analytics scheduler: {str(e)}', exc_info=True)
                await asyncio.sleep(60)

    async def _check_and_run_jobs(self):
        """Check if any jobs should run and execute them."""
        now = int(time.time())

        # 5-minute aggregation (every 5 minutes)
        if now - self._last_5min >= 300:
            await self._run_5minute_aggregation()
            self._last_5min = now

        # Hourly aggregation (every hour)
        if now - self._last_hourly >= 3600:
            await self._run_hourly_aggregation()
            self._last_hourly = now

        # Daily aggregation (once per day)
        if now - self._last_daily >= 86400:
            await self._run_daily_aggregation()
            self._last_daily = now

        # Persist metrics (every 5 minutes)
        if now - self._last_persist >= 300:
            await self._persist_metrics()
            self._last_persist = now

        # Cleanup old data (once per day)
        if now - self._last_cleanup >= 86400:
            await self._cleanup_old_data()
            self._last_cleanup = now

    async def _run_5minute_aggregation(self):
        """Aggregate last 5 minutes of data into 5-minute buckets."""
        try:
            logger.info('Running 5-minute aggregation')
            start_time = time.time()

            # Get last 5 minutes of buckets
            minute_buckets = list(enhanced_metrics_store._buckets)[-5:]

            if minute_buckets:
                analytics_aggregator.aggregate_to_5minute(minute_buckets)

                duration_ms = (time.time() - start_time) * 1000
                logger.info(f'5-minute aggregation completed in {duration_ms:.2f}ms')
            else:
                logger.debug('No buckets to aggregate (5-minute)')

        except Exception as e:
            logger.error(f'Failed to run 5-minute aggregation: {str(e)}', exc_info=True)

    async def _run_hourly_aggregation(self):
        """Aggregate last hour of 5-minute data into hourly buckets."""
        try:
            logger.info('Running hourly aggregation')
            start_time = time.time()

            analytics_aggregator.aggregate_to_hourly()

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f'Hourly aggregation completed in {duration_ms:.2f}ms')

        except Exception as e:
            logger.error(f'Failed to run hourly aggregation: {str(e)}', exc_info=True)

    async def _run_daily_aggregation(self):
        """Aggregate last day of hourly data into daily buckets."""
        try:
            logger.info('Running daily aggregation')
            start_time = time.time()

            analytics_aggregator.aggregate_to_daily()

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f'Daily aggregation completed in {duration_ms:.2f}ms')

        except Exception as e:
            logger.error(f'Failed to run daily aggregation: {str(e)}', exc_info=True)

    async def _persist_metrics(self):
        """Save metrics to disk for persistence."""
        try:
            logger.debug('Persisting metrics to disk')
            start_time = time.time()

            # Save minute-level metrics
            enhanced_metrics_store.save_to_file('platform-logs/enhanced_metrics.json')

            # Save aggregated metrics
            import json
            import os

            aggregated_data = analytics_aggregator.to_dict()
            path = 'platform-logs/aggregated_metrics.json'

            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(aggregated_data, f)
            os.replace(tmp, path)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f'Metrics persisted in {duration_ms:.2f}ms')

        except Exception as e:
            logger.error(f'Failed to persist metrics: {str(e)}', exc_info=True)

    async def _cleanup_old_data(self):
        """Remove data beyond retention policy."""
        try:
            logger.info('Running data cleanup')
            start_time = time.time()

            now = int(time.time())

            # Minute-level: Keep only last 24 hours
            cutoff_minute = now - (24 * 3600)
            while (
                enhanced_metrics_store._buckets
                and enhanced_metrics_store._buckets[0].start_ts < cutoff_minute
            ):
                enhanced_metrics_store._buckets.popleft()

            # 5-minute: Keep only last 7 days (handled by deque maxlen)
            # Hourly: Keep only last 30 days (handled by deque maxlen)
            # Daily: Keep only last 90 days (handled by deque maxlen)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f'Data cleanup completed in {duration_ms:.2f}ms')

        except Exception as e:
            logger.error(f'Failed to cleanup old data: {str(e)}', exc_info=True)


# Global scheduler instance
analytics_scheduler = AnalyticsScheduler()
