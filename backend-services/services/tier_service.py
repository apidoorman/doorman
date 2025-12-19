"""
Tier Service

Business logic for managing tiers, plans, and user assignments.
Handles tier CRUD, user assignments, upgrades, downgrades, and transitions.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from models.rate_limit_models import Tier, TierLimits, TierName, UserTierAssignment

logger = logging.getLogger(__name__)


class TierService:
    """
    Service for managing tiers and user assignments

    Features:
    - CRUD operations for tiers
    - User-to-tier assignments
    - Tier upgrades and downgrades
    - Override limits for specific users
    - Temporary tier assignments
    - Tier comparison and selection
    """

    def __init__(self, db):
        """
        Initialize tier service

        Args:
            db: MongoDB database instance (sync) or InMemoryDB
        """
        self.db = db
        self.tiers_collection = db.tiers
        self.assignments_collection = db.user_tier_assignments

    # ========================================================================
    # TIER CRUD OPERATIONS
    # ========================================================================

    async def create_tier(self, tier: Tier) -> Tier:
        """
        Create a new tier

        Args:
            tier: Tier object to create

        Returns:
            Created tier

        Raises:
            ValueError: If tier with same ID already exists
        """
        # Check if tier already exists
        existing = await self.tiers_collection.find_one({'tier_id': tier.tier_id})
        if existing:
            raise ValueError(f'Tier with ID {tier.tier_id} already exists')

        # Set timestamps
        tier.created_at = datetime.now()
        tier.updated_at = datetime.now()

        # Insert into database
        await self.tiers_collection.insert_one(tier.to_dict())

        logger.info(f'Created tier: {tier.tier_id}')
        return tier

    async def get_tier(self, tier_id: str) -> Tier | None:
        """
        Get tier by ID

        Args:
            tier_id: Tier identifier

        Returns:
            Tier object or None if not found
        """
        tier_data = await self.tiers_collection.find_one({'tier_id': tier_id})

        if tier_data:
            return Tier.from_dict(tier_data)

        return None

    async def get_tier_by_name(self, name: TierName) -> Tier | None:
        """
        Get tier by name

        Args:
            name: Tier name enum

        Returns:
            Tier object or None if not found
        """
        tier_data = await self.tiers_collection.find_one({'name': name.value})

        if tier_data:
            return Tier.from_dict(tier_data)

        return None

    async def list_tiers(
        self,
        enabled_only: bool = False,
        search_term: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Tier]:
        """
        List all tiers

        Args:
            enabled_only: Only return enabled tiers
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of tiers
        """
        query = {}
        if enabled_only:
            query['enabled'] = True

        cursor = self.tiers_collection.find(query).skip(skip).limit(limit)
        tiers: list[Tier] = []

        async for tier_data in cursor:
            tiers.append(Tier.from_dict(tier_data))

        if search_term:
            term = search_term.lower()
            tiers = [
                tier
                for tier in tiers
                if term in (tier.name or '').lower()
                or term in (tier.display_name or '').lower()
                or term in (tier.description or '').lower()
            ]

        return tiers

    async def count_tiers(self, enabled_only: bool = False, search_term: str | None = None) -> int:
        """Count tiers matching filters."""
        query: dict[str, Any] = {}
        if enabled_only:
            query['enabled'] = True
        total = await self.tiers_collection.count_documents(query)
        if not search_term:
            return total
        # If searching, we need to apply search term on name/description
        # For simplicity, load only fields required for matching
        cursor = self.tiers_collection.find(query, {'name': 1, 'display_name': 1, 'description': 1})
        term = (search_term or '').lower()
        cnt = 0
        async for doc in cursor:
            name = str(doc.get('name') or '').lower()
            dn = str(doc.get('display_name') or '').lower()
            desc = str(doc.get('description') or '').lower()
            if (term in name) or (term in dn) or (term in desc):
                cnt += 1
        return cnt

    async def update_tier(self, tier_id: str, updates: dict[str, Any]) -> Tier | None:
        """
        Update tier

        Args:
            tier_id: Tier identifier
            updates: Dictionary of fields to update

        Returns:
            Updated tier or None if not found
        """
        # Add updated timestamp
        updates['updated_at'] = datetime.now().isoformat()

        result = await self.tiers_collection.find_one_and_update(
            {'tier_id': tier_id}, {'$set': updates}, return_document=True
        )

        if result:
            logger.info(f'Updated tier: {tier_id}')
            return Tier.from_dict(result)

        return None

    async def delete_tier(self, tier_id: str) -> bool:
        """
        Delete tier

        Args:
            tier_id: Tier identifier

        Returns:
            True if deleted, False if not found
        """
        # Check if any users are assigned to this tier
        user_count = await self.assignments_collection.count_documents({'tier_id': tier_id})

        if user_count > 0:
            raise ValueError(f'Cannot delete tier {tier_id}: {user_count} users are assigned to it')

        result = await self.tiers_collection.delete_one({'tier_id': tier_id})

        if result.deleted_count > 0:
            logger.info(f'Deleted tier: {tier_id}')
            return True

        return False

    async def get_default_tier(self) -> Tier | None:
        """
        Get the default tier

        Returns:
            Default tier or None if not set
        """
        tier_data = await self.tiers_collection.find_one({'is_default': True})

        if tier_data:
            return Tier.from_dict(tier_data)

        return None

    # ========================================================================
    # USER TIER ASSIGNMENTS
    # ========================================================================

    async def assign_user_to_tier(
        self,
        user_id: str,
        tier_id: str,
        assigned_by: str | None = None,
        effective_from: datetime | None = None,
        effective_until: datetime | None = None,
        override_limits: TierLimits | None = None,
        notes: str | None = None,
    ) -> UserTierAssignment:
        """
        Assign user to a tier

        Args:
            user_id: User identifier
            tier_id: Tier identifier
            assigned_by: Who assigned the tier
            effective_from: When assignment becomes effective
            effective_until: When assignment expires
            override_limits: Custom limits for this user
            notes: Assignment notes

        Returns:
            UserTierAssignment object

        Raises:
            ValueError: If tier doesn't exist
        """
        # Verify tier exists
        tier = await self.get_tier(tier_id)
        if not tier:
            raise ValueError(f'Tier {tier_id} not found')

        # Check if user already has an assignment
        existing = await self.assignments_collection.find_one({'user_id': user_id})

        assignment = UserTierAssignment(
            user_id=user_id,
            tier_id=tier_id,
            override_limits=override_limits,
            effective_from=effective_from,
            effective_until=effective_until,
            assigned_at=datetime.now(),
            assigned_by=assigned_by,
            notes=notes,
        )

        if existing:
            # Update existing assignment
            await self.assignments_collection.replace_one(
                {'user_id': user_id}, assignment.to_dict()
            )
            logger.info(f'Updated tier assignment for user {user_id} to {tier_id}')
        else:
            # Create new assignment
            await self.assignments_collection.insert_one(assignment.to_dict())
            logger.info(f'Assigned user {user_id} to tier {tier_id}')

        return assignment

    async def get_user_assignment(self, user_id: str) -> UserTierAssignment | None:
        """
        Get user's tier assignment

        Args:
            user_id: User identifier

        Returns:
            UserTierAssignment or None if not assigned
        """
        assignment_data = await self.assignments_collection.find_one({'user_id': user_id})

        if assignment_data:
            assignment_data.pop('_id', None)
            return UserTierAssignment(**assignment_data)

        return None

    async def get_user_tier(self, user_id: str) -> Tier | None:
        """
        Get the tier for a user

        Considers effective dates and returns appropriate tier.

        Args:
            user_id: User identifier

        Returns:
            Tier object or default tier if no assignment
        """
        assignment = await self.get_user_assignment(user_id)

        if assignment:
            # Check if assignment is currently effective
            now = datetime.now()

            if assignment.effective_from and now < assignment.effective_from:
                # Assignment not yet effective
                return await self.get_default_tier()

            if assignment.effective_until and now > assignment.effective_until:
                # Assignment expired
                return await self.get_default_tier()

            # Get the assigned tier
            return await self.get_tier(assignment.tier_id)

        # No assignment, return default tier
        return await self.get_default_tier()

    async def get_user_limits(self, user_id: str) -> TierLimits | None:
        """
        Get effective limits for a user

        Considers tier limits and user-specific overrides.

        Args:
            user_id: User identifier

        Returns:
            TierLimits object or None
        """
        assignment = await self.get_user_assignment(user_id)

        if assignment and assignment.override_limits:
            # User has custom limits
            return assignment.override_limits

        # Get tier limits
        tier = await self.get_user_tier(user_id)
        if tier:
            return tier.limits

        return None

    async def remove_user_assignment(self, user_id: str) -> bool:
        """
        Remove user's tier assignment

        Args:
            user_id: User identifier

        Returns:
            True if removed, False if no assignment
        """
        result = await self.assignments_collection.delete_one({'user_id': user_id})

        if result.deleted_count > 0:
            logger.info(f'Removed tier assignment for user {user_id}')
            return True

        return False

    async def list_users_in_tier(
        self, tier_id: str, skip: int = 0, limit: int = 100
    ) -> list[UserTierAssignment]:
        """
        List all users assigned to a tier

        Args:
            tier_id: Tier identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of user assignments
        """
        cursor = self.assignments_collection.find({'tier_id': tier_id}).skip(skip).limit(limit)

        assignments = []
        async for assignment_data in cursor:
            assignments.append(UserTierAssignment(**assignment_data))

        return assignments

    # ========================================================================
    # TIER UPGRADES & DOWNGRADES
    # ========================================================================

    async def upgrade_user_tier(
        self,
        user_id: str,
        new_tier_id: str,
        immediate: bool = True,
        scheduled_date: datetime | None = None,
        assigned_by: str | None = None,
    ) -> UserTierAssignment:
        """
        Upgrade user to a higher tier

        Args:
            user_id: User identifier
            new_tier_id: New tier identifier
            immediate: Apply immediately or schedule
            scheduled_date: When to apply (if not immediate)
            assigned_by: Who initiated the upgrade

        Returns:
            Updated UserTierAssignment
        """
        # Get current and new tiers
        current_tier = await self.get_user_tier(user_id)
        new_tier = await self.get_tier(new_tier_id)

        if not new_tier:
            raise ValueError(f'Tier {new_tier_id} not found')

        # Determine effective date
        effective_from = datetime.now() if immediate else scheduled_date

        # Create assignment
        assignment = await self.assign_user_to_tier(
            user_id=user_id,
            tier_id=new_tier_id,
            assigned_by=assigned_by,
            effective_from=effective_from,
            notes=f'Upgraded from {current_tier.tier_id if current_tier else "default"}',
        )

        logger.info(f'Upgraded user {user_id} to tier {new_tier_id}')
        return assignment

    async def downgrade_user_tier(
        self,
        user_id: str,
        new_tier_id: str,
        grace_period_days: int = 0,
        assigned_by: str | None = None,
    ) -> UserTierAssignment:
        """
        Downgrade user to a lower tier

        Args:
            user_id: User identifier
            new_tier_id: New tier identifier
            grace_period_days: Days before downgrade takes effect
            assigned_by: Who initiated the downgrade

        Returns:
            Updated UserTierAssignment
        """
        # Get current and new tiers
        current_tier = await self.get_user_tier(user_id)
        new_tier = await self.get_tier(new_tier_id)

        if not new_tier:
            raise ValueError(f'Tier {new_tier_id} not found')

        # Calculate effective date with grace period
        effective_from = datetime.now() + timedelta(days=grace_period_days)

        # Create assignment
        assignment = await self.assign_user_to_tier(
            user_id=user_id,
            tier_id=new_tier_id,
            assigned_by=assigned_by,
            effective_from=effective_from,
            notes=f'Downgraded from {current_tier.tier_id if current_tier else "default"} with {grace_period_days} day grace period',
        )

        logger.info(
            f'Scheduled downgrade for user {user_id} to tier {new_tier_id} on {effective_from}'
        )
        return assignment

    async def temporary_tier_upgrade(
        self, user_id: str, temp_tier_id: str, duration_days: int, assigned_by: str | None = None
    ) -> UserTierAssignment:
        """
        Temporarily upgrade user to a higher tier

        Args:
            user_id: User identifier
            temp_tier_id: Temporary tier identifier
            duration_days: How many days the upgrade lasts
            assigned_by: Who initiated the upgrade

        Returns:
            UserTierAssignment with expiration
        """
        temp_tier = await self.get_tier(temp_tier_id)
        if not temp_tier:
            raise ValueError(f'Tier {temp_tier_id} not found')

        # Set expiration
        effective_from = datetime.now()
        effective_until = effective_from + timedelta(days=duration_days)

        # Create temporary assignment
        assignment = await self.assign_user_to_tier(
            user_id=user_id,
            tier_id=temp_tier_id,
            assigned_by=assigned_by,
            effective_from=effective_from,
            effective_until=effective_until,
            notes=f'Temporary upgrade for {duration_days} days',
        )

        logger.info(
            f'Temporary upgrade for user {user_id} to tier {temp_tier_id} until {effective_until}'
        )
        return assignment

    # ========================================================================
    # TIER COMPARISON & ANALYTICS
    # ========================================================================

    async def compare_tiers(self, tier_ids: list[str]) -> list[dict[str, Any]]:
        """
        Compare multiple tiers side-by-side

        Args:
            tier_ids: List of tier identifiers to compare

        Returns:
            List of tier comparison data
        """
        comparison = []

        for tier_id in tier_ids:
            tier = await self.get_tier(tier_id)
            if tier:
                comparison.append(
                    {
                        'tier_id': tier.tier_id,
                        'name': tier.name.value,
                        'display_name': tier.display_name,
                        'limits': tier.limits.to_dict(),
                        'price_monthly': tier.price_monthly,
                        'price_yearly': tier.price_yearly,
                        'features': tier.features,
                    }
                )

        return comparison

    async def get_tier_statistics(self, tier_id: str) -> dict[str, Any]:
        """
        Get statistics for a tier

        Args:
            tier_id: Tier identifier

        Returns:
            Dictionary with tier statistics
        """
        # Count users in tier
        user_count = await self.assignments_collection.count_documents({'tier_id': tier_id})

        # Count active assignments (within effective dates)
        now = datetime.now()
        active_count = await self.assignments_collection.count_documents(
            {
                'tier_id': tier_id,
                '$or': [{'effective_from': None}, {'effective_from': {'$lte': now}}],
                '$or': [{'effective_until': None}, {'effective_until': {'$gte': now}}],
            }
        )

        return {
            'tier_id': tier_id,
            'total_users': user_count,
            'active_users': active_count,
            'inactive_users': user_count - active_count,
        }

    async def get_all_tier_statistics(self) -> list[dict[str, Any]]:
        """
        Get statistics for all tiers

        Returns:
            List of tier statistics
        """
        tiers = await self.list_tiers()
        statistics = []

        for tier in tiers:
            stats = await self.get_tier_statistics(tier.tier_id)
            stats['tier_name'] = tier.display_name
            statistics.append(stats)

        return statistics


# Global tier service instance
_tier_service: TierService | None = None


def get_tier_service(db) -> TierService:
    """
    Get or create global tier service instance

    Args:
        db: MongoDB database instance (sync) or InMemoryDB

    Returns:
        TierService instance
    """
    global _tier_service

    if _tier_service is None:
        _tier_service = TierService(db)

    return _tier_service
