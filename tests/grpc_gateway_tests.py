import pytest
import json
import time
import requests
import uuid
import random
import os
import grpc
import asyncio
from concurrent import futures
import importlib
import logging
import sys

logger = logging.getLogger(__name__)

def create_echo_servicer(pb2_module, pb2_grpc_module):
    service_class = getattr(pb2_grpc_module, 'EchoServiceServicer')
    
    class EchoServicer(service_class):
        def __init__(self):
            super().__init__()
            self.pb2_module = pb2_module

        def Echo(self, request, context):
            response = self.pb2_module.EchoResponse(message=request.message)
            return response

        def EchoTwice(self, request, context):
            response = self.pb2_module.EchoResponse(message=request.message)
            return response

        def EchoThrice(self, request, context):
            response = self.pb2_module.EchoResponse(message=request.message)
            return response

    return EchoServicer()

class TestDoorman:
    base_url = "http://localhost:3002"
    csrf_token = None
    token = None
    username = None
    email = None
    password = None
    role_name = None
    group_name = None
    api_name = None
    client_key = None
    endpoint_path = None
    server = None

    @staticmethod
    def getAccessCookies():
        return {"access_token_cookie": TestDoorman.token}

    @classmethod
    def setup_class(cls):
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        cls.server.add_insecure_port('[::]:50051')
        cls.server.start()

    @classmethod
    def teardown_class(cls):
        if cls.server:
            cls.server.stop(0)

    @pytest.mark.asyncio
    @pytest.mark.order(1)
    async def test_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                json={"email": "admin@doorman.so", "password": "password1"}, verify=False)
        assert response.status_code == 200
        TestDoorman.csrf_token = response.cookies.get('csrf_access_token')
        TestDoorman.token = response.json().get('access_token') 
        assert TestDoorman.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(2)
    async def test_create_role(self):
        TestDoorman.role_name = "testrole" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/role", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "role_name": TestDoorman.role_name,
                                    "role_description": "Test role",
                                    "manage_users": True,
                                    "manage_apis": True,
                                    "manage_endpoints": True,
                                    "manage_groups": True,
                                    "manage_roles": True,
                                    "manage_subscriptions": True,
                                    "manage_routings": True,
                                    "manage_gateway": True,
                                    "manage_tokens": True
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(3)
    async def test_create_group(self):
        TestDoorman.group_name = "testgroup" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/group", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "group_name": TestDoorman.group_name, 
                                    "group_description": "Test group",
                                    "manage_apis": True,
                                    "manage_endpoints": True,
                                    "manage_routings": True,
                                    "manage_subscriptions": True,
                                    "manage_users": True,
                                    "manage_groups": True
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(4)
    async def test_create_user(self):
        TestDoorman.username = "newuser" + str(time.time())
        TestDoorman.email = "newuser" + str(time.time()) + "@doorman.so"
        TestDoorman.password = "newPassword@12345"
        response = requests.post(f"{self.base_url}/platform/user", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "username": TestDoorman.username, 
                                    "email": TestDoorman.email, 
                                    "password": TestDoorman.password, 
                                    "role": TestDoorman.role_name,
                                    "groups": [TestDoorman.group_name],
                                    "rate_limit_duration": 3,
                                    "rate_limit_duration_type": "minute",
                                    "throttle_duration": 10,
                                    "throttle_duration_type": "second",
                                    "throttle_wait_duration": 5,
                                    "throttle_wait_duration_type": "seconds",
                                    "custom_attributes": {
                                        "custom_key": "custom_value"
                                    }
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(5)
    async def test_onboard_api(self):
        TestDoorman.api_name = "test" + "".join(random.sample("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 8))
        response = requests.post(f"{self.base_url}/platform/api", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "api_name": TestDoorman.api_name,
                                    "api_version": "v1", 
                                    "api_description": "Test gRPC API", 
                                    "api_servers": ["grpc://localhost:50051"], 
                                    "api_allowed_roles": [TestDoorman.role_name],
                                    "api_allowed_groups": [TestDoorman.group_name],
                                    "api_type": "grpc",
                                    "api_status": "active",
                                    "api_ssl_enabled": False
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(6)
    async def test_upload_proto_file(self):
        proto_content = f"""
syntax = "proto3";

package {TestDoorman.api_name}_v1;

service EchoService {{
  rpc Echo (EchoRequest) returns (EchoResponse) {{}}
  rpc EchoTwice (EchoRequest) returns (EchoResponse) {{}}
  rpc EchoThrice (EchoRequest) returns (EchoResponse) {{}}
}}

message EchoRequest {{
  string message = 1;
}}

message EchoResponse {{
  string message = 1;
}}
"""
        with open("test.proto", "w") as f:
            f.write(proto_content)
        with open("test.proto", "rb") as f:
            response = requests.post(
                f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
                headers={
                    "X-CSRF-TOKEN": TestDoorman.csrf_token,
                    "Cookie": f"access_token_cookie={TestDoorman.token}"
                },
                files={
                    "file": ("test.proto", f, "application/x-protobuf")
                },
                verify=False
            )
        assert response.status_code == 200
        assert "message" in response.json()
        assert "Proto file uploaded and gRPC code generated successfully" in response.json()["message"]
        os.remove("test.proto")
        module_name = f"{TestDoorman.api_name}_v1"
        try:
            generated_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'generated')
            if generated_dir not in sys.path:
                sys.path.insert(0, generated_dir)
            pb2_module = importlib.import_module(f"{module_name}_pb2")
            pb2_grpc_module = importlib.import_module(f"{module_name}_pb2_grpc")
            logger.info(f"Generated pb2 module contents: {dir(pb2_module)}")
            logger.info(f"Generated pb2_grpc module contents: {dir(pb2_grpc_module)}")
            servicer = create_echo_servicer(pb2_module, pb2_grpc_module)
            pb2_grpc_module.add_EchoServiceServicer_to_server(servicer, TestDoorman.server)
            logger.info(f"Successfully registered EchoService with gRPC server")
        except ImportError as e:
            logger.error(f"Failed to import gRPC module: {str(e)}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.order(7)
    async def test_get_proto_file(self):
        response = requests.get(
            f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
            headers={
                "X-CSRF-TOKEN": TestDoorman.csrf_token,
                "Cookie": f"access_token_cookie={TestDoorman.token}"
            },
            verify=False
        )
        assert response.status_code == 200
        assert "message" in response.json()
        assert "Proto file retrieved successfully" in response.json()["message"]

    @pytest.mark.asyncio
    @pytest.mark.order(8)
    async def test_update_proto_file(self):
        updated_proto_content = f"""
syntax = "proto3";

package {TestDoorman.api_name}_v1;

service EchoService {{
  rpc Echo (EchoRequest) returns (EchoResponse) {{}}
  rpc EchoTwice (EchoRequest) returns (EchoResponse) {{}}
  rpc EchoThrice (EchoRequest) returns (EchoResponse) {{}}
}}

message EchoRequest {{
  string message = 1;
}}

message EchoResponse {{
  string message = 1;
}}
"""
        with open("test.proto", "w") as f:
            f.write(updated_proto_content)
        with open("test.proto", "rb") as f:
            response = requests.put(
                f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
                headers={
                    "X-CSRF-TOKEN": TestDoorman.csrf_token,
                    "Cookie": f"access_token_cookie={TestDoorman.token}"
                },
                files={
                    "proto_file": ("test.proto", f, "application/x-protobuf")
                },
                verify=False
            )
        assert response.status_code == 200
        assert "message" in response.json()
        assert "Proto file updated successfully" in response.json()["message"]
        os.remove("test.proto")
        module_name = f"{TestDoorman.api_name}_v1"
        try:
            generated_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'generated')
            if generated_dir not in sys.path:
                sys.path.insert(0, generated_dir)
            pb2_module = importlib.import_module(f"{module_name}_pb2")
            pb2_grpc_module = importlib.import_module(f"{module_name}_pb2_grpc")
            logger.info(f"Generated pb2 module contents: {dir(pb2_module)}")
            logger.info(f"Generated pb2_grpc module contents: {dir(pb2_grpc_module)}")
            servicer = create_echo_servicer(pb2_module, pb2_grpc_module)
            pb2_grpc_module.add_EchoServiceServicer_to_server(servicer, TestDoorman.server)
            logger.info(f"Successfully registered EchoService with gRPC server")
        except ImportError as e:
            logger.error(f"Failed to import gRPC module: {str(e)}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.order(9)
    async def test_onboard_endpoint(self):
        TestDoorman.endpoint_path = "/echo"
        response = requests.post(f"{self.base_url}/platform/endpoint", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "api_name": TestDoorman.api_name,
                                    "api_version": "v1", 
                                    "endpoint_uri": TestDoorman.endpoint_path,
                                    "endpoint_method": "POST",
                                    "endpoint_description": "Test gRPC endpoint",
                                    "endpoint_type": "grpc",
                                    "endpoint_service": "EchoService",
                                    "endpoint_method_name": "Echo",
                                    "endpoint_status": "active"
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(10)
    async def test_create_routing(self):
        TestDoorman.client_key = "test_routing" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/routing",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "routing_name": "test_routing",
                                    "routing_description": "Test routing",
                                    "client_key": TestDoorman.client_key,
                                    "routing_servers": ["grpc://localhost:50051"],
                                    "routing_type": "grpc",
                                    "routing_status": "active"
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(11)
    async def test_subscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/subscribe", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "username": TestDoorman.username, 
                                    "api_name": TestDoorman.api_name, 
                                    "api_version": "v1",
                                    "client_key": TestDoorman.client_key
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(12)
    async def test_re_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                json={"email": TestDoorman.email, "password": TestDoorman.password}, verify=False)
        assert response.status_code == 200
        TestDoorman.csrf_token = response.cookies.get('csrf_access_token')
        TestDoorman.token = response.json().get('access_token') 
        assert TestDoorman.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(13)
    async def test_basic_grpc_call(self):
        response = requests.post(
            f"{self.base_url}/api/grpc/{TestDoorman.api_name}",
            headers={
                "X-CSRF-TOKEN": TestDoorman.csrf_token,
                "Cookie": f"access_token_cookie={TestDoorman.token}",
                "X-API-Version": "v1",
                "client-key": TestDoorman.client_key,
                "Content-Type": "application/json"
            },
            json={
                "method": "EchoService.Echo",
                "message": {
                    "message": "Hello, gRPC!"
                }
            },
            verify=False
        )
        
        logger.info(f"gRPC call response status: {response.status_code}")
        logger.info(f"gRPC call response body: {response.text}")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(14)
    async def test_grpc_call_without_proto(self):
        response = requests.delete(
            f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
            headers={
                "X-CSRF-TOKEN": TestDoorman.csrf_token,
                "Cookie": f"access_token_cookie={TestDoorman.token}"
            },
            verify=False
        )
        assert response.status_code == 200

        response = requests.post(
            f"{self.base_url}/api/grpc/{TestDoorman.api_name}",
            headers={
                "X-CSRF-TOKEN": TestDoorman.csrf_token,
                "Cookie": f"access_token_cookie={TestDoorman.token}",
                "X-API-Version": "v1",
                "client-key": TestDoorman.client_key,
                "Content-Type": "application/json"
            },
            json={
                "method": "EchoService.Echo",
                "message": {
                    "message": "Hello, gRPC!"
                }
            },
            verify=False
        )
        assert response.status_code == 404
        assert "error_code" in response.json()
        assert response.json()["error_code"] == "GTW012"
        assert "Proto file not found" in response.json()["error_message"]

        proto_content = f"""
syntax = "proto3";

package {TestDoorman.api_name}_v1;

service EchoService {{
  rpc Echo (EchoRequest) returns (EchoResponse) {{}}
}}

message EchoRequest {{
  string message = 1;
}}

message EchoResponse {{
  string message = 1;
}}
"""
        with open("test.proto", "w") as f:
            f.write(proto_content)
        with open("test.proto", "rb") as f:
            response = requests.post(
                f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
                headers={
                    "X-CSRF-TOKEN": TestDoorman.csrf_token,
                    "Cookie": f"access_token_cookie={TestDoorman.token}"
                },
                files={
                    "file": ("test.proto", f, "application/x-protobuf")
                },
                verify=False
            )
        assert response.status_code == 200
        os.remove("test.proto")

    @pytest.mark.asyncio
    @pytest.mark.order(15)
    async def test_grpc_call_invalid_method(self):
        response = requests.post(
            f"{self.base_url}/api/grpc/{TestDoorman.api_name}",
            headers={
                "X-CSRF-TOKEN": TestDoorman.csrf_token,
                "Cookie": f"access_token_cookie={TestDoorman.token}",
                "X-API-Version": "v1",
                "client-key": TestDoorman.client_key,
                "Content-Type": "application/json"
            },
            json={
                "method": "InvalidService.InvalidMethod",
                "message": {
                    "message": "Hello, gRPC!"
                }
            },
            verify=False
        )
        assert response.status_code == 500
        assert "error_code" in response.json()
        assert response.json()["error_code"] == "GTW006"
        assert "Service InvalidService not found" in response.json()["error_message"]

    @pytest.mark.asyncio
    @pytest.mark.order(16)
    async def test_unsubscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/unsubscribe", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "username": TestDoorman.username, 
                                    "api_name": TestDoorman.api_name, 
                                    "api_version": "v1"
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(17)
    async def test_delete_routing(self):
        response = requests.delete(f"{self.base_url}/platform/routing/{TestDoorman.client_key}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(18)
    async def test_delete_endpoint(self):
        response = requests.delete(f"{self.base_url}/platform/endpoint/POST/{TestDoorman.api_name}/v1{TestDoorman.endpoint_path}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(19)
    async def test_delete_proto_files(self):
        response = requests.delete(f"{self.base_url}/platform/api/proto/{TestDoorman.api_name}/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        generated_dir = os.path.join(project_root, 'generated')
        module_name = f"{TestDoorman.api_name}_v1"
        
        generated_files = [
            f"{module_name}_pb2.py",
            f"{module_name}_pb2.pyc",
            f"{module_name}_pb2_grpc.py",
            f"{module_name}_pb2_grpc.pyc"
        ]
        
        for file in generated_files:
            file_path = os.path.join(generated_dir, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed generated file: {file_path}")

        proto_dir = os.path.join(project_root, 'proto')
        proto_file = f"{module_name}.proto"
        proto_path = os.path.join(proto_dir, proto_file)
        if os.path.exists(proto_path):
            os.remove(proto_path)
            logger.info(f"Removed proto file: {proto_path}")

    @pytest.mark.asyncio
    @pytest.mark.order(20)
    async def test_delete_api(self):
        response = requests.delete(f"{self.base_url}/platform/api/{TestDoorman.api_name}/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(21)
    async def test_delete_group(self):
        response = requests.delete(f"{self.base_url}/platform/group/{TestDoorman.group_name}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(22)
    async def test_delete_role(self):
        response = requests.delete(f"{self.base_url}/platform/role/{TestDoorman.role_name}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(23)
    async def test_delete_user(self):
        response = requests.delete(f"{self.base_url}/platform/user/{TestDoorman.username}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200
        