import time

import pytest

from models.rate_limit_models import Tier, TierLimits, TierName
from services.tier_service import TierService
from utils.database_async import async_database
from utils.doorman_cache_util import doorman_cache


@pytest.mark.asyncio
async def test_get_user_limits_ignores_stale_cache_without_assignment():
    service = TierService(async_database.db)
    user_id = 'admin'
    tier_id = f'tier-cache-{int(time.time() * 1000)}'

    tier = Tier(
        tier_id=tier_id,
        name=TierName.CUSTOM,
        display_name=tier_id,
        limits=TierLimits(requests_per_minute=1),
    )

    await service.create_tier(tier)
    try:
        await service.assign_user_to_tier(user_id, tier_id)
        assigned_limits = await service.get_user_limits(user_id)
        assert assigned_limits is not None
        assert assigned_limits.requests_per_minute == 1

        await service.remove_user_assignment(user_id)
        doorman_cache.set_cache(
            'user_cache',
            f'tier_limits_{user_id}',
            tier.limits.to_dict(),
        )

        limits = await service.get_user_limits(user_id)
        assert limits is None or limits.requests_per_minute != 1
    finally:
        await service.remove_user_assignment(user_id)
        try:
            await service.delete_tier(tier_id)
        except Exception:
            pass
        doorman_cache.delete_cache('user_cache', f'tier_limits_{user_id}')
