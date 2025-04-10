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
        self.client = MongoClient(
            os.getenv("MONGO_DB_URI"),
            serverSelectionTimeoutMS=5000,
            maxPoolSize=100,
            minPoolSize=5
        )
        self.db = self.client.get_database()
        self.initialize_collections()
        self.create_indexes()

    def initialize_collections(self):
        collections = ['users', 'apis', 'endpoints', 'groups', 'roles', 'subscriptions', 'routings']
        for collection in collections:
            if collection not in self.db.list_collection_names():
                self.db.create_collection(collection)
                print(f'Created collection: {collection}')

    def create_indexes(self):
        self.db.apis.create_indexes([
            IndexModel([("api_id", ASCENDING)], unique=True),
            IndexModel([("name", ASCENDING), ("version", ASCENDING)])
        ])

        self.db.endpoints.create_indexes([
            IndexModel([("api_id", ASCENDING)], unique=True),
            IndexModel([("api_name", ASCENDING), ("api_version", ASCENDING)], unique=True),
            IndexModel([("api_name", ASCENDING), ("api_version", ASCENDING), ("path", ASCENDING)], unique=True),
            IndexModel([("endpoint_method", ASCENDING),("api_name", ASCENDING), ("api_version", ASCENDING), ("endpoint_uri", ASCENDING)], unique=True),
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

        # TODO: Remove this before merging to master
        if self.db.users.find_one({"username": "admin"}):
            self.db.users.delete_one({"username": "admin"})
        if not self.db.users.find_one({"username": "admin"}):
            self.db.users.insert_one({
                "username": "admin",
                "email": "admin@pygate.org",
                "password": password_util.hash_password("password1"),
                "role": "admin",
                "groups": ["ALL"]
            })
        if self.db.roles.find_one({"role_name": "admin"}):
            self.db.roles.delete_one({"role_name": "admin"})
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