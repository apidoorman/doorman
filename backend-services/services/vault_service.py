"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
from datetime import datetime

try:
    from datetime import UTC
except Exception:
    UTC = UTC

from models.create_vault_entry_model import CreateVaultEntryModel
from models.response_model import ResponseModel
from models.update_vault_entry_model import UpdateVaultEntryModel
from utils.async_db import db_delete_one, db_find_list, db_find_one, db_insert_one, db_update_one
from utils.constants import ErrorCodes, Messages
from utils.database_async import user_collection, vault_entries_collection
from utils.vault_encryption_util import encrypt_vault_value, is_vault_configured

logger = logging.getLogger('doorman.gateway')


class VaultService:
    """Service for managing encrypted vault entries."""

    @staticmethod
    async def create_vault_entry(
        username: str, entry_data: CreateVaultEntryModel, request_id: str
    ) -> dict:
        """
        Create a new vault entry for a user.

        Args:
            username: Username of the vault entry owner
            entry_data: Vault entry creation data
            request_id: Request ID for logging

        Returns:
            ResponseModel dict with success or error
        """
        logger.info(
            f'{request_id} | Creating vault entry: {entry_data.key_name} for user: {username}'
        )

        # Check if VAULT_KEY is configured
        if not is_vault_configured():
            logger.error(f'{request_id} | VAULT_KEY not configured')
            return ResponseModel(
                status_code=500,
                error_code='VAULT001',
                error_message='Vault encryption is not configured. Set VAULT_KEY in environment variables.',
            ).dict()

        # Get user to retrieve email
        user = await db_find_one(user_collection, {'username': username})
        if not user:
            logger.error(f'{request_id} | User not found: {username}')
            return ResponseModel(
                status_code=404, error_code='VAULT002', error_message='User not found'
            ).dict()

        email = user.get('email')
        if not email:
            logger.error(f'{request_id} | User email not found: {username}')
            return ResponseModel(
                status_code=400,
                error_code='VAULT003',
                error_message='User email is required for vault encryption',
            ).dict()

        # Check if entry already exists
        existing = await db_find_one(
            vault_entries_collection, {'username': username, 'key_name': entry_data.key_name}
        )
        if existing:
            logger.error(f'{request_id} | Vault entry already exists: {entry_data.key_name}')
            return ResponseModel(
                status_code=409,
                error_code='VAULT004',
                error_message=f'Vault entry with key_name "{entry_data.key_name}" already exists',
            ).dict()

        # Encrypt the value
        try:
            encrypted_value = encrypt_vault_value(entry_data.value, email, username)
        except Exception as e:
            logger.error(f'{request_id} | Encryption failed: {str(e)}')
            return ResponseModel(
                status_code=500,
                error_code='VAULT005',
                error_message='Failed to encrypt vault value',
            ).dict()

        # Create vault entry
        now = datetime.now(UTC).isoformat()
        vault_entry = {
            'username': username,
            'key_name': entry_data.key_name,
            'encrypted_value': encrypted_value,
            'description': entry_data.description,
            'created_at': now,
            'updated_at': now,
        }

        try:
            result = await db_insert_one(vault_entries_collection, vault_entry)
            if result.acknowledged:
                logger.info(
                    f'{request_id} | Vault entry created successfully: {entry_data.key_name}'
                )
                return ResponseModel(
                    status_code=201,
                    message='Vault entry created successfully',
                    data={'key_name': entry_data.key_name},
                ).dict()
            else:
                logger.error(f'{request_id} | Failed to create vault entry')
                return ResponseModel(
                    status_code=500,
                    error_code='VAULT006',
                    error_message='Failed to create vault entry',
                ).dict()
        except Exception as e:
            logger.error(f'{request_id} | Error creating vault entry: {str(e)}')
            return ResponseModel(
                status_code=500, error_code=ErrorCodes.UNEXPECTED, error_message=Messages.UNEXPECTED
            ).dict()

    @staticmethod
    async def get_vault_entry(username: str, key_name: str, request_id: str) -> dict:
        """
        Get a vault entry by key name. Value is NOT returned.

        Args:
            username: Username of the vault entry owner
            key_name: Name of the vault key
            request_id: Request ID for logging

        Returns:
            ResponseModel dict with vault entry (without value) or error
        """
        logger.info(f'{request_id} | Getting vault entry: {key_name} for user: {username}')

        entry = await db_find_one(
            vault_entries_collection, {'username': username, 'key_name': key_name}
        )

        if not entry:
            logger.error(f'{request_id} | Vault entry not found: {key_name}')
            return ResponseModel(
                status_code=404, error_code='VAULT007', error_message='Vault entry not found'
            ).dict()

        # Remove sensitive data
        if entry.get('_id'):
            del entry['_id']
        if entry.get('encrypted_value'):
            del entry['encrypted_value']

        return ResponseModel(status_code=200, data=entry).dict()

    @staticmethod
    async def list_vault_entries(username: str, request_id: str) -> dict:
        """
        List all vault entries for a user. Values are NOT returned.

        Args:
            username: Username of the vault entry owner
            request_id: Request ID for logging

        Returns:
            ResponseModel dict with list of vault entries (without values)
        """
        logger.info(f'{request_id} | Listing vault entries for user: {username}')

        try:
            entries = await db_find_list(vault_entries_collection, {'username': username})

            # Remove sensitive data from all entries
            clean_entries = []
            for entry in entries:
                if entry.get('_id'):
                    del entry['_id']
                if entry.get('encrypted_value'):
                    del entry['encrypted_value']
                clean_entries.append(entry)

            return ResponseModel(
                status_code=200, data={'entries': clean_entries, 'count': len(clean_entries)}
            ).dict()
        except Exception as e:
            logger.error(f'{request_id} | Error listing vault entries: {str(e)}')
            return ResponseModel(
                status_code=500, error_code=ErrorCodes.UNEXPECTED, error_message=Messages.UNEXPECTED
            ).dict()

    @staticmethod
    async def update_vault_entry(
        username: str, key_name: str, update_data: UpdateVaultEntryModel, request_id: str
    ) -> dict:
        """
        Update a vault entry. Only description can be updated, not the value.

        Args:
            username: Username of the vault entry owner
            key_name: Name of the vault key
            update_data: Update data (description only)
            request_id: Request ID for logging

        Returns:
            ResponseModel dict with success or error
        """
        logger.info(f'{request_id} | Updating vault entry: {key_name} for user: {username}')

        # Check if entry exists
        entry = await db_find_one(
            vault_entries_collection, {'username': username, 'key_name': key_name}
        )

        if not entry:
            logger.error(f'{request_id} | Vault entry not found: {key_name}')
            return ResponseModel(
                status_code=404, error_code='VAULT007', error_message='Vault entry not found'
            ).dict()

        # Update only description
        now = datetime.now(UTC).isoformat()
        update_fields = {'updated_at': now}

        if update_data.description is not None:
            update_fields['description'] = update_data.description

        try:
            result = await db_update_one(
                vault_entries_collection,
                {'username': username, 'key_name': key_name},
                {'$set': update_fields},
            )

            if result.modified_count > 0:
                logger.info(f'{request_id} | Vault entry updated successfully: {key_name}')
                return ResponseModel(
                    status_code=200, message='Vault entry updated successfully'
                ).dict()
            else:
                logger.warning(f'{request_id} | No changes made to vault entry: {key_name}')
                return ResponseModel(
                    status_code=200, message='No changes made to vault entry'
                ).dict()
        except Exception as e:
            logger.error(f'{request_id} | Error updating vault entry: {str(e)}')
            return ResponseModel(
                status_code=500, error_code=ErrorCodes.UNEXPECTED, error_message=Messages.UNEXPECTED
            ).dict()

    @staticmethod
    async def delete_vault_entry(username: str, key_name: str, request_id: str) -> dict:
        """
        Delete a vault entry.

        Args:
            username: Username of the vault entry owner
            key_name: Name of the vault key
            request_id: Request ID for logging

        Returns:
            ResponseModel dict with success or error
        """
        logger.info(f'{request_id} | Deleting vault entry: {key_name} for user: {username}')

        # Check if entry exists
        entry = await db_find_one(
            vault_entries_collection, {'username': username, 'key_name': key_name}
        )

        if not entry:
            logger.error(f'{request_id} | Vault entry not found: {key_name}')
            return ResponseModel(
                status_code=404, error_code='VAULT007', error_message='Vault entry not found'
            ).dict()

        try:
            result = await db_delete_one(
                vault_entries_collection, {'username': username, 'key_name': key_name}
            )

            if result.deleted_count > 0:
                logger.info(f'{request_id} | Vault entry deleted successfully: {key_name}')
                return ResponseModel(
                    status_code=200, message='Vault entry deleted successfully'
                ).dict()
            else:
                logger.error(f'{request_id} | Failed to delete vault entry: {key_name}')
                return ResponseModel(
                    status_code=500,
                    error_code='VAULT008',
                    error_message='Failed to delete vault entry',
                ).dict()
        except Exception as e:
            logger.error(f'{request_id} | Error deleting vault entry: {str(e)}')
            return ResponseModel(
                status_code=500, error_code=ErrorCodes.UNEXPECTED, error_message=Messages.UNEXPECTED
            ).dict()
