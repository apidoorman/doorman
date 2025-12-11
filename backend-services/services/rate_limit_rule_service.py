"""
Rate Limit Rule Service

Business logic for managing rate limit rules.
Handles rule CRUD, validation, and application.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

try:
    # Use a type-only import to avoid a hard runtime dependency during tests
    if TYPE_CHECKING:
        from motor.motor_asyncio import AsyncIOMotorDatabase  # pragma: no cover
    else:  # Fallback for runtime when motor isn't installed (e.g., unit tests)
        AsyncIOMotorDatabase = Any  # type: ignore
except Exception:  # Defensive: never fail import due to typing
    AsyncIOMotorDatabase = Any  # type: ignore

from models.rate_limit_models import RateLimitRule, RuleType

logger = logging.getLogger(__name__)


class RateLimitRuleService:
    """
    Service for managing rate limit rules

    Features:
    - CRUD operations for rules
    - Rule validation
    - Priority management
    - Bulk operations
    - Rule testing
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize rate limit rule service

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.rules_collection = db.rate_limit_rules

    # ========================================================================
    # RULE CRUD OPERATIONS
    # ========================================================================

    async def create_rule(self, rule: RateLimitRule) -> RateLimitRule:
        """
        Create a new rate limit rule

        Args:
            rule: RateLimitRule object to create

        Returns:
            Created rule

        Raises:
            ValueError: If rule with same ID already exists
        """
        # Check if rule already exists
        existing = await self.rules_collection.find_one({'rule_id': rule.rule_id})
        if existing:
            raise ValueError(f'Rule with ID {rule.rule_id} already exists')

        # Set timestamps
        rule.created_at = datetime.now()
        rule.updated_at = datetime.now()

        # Insert into database
        await self.rules_collection.insert_one(rule.to_dict())

        logger.info(f'Created rate limit rule: {rule.rule_id}')
        return rule

    async def get_rule(self, rule_id: str) -> RateLimitRule | None:
        """
        Get rule by ID

        Args:
            rule_id: Rule identifier

        Returns:
            RateLimitRule object or None if not found
        """
        rule_data = await self.rules_collection.find_one({'rule_id': rule_id})

        if rule_data:
            return RateLimitRule.from_dict(rule_data)

        return None

    async def list_rules(
        self,
        rule_type: RuleType | None = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RateLimitRule]:
        """
        List rate limit rules

        Args:
            rule_type: Filter by rule type
            enabled_only: Only return enabled rules
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of rules
        """
        query = {}

        if rule_type:
            query['rule_type'] = rule_type.value

        if enabled_only:
            query['enabled'] = True

        # Sort by priority (highest first)
        cursor = self.rules_collection.find(query).sort('priority', -1).skip(skip).limit(limit)
        rules = []

        async for rule_data in cursor:
            rules.append(RateLimitRule.from_dict(rule_data))

        return rules

    async def update_rule(self, rule_id: str, updates: dict[str, Any]) -> RateLimitRule | None:
        """
        Update rule

        Args:
            rule_id: Rule identifier
            updates: Dictionary of fields to update

        Returns:
            Updated rule or None if not found
        """
        # Add updated timestamp
        updates['updated_at'] = datetime.now().isoformat()

        result = await self.rules_collection.find_one_and_update(
            {'rule_id': rule_id}, {'$set': updates}, return_document=True
        )

        if result:
            logger.info(f'Updated rate limit rule: {rule_id}')
            return RateLimitRule.from_dict(result)

        return None

    async def delete_rule(self, rule_id: str) -> bool:
        """
        Delete rule

        Args:
            rule_id: Rule identifier

        Returns:
            True if deleted, False if not found
        """
        result = await self.rules_collection.delete_one({'rule_id': rule_id})

        if result.deleted_count > 0:
            logger.info(f'Deleted rate limit rule: {rule_id}')
            return True

        return False

    async def enable_rule(self, rule_id: str) -> RateLimitRule | None:
        """
        Enable a rule

        Args:
            rule_id: Rule identifier

        Returns:
            Updated rule or None if not found
        """
        return await self.update_rule(rule_id, {'enabled': True})

    async def disable_rule(self, rule_id: str) -> RateLimitRule | None:
        """
        Disable a rule

        Args:
            rule_id: Rule identifier

        Returns:
            Updated rule or None if not found
        """
        return await self.update_rule(rule_id, {'enabled': False})

    # ========================================================================
    # RULE QUERIES
    # ========================================================================

    async def get_applicable_rules(
        self,
        user_id: str | None = None,
        api_name: str | None = None,
        endpoint_uri: str | None = None,
        ip_address: str | None = None,
    ) -> list[RateLimitRule]:
        """
        Get all applicable rules for a request

        Args:
            user_id: User identifier
            api_name: API name
            endpoint_uri: Endpoint URI
            ip_address: IP address

        Returns:
            List of applicable rules sorted by priority
        """
        query = {'enabled': True}

        # Build OR query for applicable rules
        or_conditions = []

        # Global rules always apply
        or_conditions.append({'rule_type': RuleType.GLOBAL.value})

        # Per-user rules
        if user_id:
            or_conditions.append(
                {'rule_type': RuleType.PER_USER.value, 'target_identifier': user_id}
            )

        # Per-API rules
        if api_name:
            or_conditions.append(
                {'rule_type': RuleType.PER_API.value, 'target_identifier': api_name}
            )

        # Per-endpoint rules
        if endpoint_uri:
            or_conditions.append(
                {'rule_type': RuleType.PER_ENDPOINT.value, 'target_identifier': endpoint_uri}
            )

        # Per-IP rules
        if ip_address:
            or_conditions.append(
                {'rule_type': RuleType.PER_IP.value, 'target_identifier': ip_address}
            )

        if or_conditions:
            query['$or'] = or_conditions

        # Get rules sorted by priority
        cursor = self.rules_collection.find(query).sort('priority', -1)
        rules = []

        async for rule_data in cursor:
            rules.append(RateLimitRule.from_dict(rule_data))

        return rules

    async def search_rules(self, search_term: str) -> list[RateLimitRule]:
        """
        Search rules by ID, description, or target identifier

        Args:
            search_term: Search term

        Returns:
            List of matching rules
        """
        query = {
            '$or': [
                {'rule_id': {'$regex': search_term, '$options': 'i'}},
                {'description': {'$regex': search_term, '$options': 'i'}},
                {'target_identifier': {'$regex': search_term, '$options': 'i'}},
            ]
        }

        cursor = self.rules_collection.find(query).sort('priority', -1)
        rules = []

        async for rule_data in cursor:
            rules.append(RateLimitRule.from_dict(rule_data))

        return rules

    # ========================================================================
    # BULK OPERATIONS
    # ========================================================================

    async def bulk_create_rules(self, rules: list[RateLimitRule]) -> int:
        """
        Create multiple rules at once

        Args:
            rules: List of rules to create

        Returns:
            Number of rules created
        """
        if not rules:
            return 0

        # Set timestamps
        now = datetime.now()
        for rule in rules:
            rule.created_at = now
            rule.updated_at = now

        # Insert all rules
        rule_dicts = [rule.to_dict() for rule in rules]
        result = await self.rules_collection.insert_many(rule_dicts)

        count = len(result.inserted_ids)
        logger.info(f'Bulk created {count} rate limit rules')
        return count

    async def bulk_delete_rules(self, rule_ids: list[str]) -> int:
        """
        Delete multiple rules at once

        Args:
            rule_ids: List of rule IDs to delete

        Returns:
            Number of rules deleted
        """
        if not rule_ids:
            return 0

        result = await self.rules_collection.delete_many({'rule_id': {'$in': rule_ids}})

        count = result.deleted_count
        logger.info(f'Bulk deleted {count} rate limit rules')
        return count

    async def bulk_enable_rules(self, rule_ids: list[str]) -> int:
        """
        Enable multiple rules at once

        Args:
            rule_ids: List of rule IDs to enable

        Returns:
            Number of rules enabled
        """
        if not rule_ids:
            return 0

        result = await self.rules_collection.update_many(
            {'rule_id': {'$in': rule_ids}},
            {'$set': {'enabled': True, 'updated_at': datetime.now().isoformat()}},
        )

        count = result.modified_count
        logger.info(f'Bulk enabled {count} rate limit rules')
        return count

    async def bulk_disable_rules(self, rule_ids: list[str]) -> int:
        """
        Disable multiple rules at once

        Args:
            rule_ids: List of rule IDs to disable

        Returns:
            Number of rules disabled
        """
        if not rule_ids:
            return 0

        result = await self.rules_collection.update_many(
            {'rule_id': {'$in': rule_ids}},
            {'$set': {'enabled': False, 'updated_at': datetime.now().isoformat()}},
        )

        count = result.modified_count
        logger.info(f'Bulk disabled {count} rate limit rules')
        return count

    # ========================================================================
    # RULE DUPLICATION
    # ========================================================================

    async def duplicate_rule(self, rule_id: str, new_rule_id: str) -> RateLimitRule:
        """
        Duplicate an existing rule

        Args:
            rule_id: Source rule ID
            new_rule_id: New rule ID

        Returns:
            Duplicated rule

        Raises:
            ValueError: If source rule not found or new ID already exists
        """
        # Get source rule
        source_rule = await self.get_rule(rule_id)
        if not source_rule:
            raise ValueError(f'Source rule {rule_id} not found')

        # Check if new ID already exists
        existing = await self.rules_collection.find_one({'rule_id': new_rule_id})
        if existing:
            raise ValueError(f'Rule with ID {new_rule_id} already exists')

        # Create new rule with same properties
        new_rule = RateLimitRule(
            rule_id=new_rule_id,
            rule_type=source_rule.rule_type,
            time_window=source_rule.time_window,
            limit=source_rule.limit,
            target_identifier=source_rule.target_identifier,
            burst_allowance=source_rule.burst_allowance,
            priority=source_rule.priority,
            enabled=source_rule.enabled,
            description=f'Copy of {source_rule.rule_id}',
        )

        return await self.create_rule(new_rule)

    # ========================================================================
    # RULE STATISTICS
    # ========================================================================

    async def get_rule_statistics(self) -> dict[str, Any]:
        """
        Get statistics about rate limit rules

        Returns:
            Dictionary with rule statistics
        """
        total_rules = await self.rules_collection.count_documents({})
        enabled_rules = await self.rules_collection.count_documents({'enabled': True})
        disabled_rules = total_rules - enabled_rules

        # Count by type
        type_counts = {}
        for rule_type in RuleType:
            count = await self.rules_collection.count_documents({'rule_type': rule_type.value})
            type_counts[rule_type.value] = count

        return {
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'disabled_rules': disabled_rules,
            'rules_by_type': type_counts,
        }

    # ========================================================================
    # RULE VALIDATION
    # ========================================================================

    def validate_rule(self, rule: RateLimitRule) -> list[str]:
        """
        Validate a rule

        Args:
            rule: Rule to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check limit is positive
        if rule.limit <= 0:
            errors.append('Limit must be greater than 0')

        # Check burst allowance is non-negative
        if rule.burst_allowance < 0:
            errors.append('Burst allowance cannot be negative')

        # Check target identifier for specific rule types
        if rule.rule_type in [
            RuleType.PER_USER,
            RuleType.PER_API,
            RuleType.PER_ENDPOINT,
            RuleType.PER_IP,
        ]:
            if not rule.target_identifier:
                errors.append(f'Target identifier required for {rule.rule_type.value} rules')

        return errors


# Global rule service instance
_rule_service: RateLimitRuleService | None = None


def get_rate_limit_rule_service(db: AsyncIOMotorDatabase) -> RateLimitRuleService:
    """
    Get or create global rule service instance

    Args:
        db: MongoDB database instance

    Returns:
        RateLimitRuleService instance
    """
    global _rule_service

    if _rule_service is None:
        _rule_service = RateLimitRuleService(db)

    return _rule_service
