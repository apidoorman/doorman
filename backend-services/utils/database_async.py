"""
Async database wrapper using Motor for non-blocking I/O operations.

The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception:
    AsyncIOMotorClient = None
import logging
import os

from dotenv import load_dotenv, find_dotenv

from utils import password_util
from utils.database import InMemoryDB

try:
    import sys as _sys
    _running_under_pytest = 'PYTEST_CURRENT_TEST' in os.environ or 'pytest' in _sys.modules
except Exception:
    _running_under_pytest = False
if not _running_under_pytest:
    load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger('doorman.gateway')


class AsyncDatabase:
    """Async database wrapper that supports both Motor (MongoDB) and in-memory modes."""

    def __init__(self):
        mem_flag = os.getenv('MEM_OR_EXTERNAL')
        if mem_flag is None:
            mem_flag = os.getenv('MEM_OR_REDIS', 'MEM')
        self.memory_only = str(mem_flag).upper() == 'MEM'

        if self.memory_only:
            # Reuse the same in-memory data as the sync layer while exposing
            # async-compatible collection interfaces (wrapping the same sync collections).
            try:
                from utils.database import database as _sync_db

                self.client = None
                self.db_existed = getattr(_sync_db, 'db_existed', False)

                # Build a lightweight async view that wraps the shared sync collections
                class _AsyncDBView:
                    def __init__(self, sync_db: InMemoryDB):
                        self._sync = sync_db
                        # Wrap collections with async facade using the same underlying storage
                        from utils.database import AsyncInMemoryCollection as _AIC

                        self.users = _AIC(sync_db._sync_users)
                        self.apis = _AIC(sync_db._sync_apis)
                        self.endpoints = _AIC(sync_db._sync_endpoints)
                        self.groups = _AIC(sync_db._sync_groups)
                        self.roles = _AIC(sync_db._sync_roles)
                        self.subscriptions = _AIC(sync_db._sync_subscriptions)
                        self.routings = _AIC(sync_db._sync_routings)
                        self.credit_defs = _AIC(sync_db._sync_credit_defs)
                        self.user_credits = _AIC(sync_db._sync_user_credits)
                        self.endpoint_validations = _AIC(sync_db._sync_endpoint_validations)
                        self.settings = _AIC(sync_db._sync_settings)
                        self.revocations = _AIC(sync_db._sync_revocations)
                        self.vault_entries = _AIC(sync_db._sync_vault_entries)
                        self.tiers = _AIC(sync_db._sync_tiers)
                        self.user_tier_assignments = _AIC(sync_db._sync_user_tier_assignments)
                        self.rate_limit_rules = _AIC(sync_db._sync_rate_limit_rules)

                    def get_collection(self, name):
                        # Check if collection already exists
                        if name in self._sync.list_collection_names():
                            # Return existing collection
                            sync_coll = getattr(self._sync, name)
                        else:
                            # Create new collection
                            sync_coll = self._sync.create_collection(name)
                        from utils.database import AsyncInMemoryCollection as _AIC
                        return _AIC(sync_coll)

                    def __getitem__(self, name):
                        return self.get_collection(name)

                    def __getattr__(self, name):
                        try:
                            return super().__getattribute__(name)
                        except AttributeError:
                            return self.get_collection(name)

                    def list_collection_names(self):
                        return self._sync.list_collection_names()

                    def get_database(self):
                        return self

                self.db = _AsyncDBView(_sync_db.db)
                logger.info('Async Memory-only mode: Sharing in-memory data via async wrappers')
                return
            except Exception:
                # Fallback to independent async DB (should not happen in tests)
                self.client = None
                self.db_existed = False
                self.db = InMemoryDB(async_mode=True)
                logger.info('Async Memory-only mode: Using isolated in-memory collections')
                return

        mongo_hosts = os.getenv('MONGO_DB_HOSTS')
        replica_set_name = os.getenv('MONGO_REPLICA_SET_NAME')
        mongo_user = os.getenv('MONGO_DB_USER')
        mongo_pass = os.getenv('MONGO_DB_PASSWORD')

        if not mongo_user or not mongo_pass:
            raise RuntimeError(
                'MONGO_DB_USER and MONGO_DB_PASSWORD are required when MEM_OR_EXTERNAL != MEM. '
                'Set these environment variables to secure your MongoDB connection.'
            )

        host_list = [host.strip() for host in mongo_hosts.split(',') if host.strip()]
        self.db_existed = True

        if len(host_list) > 1 and replica_set_name:
            connection_uri = f'mongodb://{mongo_user}:{mongo_pass}@{",".join(host_list)}/doorman?replicaSet={replica_set_name}'
        else:
            connection_uri = f'mongodb://{mongo_user}:{mongo_pass}@{",".join(host_list)}/doorman'

        if AsyncIOMotorClient is None:
            raise RuntimeError(
                'motor is required for async MongoDB mode; install motor or set MEM_OR_EXTERNAL=MEM'
            )
        self.client = AsyncIOMotorClient(
            connection_uri, serverSelectionTimeoutMS=5000, maxPoolSize=100, minPoolSize=5
        )
        self.db = self.client.get_database()

    def get_collection(self, name):
        if self.memory_only:
            # motor.db.get_collection equivalent for memory view
            return self.db.get_collection(name)
        return self.db.get_collection(name)

    async def initialize_collections(self):
        """Initialize collections and default data."""
        if self.memory_only:
            from utils.database import database

            database.initialize_collections()
            return

        collections = [
            'users',
            'apis',
            'endpoints',
            'groups',
            'roles',
            'subscriptions',
            'routings',
            'credit_defs',
            'user_credits',
            'endpoint_validations',
            'settings',
            'revocations',
            'vault_entries',
        ]

        existing_collections = await self.db.list_collection_names()

        for collection in collections:
            if collection not in existing_collections:
                self.db_existed = False
                await self.db.create_collection(collection)
                logger.debug(f'Created collection: {collection}')

        if not self.db_existed:
            admin_exists = await self.db.users.find_one({'username': 'admin'})
            if not admin_exists:
                email = os.getenv('DOORMAN_ADMIN_EMAIL') or 'admin@doorman.dev'
                pwd = os.getenv('DOORMAN_ADMIN_PASSWORD')
                if not pwd:
                    raise RuntimeError(
                        'DOORMAN_ADMIN_PASSWORD is required for admin initialization'
                    )
                pwd_hash = password_util.hash_password(pwd)
                await self.db.users.insert_one(
                    {
                        'username': 'admin',
                        'email': email,
                        'password': pwd_hash,
                        'role': 'admin',
                        'groups': ['ALL', 'admin'],
                        'rate_limit_duration': 1,
                        'rate_limit_duration_type': 'second',
                        'throttle_duration': 1,
                        'throttle_duration_type': 'second',
                        'throttle_wait_duration': 0,
                        'throttle_wait_duration_type': 'second',
                        'custom_attributes': {'custom_key': 'custom_value'},
                        'active': True,
                        'throttle_queue_limit': 1,
                        'throttle_enabled': None,
                        'ui_access': True,
                    }
                )

        try:
            adm = await self.db.users.find_one({'username': 'admin'})
            if adm and adm.get('ui_access') is not True:
                await self.db.users.update_one({'username': 'admin'}, {'$set': {'ui_access': True}})
            if adm and not adm.get('password'):
                env_pwd = os.getenv('DOORMAN_ADMIN_PASSWORD')
                if env_pwd:
                    await self.db.users.update_one(
                        {'username': 'admin'},
                        {'$set': {'password': password_util.hash_password(env_pwd)}},
                    )
                    logger.warning('Admin user lacked password; set from DOORMAN_ADMIN_PASSWORD')
                else:
                    raise RuntimeError(
                        'Admin user missing password and DOORMAN_ADMIN_PASSWORD not set'
                    )
            # Ensure admin email matches env if provided
            env_email = os.getenv('DOORMAN_ADMIN_EMAIL')
            if adm and env_email and adm.get('email') != env_email:
                await self.db.users.update_one(
                    {'username': 'admin'}, {'$set': {'email': env_email}}
                )
        except Exception:
            pass

        admin_role = await self.db.roles.find_one({'role_name': 'admin'})
        if not admin_role:
            await self.db.roles.insert_one(
                {
                    'role_name': 'admin',
                    'role_description': 'Administrator role',
                    'manage_users': True,
                    'manage_apis': True,
                    'manage_endpoints': True,
                    'manage_groups': True,
                    'manage_roles': True,
                    'manage_routings': True,
                    'manage_gateway': True,
                    'manage_subscriptions': True,
                    'manage_credits': True,
                    'manage_auth': True,
                    'view_logs': True,
                    'export_logs': True,
                    'manage_security': True,
                }
            )

        admin_group = await self.db.groups.find_one({'group_name': 'admin'})
        if not admin_group:
            await self.db.groups.insert_one(
                {
                    'group_name': 'admin',
                    'group_description': 'Administrator group with full access',
                    'api_access': [],
                }
            )

        all_group = await self.db.groups.find_one({'group_name': 'ALL'})
        if not all_group:
            await self.db.groups.insert_one(
                {
                    'group_name': 'ALL',
                    'group_description': 'Default group with access to all APIs',
                    'api_access': [],
                }
            )

    async def create_indexes(self):
        """Create database indexes for performance."""
        if self.memory_only:
            logger.debug('Async Memory-only mode: Skipping MongoDB index creation')
            return

        from pymongo import ASCENDING, IndexModel

        await self.db.apis.create_indexes(
            [
                IndexModel([('api_id', ASCENDING)], unique=True),
                IndexModel([('api_name', ASCENDING), ('api_version', ASCENDING)]),
            ]
        )

        await self.db.endpoints.create_indexes(
            [
                IndexModel(
                    [
                        ('endpoint_method', ASCENDING),
                        ('api_name', ASCENDING),
                        ('api_version', ASCENDING),
                        ('endpoint_uri', ASCENDING),
                    ],
                    unique=True,
                )
            ]
        )

        await self.db.users.create_indexes(
            [
                IndexModel([('username', ASCENDING)], unique=True),
                IndexModel([('email', ASCENDING)], unique=True),
            ]
        )

        await self.db.groups.create_indexes([IndexModel([('group_name', ASCENDING)], unique=True)])

        await self.db.roles.create_indexes([IndexModel([('role_name', ASCENDING)], unique=True)])

        await self.db.subscriptions.create_indexes(
            [IndexModel([('username', ASCENDING)], unique=True)]
        )

        await self.db.routings.create_indexes(
            [IndexModel([('client_key', ASCENDING)], unique=True)]
        )

        await self.db.credit_defs.create_indexes(
            [IndexModel([('api_credit_group', ASCENDING)], unique=True)]
        )
        await self.db.user_credits.create_indexes(
            [IndexModel([('username', ASCENDING)], unique=True)]
        )

        await self.db.endpoint_validations.create_indexes(
            [IndexModel([('endpoint_id', ASCENDING)], unique=True)]
        )

        await self.db.vault_entries.create_indexes(
            [
                IndexModel([('username', ASCENDING), ('key_name', ASCENDING)], unique=True),
                IndexModel([('username', ASCENDING)]),
            ]
        )

    def is_memory_only(self) -> bool:
        """Check if running in memory-only mode."""
        return self.memory_only

    def get_mode_info(self) -> dict:
        """Get information about database mode."""
        return {
            'mode': 'memory_only' if self.memory_only else 'mongodb',
            'mongodb_connected': not self.memory_only and self.client is not None,
            'collections_available': not self.memory_only,
            'cache_backend': os.getenv('MEM_OR_EXTERNAL', os.getenv('MEM_OR_REDIS', 'REDIS')),
        }

    async def close(self):
        """Close database connections gracefully."""
        if self.client:
            self.client.close()
            logger.info('Async MongoDB connections closed')


async_database = AsyncDatabase()

if async_database.memory_only:
    # Already sharing the same DB; no snapshot hydration needed
    pass

if async_database.memory_only:
    db = async_database.db
    mongodb_client = None
    api_collection = db.apis
    endpoint_collection = db.endpoints
    group_collection = db.groups
    role_collection = db.roles
    routing_collection = db.routings
    subscriptions_collection = db.subscriptions
    user_collection = db.users
    credit_def_collection = db.credit_defs
    user_credit_collection = db.user_credits
    endpoint_validation_collection = db.endpoint_validations
    revocations_collection = db.revocations
    vault_entries_collection = db.vault_entries
else:
    db = async_database.db
    mongodb_client = async_database.client
    api_collection = db.apis
    endpoint_collection = db.endpoints
    group_collection = db.groups
    role_collection = db.roles
    routing_collection = db.routings
    subscriptions_collection = db.subscriptions
    user_collection = db.users
    credit_def_collection = db.credit_defs
    user_credit_collection = db.user_credits
    endpoint_validation_collection = db.endpoint_validations
    try:
        revocations_collection = db.revocations
    except Exception:
        revocations_collection = None
    try:
        vault_entries_collection = db.vault_entries
    except Exception:
        vault_entries_collection = None


async def close_async_database_connections():
    """Close all async database connections for graceful shutdown."""
    await async_database.close()
