import random
import time
import requests
import pytest

class TestPygate:
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

    @staticmethod
    def getAccessCookies():
        return {"access_token_cookie": TestPygate.token}

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        for _ in range(5):
            try:
                response = requests.get(f"{cls.base_url}/api/status/rest")
                if response.status_code == 200:
                    print("Server started successfully")
                    break
            except requests.exceptions.ConnectionError:
                print("Failed to connect to the server, retrying...")
                time.sleep(2)
        else:
            print("Failed to connect to the server after multiple attempts")
            raise RuntimeError("pygate is not running")

    @pytest.mark.asyncio
    @pytest.mark.order(1)
    async def test_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                json={"email": "admin@pygate.org", "password": "password1"})
        assert response.status_code == 200

        TestPygate.token = response.json().get('access_token') 
        assert TestPygate.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(2)
    async def test_create_role(self):
        TestPygate.role_name = "testrole" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/role", 
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "role_name": TestPygate.role_name,
                                    "role_description": "Test role",
                                    "manage_users": True,
                                    "manage_apis": True,
                                    "manage_endpoints": True,
                                    "manage_groups": True,
                                    "manage_roles": True,
                                    "manage_subscriptions": True,
                                    "manage_routings": True,
                                    "manage_gateway": True
                                })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(3)
    async def test_create_user(self):
        TestPygate.username = "newuser" + str(time.time())
        TestPygate.email = "newuser" + str(time.time()) + "@pygate.org"
        TestPygate.password = "newPassword@12345"
        response = requests.post(f"{self.base_url}/platform/user", 
                                 cookies=TestPygate.getAccessCookies(),
                                 json={
                                    "username": TestPygate.username, 
                                    "email": TestPygate.email, 
                                    "password": TestPygate.password, 
                                    "role": TestPygate.role_name,
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
                                 })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(4)
    async def test_create_group(self):
        TestPygate.group_name = "testgroup" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/group", 
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "group_name": TestPygate.group_name, 
                                    "group_description": "Test group"
                                })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(5)
    async def test_get_groups(self):
        response = requests.get(f"{self.base_url}/platform/group/all",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(6)
    async def test_get_group(self):
        response = requests.get(f"{self.base_url}/platform/group/" + TestPygate.group_name,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(7)
    async def test_get_roles(self):
        response = requests.get(f"{self.base_url}/platform/role/all",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(8)
    async def test_get_role(self):
        response = requests.get(f"{self.base_url}/platform/role/" + TestPygate.role_name,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(9)
    async def test_onboard_api(self):
        TestPygate.api_name = "test" + "".join(random.sample("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 8))
        response = requests.post(f"{self.base_url}/platform/api", 
                                 cookies=TestPygate.getAccessCookies(),
                                 json={
                                     "api_name": TestPygate.api_name,
                                     "api_version": "v1", 
                                     "api_description": "Test API", 
                                     "api_servers": ["https://fake-json-api.mock.beeceptor.com/"], 
                                     "api_allowed_roles": [TestPygate.role_name],
                                     "api_allowed_groups": ["ALL", TestPygate.group_name],
                                     "api_type": "REST"
                                 })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(10)
    async def test_onboard_endpoint(self):

        TestPygate.endpoint_path = "/users"

        response = requests.post(f"{self.base_url}/platform/endpoint", 
                                 cookies=TestPygate.getAccessCookies(),
                                 json={
                                    "api_name": TestPygate.api_name,
                                    "api_version": "v1", 
                                    "endpoint_uri": TestPygate.endpoint_path,
                                    "endpoint_method": "GET",
                                    "endpoint_description": "Test endpoint",
                                 })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(11)
    async def test_subscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/subscribe", 
                                 cookies=TestPygate.getAccessCookies(),
                                    json={
                                        "username": TestPygate.username, 
                                        "api_name": TestPygate.api_name, 
                                        "api_version": "v1"
                                    })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(12)
    async def test_re_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                json={"email": TestPygate.email, "password": TestPygate.password})
        assert response.status_code == 200

        TestPygate.token = response.json().get('access_token') 
        assert TestPygate.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(13)
    async def test_create_routing(self):
        TestPygate.client_key = "test_routing" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/routing",
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "routing_name": "test_routing",
                                    "routing_description": "Test routing",
                                    "client_key": TestPygate.client_key,
                                    "routing_servers": ["https://fake-json-api.mock.beeceptor.com/"],
                                })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(14)
    async def test_get_routing(self):
        response = requests.get(f"{self.base_url}/platform/routing/{TestPygate.client_key}",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(15)
    async def test_update_routing(self):
        response = requests.put(f"{self.base_url}/platform/routing/{TestPygate.client_key}",
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "routing_description": "Updated routing description"
                                })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(16)
    async def test_gateway_call_client_key(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                headers={"client-key": TestPygate.client_key},
                                cookies=TestPygate.getAccessCookies(),
                                )
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(17)
    async def test_delete_routing(self):
        response = requests.delete(f"{self.base_url}/platform/routing/{TestPygate.client_key}",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(18)
    async def test_gateway_call_regular_route(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(19)
    async def test_gateway_call_rate_limited(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 429


    @pytest.mark.asyncio
    @pytest.mark.order(20)
    async def test_unsubscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/unsubscribe", 
                                    cookies=TestPygate.getAccessCookies(),
                                    json={
                                        "username": TestPygate.username, 
                                        "api_name": TestPygate.api_name, 
                                        "api_version": "v1"
                                    })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(21)
    async def test_re_gateway_call(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.order(22)
    async def test_get_api(self):
        response = requests.get(f"{self.base_url}/platform/api/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(23)
    async def test_get_all_apis(self):
        response = requests.get(f"{self.base_url}/platform/api/all",
                                cookies=TestPygate.getAccessCookies(),
                                params={"page": 1, "page_size": 10})
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(24)
    async def test_api_endpoints(self):
        response = requests.get(f"{self.base_url}/platform/endpoint/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies()) 
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(25)
    async def test_re_subscribe(self):
        response = requests.post(f"{self.base_url}/platform/subscription/subscribe", 
                                 cookies=TestPygate.getAccessCookies(),
                                    json={
                                        "username": TestPygate.username, 
                                        "api_name": TestPygate.api_name, 
                                        "api_version": "v1"
                                    })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(26)
    async def test_update_user(self):
        TestPygate.email  = "newuser" + str(time.time()) + "@pygate.org"
        response = requests.put(f"{self.base_url}/platform/user/" + TestPygate.username,
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "email": TestPygate.email,
                                    "groups": ["ALL", "ALL_UPDATED"]
                                })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(27)
    async def test_update_password(self):
        new_password = "newerPassword@6789"
        response = requests.put(f"{self.base_url}/platform/user/" + TestPygate.username + "/update-password",
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "old_password": TestPygate.password,
                                    "new_password": new_password
                                })
        TestPygate.password = new_password
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(28)
    async def test_re_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                 json={"email": TestPygate.email, "password": TestPygate.password})
        assert response.status_code == 200

        TestPygate.token = response.json().get('access_token') 
        assert TestPygate.token is not None

    @pytest.mark.asyncio
    @pytest.mark.order(29)
    async def test_get_user(self):
        response = requests.get(f"{self.base_url}/platform/user/" + TestPygate.username,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(30)
    async def test_get_user_by_email(self):
        response = requests.get(f"{self.base_url}/platform/user/email/" + TestPygate.email,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(31)
    async def test_auth_refresh_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization/refresh",
                                cookies=TestPygate.getAccessCookies())
        TestPygate.token = response.json().get('refresh_token')
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(32)
    async def test_update_api(self):
        response = requests.put(f"{self.base_url}/platform/api/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "api_description": "Updated API description",
                                    "api_allowed_roles": [TestPygate.role_name],
                                    "api_allowed_groups": ["ALL", TestPygate.group_name]
                                })
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(33)
    async def test_update_endpoint(self):
        response = requests.put(f"{self.base_url}/platform/endpoint/GET/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path,
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "endpoint_description": "Updated endpoint description"
                                })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(34)
    async def test_delete_endpoint(self):
        response = requests.delete(f"{self.base_url}/platform/endpoint/GET/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(35)
    async def test_delete_api(self):
        response = requests.delete(f"{self.base_url}/platform/api/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(36)
    async def test_update_group(self):
        response = requests.put(f"{self.base_url}/platform/group/" + TestPygate.group_name,
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "group_description": "Updated group description"
                                })
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(37)
    async def test_delete_group(self):
        response = requests.delete(f"{self.base_url}/platform/group/" + TestPygate.group_name,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(38)
    async def test_update_role(self):
        response = requests.put(f"{self.base_url}/platform/role/" + TestPygate.role_name,
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "role_description": "Updated role description"
                                })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(39)
    async def test_clear_all_caches(self):
        response = requests.delete(f"{self.base_url}/api/caches",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(40)
    async def test_delete_role(self):
        response = requests.delete(f"{self.base_url}/platform/role/" + TestPygate.role_name,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

if __name__ == '__main__':
    pytest.main()