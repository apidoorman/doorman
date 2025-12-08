"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pymongo import MongoClient, IndexModel, ASCENDING
from dotenv import load_dotenv
import os
import uuid
import copy
import json
import threading
import secrets
import string as _string
import logging

from utils import password_util
from utils import chaos_util

load_dotenv()

logger = logging.getLogger('doorman.gateway')

def _build_admin_seed_doc(email: str, pwd_hash: str) -> dict:
    """Canonical admin bootstrap document used for both memory and Mongo modes.

    Ensures identical defaults across storage backends.
    """
    return {
        'username': 'admin',
        'email': email,
        'password': pwd_hash,
        'role': 'admin',
        'groups': ['ALL', 'admin'],
        'ui_access': True,
        # Admin seed defaults for rate/throttle as canonical values
        'rate_limit_duration': 1,
        'rate_limit_duration_type': 'second',
        'throttle_duration': 1,
        'throttle_duration_type': 'second',
        'throttle_wait_duration': 0,
        'throttle_wait_duration_type': 'second',
        'throttle_queue_limit': 1,
        'throttle_enabled': None,
        'custom_attributes': {'custom_key': 'custom_value'},
        'active': True,
    }

class Database:
    def __init__(self):

        mem_flag = os.getenv('MEM_OR_EXTERNAL')
        if mem_flag is None:
            mem_flag = os.getenv('MEM_OR_REDIS', 'MEM')
        self.memory_only = str(mem_flag).upper() == 'MEM'
        if self.memory_only:
            self.client = None
            self.db_existed = False
            self.db = InMemoryDB()
            logger.info('Memory-only mode: Using in-memory collections')
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
            connection_uri = f"mongodb://{mongo_user}:{mongo_pass}@{','.join(host_list)}/doorman?replicaSet={replica_set_name}"
        else:
            connection_uri = f"mongodb://{mongo_user}:{mongo_pass}@{','.join(host_list)}/doorman"

        self.client = MongoClient(
            connection_uri,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=100,
            minPoolSize=5
        )
        self.db = self.client.get_database()
    def initialize_collections(self):
        if self.memory_only:
            # Resolve admin seed credentials consistently across modes (no auto-generation)
            def _admin_seed_creds():
                email = os.getenv('DOORMAN_ADMIN_EMAIL') or 'admin@doorman.dev'
                pwd = os.getenv('DOORMAN_ADMIN_PASSWORD')
                if not pwd:
                    raise RuntimeError('DOORMAN_ADMIN_PASSWORD is required for admin initialization')
                return email, password_util.hash_password(pwd)

            users = self.db.users
            roles = self.db.roles
            groups = self.db.groups

            if not roles.find_one({'role_name': 'admin'}):
                roles.insert_one({
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
                    'manage_security': True,
                    'view_logs': True,
                    'export_logs': True,
                    'ui_access': True
                })

            if not groups.find_one({'group_name': 'admin'}):
                groups.insert_one({
                    'group_name': 'admin',
                    'group_description': 'Administrator group with full access',
                    'api_access': []
                })
            if not groups.find_one({'group_name': 'ALL'}):
                groups.insert_one({
                    'group_name': 'ALL',
                    'group_description': 'Default group with access to all APIs',
                    'api_access': []
                })

            if not users.find_one({'username': 'admin'}):
                _email, _pwd_hash = _admin_seed_creds()
                users.insert_one(_build_admin_seed_doc(_email, _pwd_hash))

            try:
                adm = users.find_one({'username': 'admin'})
                if adm and adm.get('ui_access') is not True:
                    users.update_one({'username': 'admin'}, {'$set': {'ui_access': True}})
            except Exception:
                pass

            try:
                from datetime import datetime
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                env_logs = os.getenv('LOGS_DIR')
                logs_dir = os.path.abspath(env_logs) if env_logs else os.path.join(base_dir, 'platform-logs')
                os.makedirs(logs_dir, exist_ok=True)
                log_path = os.path.join(logs_dir, 'doorman.log')
                now = datetime.now()
                entries = []
                samples = [
                    ('customers', '/customers/v1/list'),
                    ('orders', '/orders/v1/status'),
                    ('weather', '/weather/v1/status'),
                ]
                for api_name, ep in samples:
                    ts = now.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                    rid = str(uuid.uuid4())
                    msg = f'{rid} | Username: admin | From: 127.0.0.1:54321 | Endpoint: GET {ep} | Total time: 42ms'
                    entries.append(f'{ts} - doorman.gateway - INFO - {msg}\n')
                with open(log_path, 'a', encoding='utf-8') as lf:
                    lf.writelines(entries)
            except Exception:
                pass
            logger.info('Memory-only mode: Core data initialized (admin user/role/groups)')
            return
        collections = ['users', 'apis', 'endpoints', 'groups', 'roles', 'subscriptions', 'routings', 'credit_defs', 'user_credits', 'endpoint_validations', 'settings', 'revocations', 'vault_entries', 'tiers', 'user_tier_assignments']
        for collection in collections:
            if collection not in self.db.list_collection_names():
                self.db_existed = False
                self.db.create_collection(collection)
                logger.debug(f'Created collection: {collection}')
        if not self.db_existed:
            if not self.db.users.find_one({'username': 'admin'}):
                # Resolve admin seed credentials consistently across modes (no auto-generation)
                def _admin_seed_creds_mongo():
                    email = os.getenv('DOORMAN_ADMIN_EMAIL') or 'admin@doorman.dev'
                    pwd = os.getenv('DOORMAN_ADMIN_PASSWORD')
                    if not pwd:
                        raise RuntimeError('DOORMAN_ADMIN_PASSWORD is required for admin initialization')
                    return email, password_util.hash_password(pwd)
                _email, _pwd_hash = _admin_seed_creds_mongo()
                self.db.users.insert_one(_build_admin_seed_doc(_email, _pwd_hash))
        try:
            adm = self.db.users.find_one({'username': 'admin'})
            if adm and adm.get('ui_access') is not True:
                self.db.users.update_one({'username': 'admin'}, {'$set': {'ui_access': True}})
        except Exception:
            pass
        try:
            adm2 = self.db.users.find_one({'username': 'admin'})
            if adm2 and not adm2.get('password'):
                env_pwd = os.getenv('DOORMAN_ADMIN_PASSWORD')
                if env_pwd:
                    self.db.users.update_one(
                        {'username': 'admin'},
                        {'$set': {'password': password_util.hash_password(env_pwd)}}
                    )
                    logger.warning('Admin user lacked password; set from DOORMAN_ADMIN_PASSWORD')
                else:
                    raise RuntimeError('Admin user missing password and DOORMAN_ADMIN_PASSWORD not set')
        except Exception:
            pass
            if not self.db.roles.find_one({'role_name': 'admin'}):
                self.db.roles.insert_one({
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
                    'manage_security': True
                })
            if not self.db.groups.find_one({'group_name': 'admin'}):
                self.db.groups.insert_one({
                    'group_name': 'admin',
                    'group_description': 'Administrator group with full access',
                    'api_access': []
                })
            if not self.db.groups.find_one({'group_name': 'ALL'}):
                self.db.groups.insert_one({
                    'group_name': 'ALL',
                    'group_description': 'Default group with access to all APIs',
                    'api_access': []
                })

    def create_indexes(self):
        if self.memory_only:
            logger.debug('Memory-only mode: Skipping MongoDB index creation')
            return
        self.db.apis.create_indexes([
            IndexModel([('api_id', ASCENDING)], unique=True),
            IndexModel([('name', ASCENDING), ('version', ASCENDING)])
        ])
        self.db.endpoints.create_indexes([
            IndexModel([('endpoint_method', ASCENDING), ('api_name', ASCENDING), ('api_version', ASCENDING), ('endpoint_uri', ASCENDING)], unique=True),
        ])
        self.db.users.create_indexes([
            IndexModel([('username', ASCENDING)], unique=True),
            IndexModel([('email', ASCENDING)], unique=True)
        ])
        self.db.groups.create_indexes([
            IndexModel([('group_name', ASCENDING)], unique=True)
        ])
        self.db.roles.create_indexes([
            IndexModel([('role_name', ASCENDING)], unique=True)
        ])
        self.db.subscriptions.create_indexes([
            IndexModel([('username', ASCENDING)], unique=True)
        ])
        self.db.routings.create_indexes([
            IndexModel([('client_key', ASCENDING)], unique=True)
        ])
        self.db.credit_defs.create_indexes([
            IndexModel([('api_credit_group', ASCENDING)], unique=True),
            IndexModel([('username', ASCENDING)], unique=True)
        ])
        self.db.endpoint_validations.create_indexes([
            IndexModel([('endpoint_id', ASCENDING)], unique=True)
        ])
        self.db.vault_entries.create_indexes([
            IndexModel([('username', ASCENDING), ('key_name', ASCENDING)], unique=True),
            IndexModel([('username', ASCENDING)])
        ])
        self.db.tiers.create_indexes([
            IndexModel([('tier_id', ASCENDING)], unique=True),
            IndexModel([('name', ASCENDING)])
        ])
        self.db.user_tier_assignments.create_indexes([
            IndexModel([('user_id', ASCENDING)], unique=True),
            IndexModel([('tier_id', ASCENDING)])
        ])

    def is_memory_only(self) -> bool:
        return self.memory_only

    def get_mode_info(self) -> dict:
        return {
            'mode': 'memory_only' if self.memory_only else 'mongodb',
            'mongodb_connected': not self.memory_only and self.client is not None,
            'collections_available': not self.memory_only,
            'cache_backend': os.getenv('MEM_OR_EXTERNAL', os.getenv('MEM_OR_REDIS', 'REDIS'))
        }

class InMemoryInsertResult:
    def __init__(self, inserted_id):
        self.acknowledged = True
        self.inserted_id = inserted_id

class InMemoryUpdateResult:
    def __init__(self, modified_count):
        self.acknowledged = True
        self.modified_count = modified_count

class InMemoryDeleteResult:
    def __init__(self, deleted_count):
        self.acknowledged = True
        self.deleted_count = deleted_count

class InMemoryCursor:
    def __init__(self, docs):

        self._docs = [copy.deepcopy(d) for d in docs]
        self._index = 0

    def sort(self, field, direction=1):
        reverse = direction == -1
        self._docs.sort(key=lambda d: d.get(field), reverse=reverse)
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        if n is not None:
            self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter([copy.deepcopy(d) for d in self._docs])

    def __aiter__(self):
        """Async iterator support for compatibility with async/await patterns"""
        self._index = 0
        return self

    async def __anext__(self):
        """Async iteration - returns next document"""
        if self._index >= len(self._docs):
            raise StopAsyncIteration
        doc = copy.deepcopy(self._docs[self._index])
        self._index += 1
        return doc

    def to_list(self, length=None):
        data = [copy.deepcopy(d) for d in self._docs]
        if length is None:
            return data
        try:

            return data[: int(length)]
        except Exception:
            return data

class InMemoryCollection:
    def __init__(self, name):
        self.name = name
        self._docs = []
        self._lock = threading.RLock()

    def _match(self, doc, query):
        if not query:
            return True
        for k, v in query.items():
            # Handle $or operator
            if k == '$or':
                if not isinstance(v, list):
                    continue
                or_match = False
                for or_query in v:
                    if self._match(doc, or_query):
                        or_match = True
                        break
                if not or_match:
                    return False
            elif isinstance(v, dict):
                if '$in' in v:
                    if doc.get(k) not in v['$in']:
                        return False
                else:
                    if doc.get(k) != v:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def find_one(self, query=None):
        """Find one document (synchronous)"""
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            query = query or {}
            for d in self._docs:
                if self._match(d, query):
                    return copy.deepcopy(d)
            return None

    # Alias for backward compatibility
    find_one_sync = find_one

    def find(self, query=None):
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            query = query or {}
            matches = [d for d in self._docs if self._match(d, query)]
            return InMemoryCursor(matches)

    def insert_one(self, doc):
        """Insert one document (synchronous)"""
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            new_doc = copy.deepcopy(doc)
            if '_id' not in new_doc:
                new_doc['_id'] = str(uuid.uuid4())
            self._docs.append(new_doc)
            return InMemoryInsertResult(new_doc['_id'])

    # Alias for backward compatibility
    insert_one_sync = insert_one

    def update_one(self, query, update):
        """Update one document (synchronous)"""
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            set_data = update.get('$set', {}) if isinstance(update, dict) else {}
            push_data = update.get('$push', {}) if isinstance(update, dict) else {}
            for i, d in enumerate(self._docs):
                if self._match(d, query):
                    updated = copy.deepcopy(d)

                    if set_data:
                        for k, v in set_data.items():

                            if isinstance(k, str) and '.' in k:
                                parts = k.split('.')
                                cur = updated
                                for part in parts[:-1]:
                                    nxt = cur.get(part)
                                    if not isinstance(nxt, dict):
                                        nxt = {}
                                        cur[part] = nxt
                                    cur = nxt
                                cur[parts[-1]] = v
                            else:
                                updated[k] = v

                    if push_data:
                        for k, v in push_data.items():
                            cur = updated.get(k)
                            if cur is None or not isinstance(cur, list):
                                updated[k] = [v]
                            else:
                                updated[k].append(v)
                    self._docs[i] = updated
                    return InMemoryUpdateResult(1)
            return InMemoryUpdateResult(0)

    # Alias for backward compatibility
    update_one_sync = update_one

    def delete_one(self, query):
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            for i, d in enumerate(self._docs):
                if self._match(d, query):
                    del self._docs[i]
                    return InMemoryDeleteResult(1)
            return InMemoryDeleteResult(0)

    def count_documents(self, query=None):
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            query = query or {}
            return len([1 for d in self._docs if self._match(d, query)])

    def replace_one(self, query, replacement):
        """Replace entire document matching query"""
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            for i, d in enumerate(self._docs):
                if self._match(d, query):
                    new_doc = copy.deepcopy(replacement)
                    # Preserve _id if not in replacement
                    if '_id' not in new_doc and '_id' in d:
                        new_doc['_id'] = d['_id']
                    self._docs[i] = new_doc
                    return InMemoryUpdateResult(1)
            return InMemoryUpdateResult(0)

    def find_one_and_update(self, query, update, return_document=False):
        """Find and update a document, optionally returning the updated document"""
        if chaos_util.should_fail('mongo'):
            chaos_util.burn_error_budget('mongo')
            raise RuntimeError('chaos: simulated mongo outage')
        with self._lock:
            set_data = update.get('$set', {}) if isinstance(update, dict) else {}
            for i, d in enumerate(self._docs):
                if self._match(d, query):
                    updated = copy.deepcopy(d)
                    if set_data:
                        for k, v in set_data.items():
                            if isinstance(k, str) and '.' in k:
                                parts = k.split('.')
                                cur = updated
                                for part in parts[:-1]:
                                    nxt = cur.get(part)
                                    if not isinstance(nxt, dict):
                                        nxt = {}
                                        cur[part] = nxt
                                    cur = nxt
                                cur[parts[-1]] = v
                            else:
                                updated[k] = v
                    self._docs[i] = updated
                    return copy.deepcopy(updated) if return_document else None
            return None

    def create_indexes(self, *args, **kwargs):

        return []


class AsyncInMemoryCollection:
    """Async wrapper around InMemoryCollection for async/await compatibility"""
    
    def __init__(self, sync_collection):
        self._sync = sync_collection
        self.name = sync_collection.name
    
    async def find_one(self, query=None):
        """Async find_one"""
        return self._sync.find_one(query)
    
    def find(self, query=None):
        """Returns cursor (sync method, but cursor supports async iteration)"""
        return self._sync.find(query)
    
    async def insert_one(self, doc):
        """Async insert_one"""
        return self._sync.insert_one(doc)
    
    async def update_one(self, query, update):
        """Async update_one"""
        return self._sync.update_one(query, update)
    
    async def delete_one(self, query):
        """Async delete_one"""
        return self._sync.delete_one(query)
    
    async def count_documents(self, query=None):
        """Async count_documents"""
        return self._sync.count_documents(query)
    
    async def replace_one(self, query, replacement):
        """Async replace_one"""
        return self._sync.replace_one(query, replacement)
    
    async def find_one_and_update(self, query, update, return_document=False):
        """Async find_one_and_update"""
        return self._sync.find_one_and_update(query, update, return_document)
    
    def create_indexes(self, *args, **kwargs):
        return self._sync.create_indexes(*args, **kwargs)


class InMemoryDB:
    def __init__(self, async_mode=False):
        self._async_mode = async_mode
        CollectionClass = AsyncInMemoryCollection if async_mode else InMemoryCollection
        
        # Create base sync collections
        self._sync_users = InMemoryCollection('users')
        self._sync_apis = InMemoryCollection('apis')
        self._sync_endpoints = InMemoryCollection('endpoints')
        self._sync_groups = InMemoryCollection('groups')
        self._sync_roles = InMemoryCollection('roles')
        self._sync_subscriptions = InMemoryCollection('subscriptions')
        self._sync_routings = InMemoryCollection('routings')
        self._sync_credit_defs = InMemoryCollection('credit_defs')
        self._sync_user_credits = InMemoryCollection('user_credits')
        self._sync_endpoint_validations = InMemoryCollection('endpoint_validations')
        self._sync_settings = InMemoryCollection('settings')
        self._sync_revocations = InMemoryCollection('revocations')
        self._sync_vault_entries = InMemoryCollection('vault_entries')
        self._sync_tiers = InMemoryCollection('tiers')
        self._sync_user_tier_assignments = InMemoryCollection('user_tier_assignments')
        
        # Expose as async or sync based on mode
        if async_mode:
            self.users = AsyncInMemoryCollection(self._sync_users)
            self.apis = AsyncInMemoryCollection(self._sync_apis)
            self.endpoints = AsyncInMemoryCollection(self._sync_endpoints)
            self.groups = AsyncInMemoryCollection(self._sync_groups)
            self.roles = AsyncInMemoryCollection(self._sync_roles)
            self.subscriptions = AsyncInMemoryCollection(self._sync_subscriptions)
            self.routings = AsyncInMemoryCollection(self._sync_routings)
            self.credit_defs = AsyncInMemoryCollection(self._sync_credit_defs)
            self.user_credits = AsyncInMemoryCollection(self._sync_user_credits)
            self.endpoint_validations = AsyncInMemoryCollection(self._sync_endpoint_validations)
            self.settings = AsyncInMemoryCollection(self._sync_settings)
            self.revocations = AsyncInMemoryCollection(self._sync_revocations)
            self.vault_entries = AsyncInMemoryCollection(self._sync_vault_entries)
            self.tiers = AsyncInMemoryCollection(self._sync_tiers)
            self.user_tier_assignments = AsyncInMemoryCollection(self._sync_user_tier_assignments)
        else:
            self.users = self._sync_users
            self.apis = self._sync_apis
            self.endpoints = self._sync_endpoints
            self.groups = self._sync_groups
            self.roles = self._sync_roles
            self.subscriptions = self._sync_subscriptions
            self.routings = self._sync_routings
            self.credit_defs = self._sync_credit_defs
            self.user_credits = self._sync_user_credits
            self.endpoint_validations = self._sync_endpoint_validations
            self.settings = self._sync_settings
            self.revocations = self._sync_revocations
            self.vault_entries = self._sync_vault_entries
            self.tiers = self._sync_tiers
            self.user_tier_assignments = self._sync_user_tier_assignments

    def list_collection_names(self):
        return [
            'users', 'apis', 'endpoints', 'groups', 'roles',
            'subscriptions', 'routings', 'credit_defs', 'user_credits',
            'endpoint_validations', 'settings', 'revocations', 'vault_entries',
            'tiers', 'user_tier_assignments'
        ]

    def create_collection(self, name):
        if name not in self.list_collection_names():
            setattr(self, name, InMemoryCollection(name))
        return getattr(self, name)

    def get_database(self):
        return self

    def dump_data(self) -> dict:
        def coll_docs(coll: InMemoryCollection):
            return [copy.deepcopy(d) for d in coll._docs]

        return {
            'users': coll_docs(self._sync_users),
            'apis': coll_docs(self._sync_apis),
            'endpoints': coll_docs(self._sync_endpoints),
            'groups': coll_docs(self._sync_groups),
            'roles': coll_docs(self._sync_roles),
            'subscriptions': coll_docs(self._sync_subscriptions),
            'routings': coll_docs(self._sync_routings),
            'credit_defs': coll_docs(self._sync_credit_defs),
            'user_credits': coll_docs(self._sync_user_credits),
            'endpoint_validations': coll_docs(self._sync_endpoint_validations),
            'settings': coll_docs(self._sync_settings),
            'revocations': coll_docs(self._sync_revocations),
            'vault_entries': coll_docs(self._sync_vault_entries),
            'tiers': coll_docs(self._sync_tiers),
            'user_tier_assignments': coll_docs(self._sync_user_tier_assignments),
        }

    def load_data(self, data: dict):
        def load_coll(coll: InMemoryCollection, docs: list):
            coll._docs = [copy.deepcopy(d) for d in (docs or [])]

        load_coll(self._sync_users, data.get('users', []))
        load_coll(self._sync_apis, data.get('apis', []))
        load_coll(self._sync_endpoints, data.get('endpoints', []))
        load_coll(self._sync_groups, data.get('groups', []))
        load_coll(self._sync_roles, data.get('roles', []))
        load_coll(self._sync_subscriptions, data.get('subscriptions', []))
        load_coll(self._sync_routings, data.get('routings', []))
        load_coll(self._sync_credit_defs, data.get('credit_defs', []))
        load_coll(self._sync_user_credits, data.get('user_credits', []))
        load_coll(self._sync_endpoint_validations, data.get('endpoint_validations', []))
        load_coll(self._sync_settings, data.get('settings', []))
        load_coll(self._sync_revocations, data.get('revocations', []))
        load_coll(self._sync_vault_entries, data.get('vault_entries', []))
        load_coll(self._sync_tiers, data.get('tiers', []))
        load_coll(self._sync_user_tier_assignments, data.get('user_tier_assignments', []))

database = Database()
database.initialize_collections()
database.create_indexes()
if database.memory_only:

    db = database.db
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
    db = database.db
    mongodb_client = database.client
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

def close_database_connections():
    """
    Close all database connections for graceful shutdown.
    """
    global mongodb_client
    try:
        if mongodb_client:
            mongodb_client.close()
            logger.info("MongoDB connections closed")
    except Exception as e:
        logger.warning(f"Error closing MongoDB connections: {e}")
