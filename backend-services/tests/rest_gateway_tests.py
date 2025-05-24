import random
import time
import requests
import pytest

class TestDoorman:
    base_url = "http://localhost:3002"
    token = None
    api_name = None
    endpoint_path = None
    group_name = None
    role_name = None
    username = None
    email = None
    password = None
    client_key = None
    csrf_token = None

    @staticmethod
    def getAccessCookies():
        return {"access_token_cookie": TestDoorman.token}

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        for _ in range(5):
            try:
                response = requests.get(f"{cls.base_url}/api/status", verify=False)
                if response.status_code == 200:
                    print("Server started successfully")
                    break
            except requests.exceptions.ConnectionError:
                print("Failed to connect to the server, retrying...")
                time.sleep(2)
        else:
            print("Failed to connect to the server after multiple attempts")
            raise RuntimeError("doorman is not running")

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
                                    "manage_gateway": True
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(3)
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
                                    "groups": ["ALL"],
                                    "rate_limit_duration": 2,
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
    @pytest.mark.order(4)
    async def test_create_group(self):
        TestDoorman.group_name = "testgroup" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/group", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "group_name": TestDoorman.group_name, 
                                    "group_description": "Test group"
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(5)
    async def test_get_groups(self):
        response = requests.get(f"{self.base_url}/platform/group/all",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(6)
    async def test_get_group(self):
        response = requests.get(f"{self.base_url}/platform/group/" + TestDoorman.group_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(7)
    async def test_get_roles(self):
        response = requests.get(f"{self.base_url}/platform/role/all",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(8)
    async def test_get_role(self):
        response = requests.get(f"{self.base_url}/platform/role/" + TestDoorman.role_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(9)
    async def test_onboard_api(self):
        TestDoorman.api_name = "test" + "".join(random.sample("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 8))
        response = requests.post(f"{self.base_url}/platform/api", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                 json={
                                     "api_name": TestDoorman.api_name,
                                     "api_version": "v1", 
                                     "api_description": "Test API", 
                                     "api_servers": ["https://fake-json-api.mock.beeceptor.com"], 
                                     "api_allowed_roles": [TestDoorman.role_name],
                                     "api_allowed_groups": ["ALL", TestDoorman.group_name],
                                     "api_type": "REST"
                                 }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(10)
    async def test_onboard_endpoint(self):

        TestDoorman.endpoint_path = "/users"

        response = requests.post(f"{self.base_url}/platform/endpoint", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                 json={
                                    "api_name": TestDoorman.api_name,
                                    "api_version": "v1", 
                                    "endpoint_uri": TestDoorman.endpoint_path,
                                    "endpoint_method": "GET",
                                    "endpoint_description": "Test endpoint",
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
                                        "api_version": "v1"
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
    async def test_create_routing(self):
        TestDoorman.client_key = "test_routing" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/routing",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "routing_name": "test_routing",
                                    "routing_description": "Test routing",
                                    "client_key": TestDoorman.client_key,
                                    "routing_servers": ["https://fake-json-api.mock.beeceptor.com/"],
                                }, verify=False)
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(14)
    async def test_get_routing(self):
        response = requests.get(f"{self.base_url}/platform/routing/{TestDoorman.client_key}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(15)
    async def test_update_routing(self):
        response = requests.put(f"{self.base_url}/platform/routing/{TestDoorman.client_key}",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "routing_description": "Updated routing description"
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(16)
    async def test_gateway_call_client_key(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path.replace("{userId}", "2"),
                                headers={"client-key": TestDoorman.client_key, "X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
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
    async def test_gateway_call_regular_route(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path.replace("{userId}", "2"),
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(19)
    async def test_gateway_call_rate_limited(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path.replace("{userId}", "2"),
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 429


    @pytest.mark.asyncio
    @pytest.mark.order(20)
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
    @pytest.mark.order(21)
    async def test_re_gateway_call(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path.replace("{userId}", "2"),
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.order(22)
    async def test_get_api(self):
        response = requests.get(f"{self.base_url}/platform/api/" + TestDoorman.api_name + "/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(23)
    async def test_get_all_apis(self):
        response = requests.get(f"{self.base_url}/platform/api/all",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                params={"page": 1, "page_size": 10}, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(24)
    async def test_api_endpoints(self):
        response = requests.get(f"{self.base_url}/platform/endpoint/" + TestDoorman.api_name + "/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False) 
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(25)
    async def test_re_subscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/subscribe", 
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                    json={
                                        "username": TestDoorman.username, 
                                        "api_name": TestDoorman.api_name, 
                                        "api_version": "v1"
                                    }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(26)
    async def test_update_user(self):
        TestDoorman.email  = "newuser" + str(time.time()) + "@doorman.so"
        response = requests.put(f"{self.base_url}/platform/user/" + TestDoorman.username,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "email": TestDoorman.email,
                                    "groups": ["ALL", "ALL_UPDATED"]
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(27)
    async def test_update_password(self):
        new_password = "newerPassword@6789"
        response = requests.put(f"{self.base_url}/platform/user/" + TestDoorman.username + "/update-password",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "old_password": TestDoorman.password,
                                    "new_password": new_password
                                }, verify=False)
        TestDoorman.password = new_password
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(28)
    async def test_re_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                 json={"email": TestDoorman.email, "password": TestDoorman.password}, verify=False)
        assert response.status_code == 200
        TestDoorman.csrf_token = response.cookies.get('csrf_access_token')
        TestDoorman.token = response.json().get('access_token') 
        assert TestDoorman.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(29)
    async def test_get_user(self):
        response = requests.get(f"{self.base_url}/platform/user/" + TestDoorman.username,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(30)
    async def test_get_user_by_email(self):
        response = requests.get(f"{self.base_url}/platform/user/email/" + TestDoorman.email,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(31)
    async def test_auth_refresh_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization/refresh",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        TestDoorman.csrf_token = response.cookies.get('csrf_access_token')
        TestDoorman.token = response.json().get('refresh_token')
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(32)
    async def test_update_api(self):
        response = requests.put(f"{self.base_url}/platform/api/" + TestDoorman.api_name + "/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "api_description": "Updated API description",
                                    "api_allowed_roles": [TestDoorman.role_name],
                                    "api_allowed_groups": ["ALL", TestDoorman.group_name]
                                }, verify=False)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(33)
    async def test_update_endpoint(self):
        response = requests.put(f"{self.base_url}/platform/endpoint/GET/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "endpoint_description": "Updated endpoint description"
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(34)
    async def test_delete_endpoint(self):
        response = requests.delete(f"{self.base_url}/platform/endpoint/GET/" + TestDoorman.api_name + "/v1" + TestDoorman.endpoint_path,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(35)
    async def test_delete_api(self):
        response = requests.delete(f"{self.base_url}/platform/api/" + TestDoorman.api_name + "/v1",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(36)
    async def test_update_group(self):
        response = requests.put(f"{self.base_url}/platform/group/" + TestDoorman.group_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "group_description": "Updated group description"
                                }, verify=False)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(37)
    async def test_delete_group(self):
        response = requests.delete(f"{self.base_url}/platform/group/" + TestDoorman.group_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(38)
    async def test_update_role(self):
        response = requests.put(f"{self.base_url}/platform/role/" + TestDoorman.role_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(),
                                json={
                                    "role_description": "Updated role description"
                                }, verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(39)
    async def test_clear_all_caches(self):
        response = requests.delete(f"{self.base_url}/api/caches",
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(40)
    async def test_delete_role(self):
        response = requests.delete(f"{self.base_url}/platform/role/" + TestDoorman.role_name,
                                headers={"X-CSRF-TOKEN": TestDoorman.csrf_token},
                                cookies=TestDoorman.getAccessCookies(), verify=False)
        assert response.status_code == 200