"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from pymongo import MongoClient, IndexModel, ASCENDING
from utils import password_util
from dotenv import load_dotenv
import os

load_dotenv()

class Database:
    def __init__(self):
        mongo_hosts = os.getenv("MONGO_DB_HOSTS")
        replica_set_name = os.getenv("MONGO_REPLICA_SET_NAME")

        host_list = [host.strip() for host in mongo_hosts.split(',') if host.strip()]
        self.db_existed = True

        if len(host_list) > 1 and replica_set_name:
            connection_uri = f"mongodb://{','.join(host_list)}/pygate?replicaSet={replica_set_name}"
        else:
            connection_uri = f"mongodb://{','.join(host_list)}/pygate"

        self.client = MongoClient(
            connection_uri,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=100,
            minPoolSize=5
        )
        self.db = self.client.get_database()

    def initialize_collections(self):
        collections = ['users', 'apis', 'endpoints', 'groups', 'roles', 'subscriptions', 'routings', 'token_defs', 'user_tokens']
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
                    "manage_subscriptions": True
                })

    def create_indexes(self):
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

        self.db.token_defs.create_indexes([
            IndexModel([("api_token_group", ASCENDING)], unique=True)
        ])

        self.db.token_defs.create_indexes([
            IndexModel([("username", ASCENDING)], unique=True)
        ])

database = Database()

database.initialize_collections()
database.create_indexes()

db = database.db
api_collection = db.apis
endpoint_collection = db.endpoints
group_collection = db.groups
role_collection = db.roles
routing_collection = db.routings
subscriptions_collection = db.subscriptions
user_collection = db.users
token_def_collection = db.token_defs
user_token_collection = db.user_tokens