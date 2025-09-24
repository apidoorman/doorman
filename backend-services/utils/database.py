"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from pymongo import MongoClient, IndexModel, ASCENDING
from utils import password_util
from dotenv import load_dotenv
import os
import uuid
import copy
import json

load_dotenv()

class Database:
    def __init__(self):
        # If running in memory-only mode, use in-memory collections so the
        # application can still function (e.g., admin login) without MongoDB.
        # Unified flag: MEM_OR_EXTERNAL (MEM|REDIS). Backward-compatible alias: MEM_OR_REDIS.
        mem_flag = os.getenv("MEM_OR_EXTERNAL")
        if mem_flag is None:
            mem_flag = os.getenv("MEM_OR_REDIS", "MEM")
        self.memory_only = str(mem_flag).upper() == "MEM"
        if self.memory_only:
            self.client = None
            self.db_existed = False
            self.db = InMemoryDB()
            print("Memory-only mode: Using in-memory collections")
            return
        mongo_hosts = os.getenv("MONGO_DB_HOSTS")
        replica_set_name = os.getenv("MONGO_REPLICA_SET_NAME")
        host_list = [host.strip() for host in mongo_hosts.split(',') if host.strip()]
        self.db_existed = True
        if len(host_list) > 1 and replica_set_name:
            connection_uri = f"mongodb://{','.join(host_list)}/doorman?replicaSet={replica_set_name}"
        else:
            connection_uri = f"mongodb://{','.join(host_list)}/doorman"
        self.client = MongoClient(
            connection_uri,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=100,
            minPoolSize=5
        )
        self.db = self.client.get_database()
    def initialize_collections(self):
        if self.memory_only:
            # Ensure core collections and seed admin user/role/group in memory
            users = self.db.users
            roles = self.db.roles
            groups = self.db.groups
            # Seed role 'admin'
            if not roles.find_one({"role_name": "admin"}):
                roles.insert_one({
                    "role_name": 'admin',
                    "role_description": "admin role",
                    "manage_users": True,
                    "manage_apis": True,
                    "manage_endpoints": True,
                    "manage_groups": True,
                    "manage_roles": True,
                    "manage_routings": True,
                    "manage_gateway": True,
                    "manage_subscriptions": True,
                    "manage_credits": True
                })
            # Seed groups 'admin' and 'ALL'
            if not groups.find_one({"group_name": "admin"}):
                groups.insert_one({
                    "group_name": "admin",
                    "group_description": "Administrator group with full access",
                    "api_access": []
                })
            if not groups.find_one({"group_name": "ALL"}):
                groups.insert_one({
                    "group_name": "ALL",
                    "group_description": "Default group with access to all APIs",
                    "api_access": []
                })
            # Seed admin user if missing
            if not users.find_one({"username": "admin"}):
                users.insert_one({
                    "username": "admin",
                    "email": os.getenv("STARTUP_ADMIN_EMAIL"),
                    "password": password_util.hash_password(os.getenv("STARTUP_ADMIN_PASSWORD")),
                    "role": "admin",
                    "groups": ["ALL", "admin"],
                    "rate_limit_duration": 2000000,
                    "rate_limit_duration_type": "minute",
                    "throttle_duration": 100000000,
                    "throttle_duration_type": "second",
                    "throttle_wait_duration": 5000000,
                    "throttle_wait_duration_type": "seconds",
                    "custom_attributes": {"custom_key": "custom_value"},
                    "active": True
                })
            # Demo data seeding: public APIs + endpoints (idempotent)
            apis = self.db.apis
            endpoints = self.db.endpoints
            demo_apis = [
                {
                    "api_name": "customers", "api_version": "v1",
                    "api_description": "Customers API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8080"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                },
                {
                    "api_name": "orders", "api_version": "v1",
                    "api_description": "Orders API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8081"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                },
                {
                    "api_name": "billing", "api_version": "v1",
                    "api_description": "Billing API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8082"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                },
                {
                    "api_name": "weather", "api_version": "v1",
                    "api_description": "Weather API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8083"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                },
                {
                    "api_name": "news", "api_version": "v1",
                    "api_description": "News API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8084"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                },
                {
                    "api_name": "crypto", "api_version": "v1",
                    "api_description": "Crypto Prices API", "api_allowed_roles": ["admin"],
                    "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8085"],
                    "api_type": "REST", "api_allowed_retry_count": 0
                }
            ]
            for api in demo_apis:
                if not apis.find_one({"api_name": api["api_name"], "api_version": api["api_version"]}):
                    api_doc = dict(api)
                    api_doc["api_id"] = str(uuid.uuid4())
                    api_doc["api_path"] = f"/{api['api_name']}/{api['api_version']}"
                    apis.insert_one(api_doc)
                    # Seed 1-2 endpoints for each API
                    for ep in [
                        {"method": "GET", "uri": "/status", "desc": f"Get {api['api_name']} status"},
                        {"method": "GET", "uri": "/list", "desc": f"List {api['api_name']}"}
                    ]:
                        if not endpoints.find_one({
                            "api_name": api["api_name"], "api_version": api["api_version"],
                            "endpoint_method": ep["method"], "endpoint_uri": ep["uri"]
                        }):
                            endpoints.insert_one({
                                "api_name": api["api_name"],
                                "api_version": api["api_version"],
                                "endpoint_method": ep["method"],
                                "endpoint_uri": ep["uri"],
                                "endpoint_description": ep["desc"],
                                "api_id": api_doc["api_id"],
                                "endpoint_id": str(uuid.uuid4())
                            })
            # Seed a few gateway-like log entries so they appear in UI logging
            try:
                from datetime import datetime
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                # Respect LOGS_DIR env; default to backend-services/platform-logs
                env_logs = os.getenv("LOGS_DIR")
                logs_dir = os.path.abspath(env_logs) if env_logs else os.path.join(base_dir, "platform-logs")
                os.makedirs(logs_dir, exist_ok=True)
                log_path = os.path.join(logs_dir, "doorman.log")
                now = datetime.now()
                entries = []
                samples = [
                    ("customers", "/customers/v1/list"),
                    ("orders", "/orders/v1/status"),
                    ("weather", "/weather/v1/status"),
                ]
                for api_name, ep in samples:
                    ts = now.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                    rid = str(uuid.uuid4())
                    msg = f"{rid} | Username: admin | From: 127.0.0.1:54321 | Endpoint: GET {ep} | Total time: 42ms"
                    entries.append(f"{ts} - doorman.gateway - INFO - {msg}\n")
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.writelines(entries)
            except Exception:
                pass
            print("Memory-only mode: Core data initialized (admin user/role/groups)")
            return
        collections = ['users', 'apis', 'endpoints', 'groups', 'roles', 'subscriptions', 'routings', 'credit_defs', 'user_credits', 'endpoint_validations', 'settings']
        for collection in collections:
            if collection not in self.db.list_collection_names():
                self.db_existed = False
                self.db.create_collection(collection)
                print(f'Created collection: {collection}')
        if not self.db_existed:
            if not self.db.users.find_one({"username": "admin"}):
                self.db.users.insert_one({
                    "username": "admin",
                    "email": os.getenv("STARTUP_ADMIN_EMAIL"),
                    "password": password_util.hash_password(os.getenv("STARTUP_ADMIN_PASSWORD")),
                    "role": "admin",
                    "groups": ["ALL", "admin"],
                    "rate_limit_duration": 2000000,
                    "rate_limit_duration_type": "minute",
                    "throttle_duration": 100000000,
                    "throttle_duration_type": "second",
                    "throttle_wait_duration": 5000000,
                    "throttle_wait_duration_type": "seconds",
                    "custom_attributes": {
                        "custom_key": "custom_value"
                    },
                    "active": True
                })
            if not self.db.roles.find_one({"role_name": "admin"}):
                self.db.roles.insert_one({
                    "role_name": 'admin',
                    "role_description": "admin role",
                    "manage_users": True,
                    "manage_apis": True,
                    "manage_endpoints": True,
                    "manage_groups": True,
                    "manage_roles": True,
                    "manage_routings": True,
                    "manage_gateway": True,
                    "manage_subscriptions": True,
                    "manage_security": True
                })
            if not self.db.groups.find_one({"group_name": "admin"}):
                self.db.groups.insert_one({
                    "group_name": "admin",
                    "group_description": "Administrator group with full access",
                    "api_access": []
                })
            if not self.db.groups.find_one({"group_name": "ALL"}):
                self.db.groups.insert_one({
                    "group_name": "ALL",
                    "group_description": "Default group with access to all APIs",
                    "api_access": []
                })
            # Demo data seeding for MongoDB: public APIs + endpoints when DB is new
            apis = self.db.apis
            endpoints = self.db.endpoints
            if apis.count_documents({}) == 0:
                demo_apis = [
                    {"api_name": "customers", "api_version": "v1", "api_description": "Customers API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8080"], "api_type": "REST", "api_allowed_retry_count": 0},
                    {"api_name": "orders", "api_version": "v1", "api_description": "Orders API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8081"], "api_type": "REST", "api_allowed_retry_count": 0},
                    {"api_name": "billing", "api_version": "v1", "api_description": "Billing API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8082"], "api_type": "REST", "api_allowed_retry_count": 0},
                    {"api_name": "weather", "api_version": "v1", "api_description": "Weather API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8083"], "api_type": "REST", "api_allowed_retry_count": 0},
                    {"api_name": "news", "api_version": "v1", "api_description": "News API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8084"], "api_type": "REST", "api_allowed_retry_count": 0},
                    {"api_name": "crypto", "api_version": "v1", "api_description": "Crypto Prices API", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://localhost:8085"], "api_type": "REST", "api_allowed_retry_count": 0}
                ]
                for api in demo_apis:
                    api_doc = dict(api)
                    api_doc["api_id"] = str(uuid.uuid4())
                    api_doc["api_path"] = f"/{api['api_name']}/{api['api_version']}"
                    apis.insert_one(api_doc)
                    for ep in [
                        {"method": "GET", "uri": "/status", "desc": f"Get {api['api_name']} status"},
                        {"method": "GET", "uri": "/list", "desc": f"List {api['api_name']}"}
                    ]:
                        endpoints.insert_one({
                            "api_name": api["api_name"],
                            "api_version": api["api_version"],
                            "endpoint_method": ep["method"],
                            "endpoint_uri": ep["uri"],
                            "endpoint_description": ep["desc"],
                            "api_id": api_doc["api_id"],
                            "endpoint_id": str(uuid.uuid4())
                        })

    def create_indexes(self):
        if self.memory_only:
            # No-op for in-memory collections, but keep method for parity
            print("Memory-only mode: Skipping MongoDB index creation")
            return
        self.db.apis.create_indexes([
            IndexModel([("api_id", ASCENDING)], unique=True),
            IndexModel([("name", ASCENDING), ("version", ASCENDING)])
        ])
        self.db.endpoints.create_indexes([
            IndexModel([("endpoint_method", ASCENDING), ("api_name", ASCENDING), ("api_version", ASCENDING), ("endpoint_uri", ASCENDING)], unique=True),
        ])
        self.db.users.create_indexes([
            IndexModel([("username", ASCENDING)], unique=True),
            IndexModel([("email", ASCENDING)], unique=True)
        ])
        self.db.groups.create_indexes([
            IndexModel([("group_name", ASCENDING)], unique=True)
        ])
        self.db.roles.create_indexes([
            IndexModel([("role_name", ASCENDING)], unique=True)
        ])
        self.db.subscriptions.create_indexes([
            IndexModel([("username", ASCENDING)], unique=True)
        ])
        self.db.routings.create_indexes([
            IndexModel([("client_key", ASCENDING)], unique=True)
        ])
        self.db.credit_defs.create_indexes([
            IndexModel([("api_credit_group", ASCENDING)], unique=True),
            IndexModel([("username", ASCENDING)], unique=True)
        ])
        self.db.endpoint_validations.create_indexes([
            IndexModel([("endpoint_id", ASCENDING)], unique=True)
        ])
    
    def is_memory_only(self) -> bool:
        return self.memory_only
    
    def get_mode_info(self) -> dict:
        return {
            'mode': 'memory_only' if self.memory_only else 'mongodb',
            'mongodb_connected': not self.memory_only and self.client is not None,
            'collections_available': not self.memory_only,
            'cache_backend': os.getenv("MEM_OR_EXTERNAL", os.getenv("MEM_OR_REDIS", "REDIS"))
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
        # Store deep copies to avoid outside mutation
        self._docs = [copy.deepcopy(d) for d in docs]

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

    def to_list(self, length=None):
        data = [copy.deepcopy(d) for d in self._docs]
        if length is None:
            return data
        try:
            # Motor's to_list(length=None) returns all; mimic length semantics
            return data[: int(length)]
        except Exception:
            return data


class InMemoryCollection:
    def __init__(self, name):
        self.name = name
        self._docs = []

    def _match(self, doc, query):
        if not query:
            return True
        for k, v in query.items():
            if isinstance(v, dict):
                # minimal $and/$or/$in not supported; keep simple equality for now
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
        query = query or {}
        for d in self._docs:
            if self._match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None):
        query = query or {}
        matches = [d for d in self._docs if self._match(d, query)]
        return InMemoryCursor(matches)

    def insert_one(self, doc):
        new_doc = copy.deepcopy(doc)
        if '_id' not in new_doc:
            new_doc['_id'] = str(uuid.uuid4())
        self._docs.append(new_doc)
        return InMemoryInsertResult(new_doc['_id'])

    def update_one(self, query, update):
        set_data = update.get('$set', {}) if isinstance(update, dict) else {}
        push_data = update.get('$push', {}) if isinstance(update, dict) else {}
        for i, d in enumerate(self._docs):
            if self._match(d, query):
                updated = copy.deepcopy(d)
                # Apply $set fields
                if set_data:
                    updated.update(set_data)
                # Apply $push for list fields (create list if missing)
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

    def delete_one(self, query):
        for i, d in enumerate(self._docs):
            if self._match(d, query):
                del self._docs[i]
                return InMemoryDeleteResult(1)
        return InMemoryDeleteResult(0)

    def count_documents(self, query=None):
        query = query or {}
        return len([1 for d in self._docs if self._match(d, query)])

    def create_indexes(self, *args, **kwargs):
        # No-op in memory
        return []


class InMemoryDB:
    def __init__(self):
        # Create collections
        self.users = InMemoryCollection('users')
        self.apis = InMemoryCollection('apis')
        self.endpoints = InMemoryCollection('endpoints')
        self.groups = InMemoryCollection('groups')
        self.roles = InMemoryCollection('roles')
        self.subscriptions = InMemoryCollection('subscriptions')
        self.routings = InMemoryCollection('routings')
        self.credit_defs = InMemoryCollection('credit_defs')
        self.user_credits = InMemoryCollection('user_credits')
        self.endpoint_validations = InMemoryCollection('endpoint_validations')
        self.settings = InMemoryCollection('settings')

    def list_collection_names(self):
        return [
            'users', 'apis', 'endpoints', 'groups', 'roles',
            'subscriptions', 'routings', 'credit_defs', 'user_credits',
            'endpoint_validations', 'settings'
        ]

    def create_collection(self, name):
        if name not in self.list_collection_names():
            setattr(self, name, InMemoryCollection(name))
        return getattr(self, name)

    def get_database(self):
        return self

    # Export all collections to a serializable dict
    def dump_data(self) -> dict:
        def coll_docs(coll: InMemoryCollection):
            return [copy.deepcopy(d) for d in coll._docs]

        return {
            'users': coll_docs(self.users),
            'apis': coll_docs(self.apis),
            'endpoints': coll_docs(self.endpoints),
            'groups': coll_docs(self.groups),
            'roles': coll_docs(self.roles),
            'subscriptions': coll_docs(self.subscriptions),
            'routings': coll_docs(self.routings),
            'credit_defs': coll_docs(self.credit_defs),
            'user_credits': coll_docs(self.user_credits),
            'endpoint_validations': coll_docs(self.endpoint_validations),
            'settings': coll_docs(self.settings),
        }

    # Load collections from a dict (overwrites existing in-memory data)
    def load_data(self, data: dict):
        def load_coll(coll: InMemoryCollection, docs: list):
            coll._docs = [copy.deepcopy(d) for d in (docs or [])]

        load_coll(self.users, data.get('users', []))
        load_coll(self.apis, data.get('apis', []))
        load_coll(self.endpoints, data.get('endpoints', []))
        load_coll(self.groups, data.get('groups', []))
        load_coll(self.roles, data.get('roles', []))
        load_coll(self.subscriptions, data.get('subscriptions', []))
        load_coll(self.routings, data.get('routings', []))
        load_coll(self.credit_defs, data.get('credit_defs', []))
        load_coll(self.user_credits, data.get('user_credits', []))
        load_coll(self.endpoint_validations, data.get('endpoint_validations', []))
        load_coll(self.settings, data.get('settings', []))


database = Database()
database.initialize_collections()
database.create_indexes()
if database.memory_only:
    # Wire up in-memory collections so services can operate normally
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
