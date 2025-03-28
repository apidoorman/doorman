import json
import random
import time
import requests
import pytest
import asyncio

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

    @staticmethod
    def getAccessCookies():
        return {"access_token_cookie": TestPygate.token}

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls):
        for _ in range(5):
            try:
                response = requests.get(f"{cls.base_url}/platform/status")
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

        response = requests.get(f"{self.base_url}/platform/authorization/status",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(2)
    async def test_create_user(self):
        TestPygate.username = "newuser" + str(time.time())
        TestPygate.email = "newuser" + str(time.time()) + "@pygate.org"
        TestPygate.password = "newpass"
        response = requests.post(f"{self.base_url}/platform/user", 
                                 cookies=TestPygate.getAccessCookies(),
                                 json={
                                     "username": TestPygate.username, 
                                     "email": TestPygate.email, 
                                     "password": TestPygate.password, 
                                     "role": "admin",
                                     "groups": ["ALL"]
                                 })
        assert response.status_code == 201

    @pytest.mark.asyncio
    @pytest.mark.order(3)
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
    @pytest.mark.order(4)
    async def test_get_groups(self):
        response = requests.get(f"{self.base_url}/platform/group/all",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(5)
    async def test_get_group(self):
        response = requests.get(f"{self.base_url}/platform/group/" + TestPygate.group_name,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(6)
    async def test_create_role(self):
        TestPygate.role_name = "testrole" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/role", 
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "role_name": TestPygate.role_name,
                                    "role_description": "Test role",
                                    "manage_users": False,
                                    "manage_apis": False,
                                    "manage_endpoints": False,
                                    "manage_groups": False,
                                    "manage_roles": False
                                })
        assert response.status_code == 201

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
                                     "endpoint_method": "GET"
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

        response = requests.get(f"{self.base_url}/platform/authorization/status",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(13)
    async def test_gateway_call(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(14)
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
    @pytest.mark.order(15)
    async def test_re_gateway_call(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"),
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.order(16)
    async def test_get_api(self):
        response = requests.get(f"{self.base_url}/platform/api/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(17)
    async def test_get_all_apis(self):
        response = requests.get(f"{self.base_url}/platform/api/all",
                                cookies=TestPygate.getAccessCookies(),
                                params={"page": 1, "page_size": 10})
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(18)
    async def test_api_endpoints(self):
        response = requests.get(f"{self.base_url}/platform/endpoint/api/" + TestPygate.api_name + "/v1",
                                cookies=TestPygate.getAccessCookies()) 
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(19)
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
    @pytest.mark.order(20)
    async def test_update_user(self):
        TestPygate.email  = "newuser" + str(time.time()) + "@pygate.org"
        response = requests.put(f"{self.base_url}/platform/user/" + TestPygate.username,
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "email": TestPygate.email,
                                    "role": "admin",
                                    "groups": ["ALL", "ALL_UPDATED"]
                                })
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(21)
    async def test_update_password(self):
        new_password = "newpass123"
        response = requests.put(f"{self.base_url}/platform/user/" + TestPygate.username + "/update-password",
                                cookies=TestPygate.getAccessCookies(),
                                json={
                                    "old_password": TestPygate.password,
                                    "new_password": new_password
                                })
        TestPygate.password = new_password
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(22)
    async def test_re_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                 json={"email": TestPygate.email, "password": TestPygate.password})
        assert response.status_code == 200

        TestPygate.token = response.json().get('access_token') 
        assert TestPygate.token is not None

        response = requests.get(f"{self.base_url}/platform/authorization/status",
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.order(23)
    async def test_get_user(self):
        response = requests.get(f"{self.base_url}/platform/user/" + TestPygate.username,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.order(24)
    async def test_get_user_by_email(self):
        response = requests.get(f"{self.base_url}/platform/user/email/" + TestPygate.email,
                                cookies=TestPygate.getAccessCookies())
        assert response.status_code == 200

if __name__ == '__main__':
    pytest.main()