import json
import random
import unittest
import time
import requests

class TestPygate(unittest.TestCase):
    base_url = "http://localhost:3002"
    token = None
    api_name = None
    endpoint_path = None
    group_name = None
    role_name = None

    @classmethod
    def setUpClass(cls):
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

    def test_01_auth_calls(self):
        response = requests.post(f"{self.base_url}/platform/authorization", 
                                 json={"email": "admin@pygate.org", "password": "password1"})
        self.assertEqual(response.status_code, 200)

        TestPygate.token = response.json().get('access_token') 
        self.assertIsNotNone(TestPygate.token)

        response = requests.get(f"{self.base_url}/platform/authorization/status",
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

    def test_02_create_user(self):
        if not TestPygate.token:
            self.fail("Auth token is missing")

        response = requests.post(f"{self.base_url}/platform/user", 
                                 headers={"Authorization": f"Bearer {TestPygate.token}"},
                                 json={
                                     "username": "newuser" + str(time.time()), 
                                     "email": "newuser" + str(time.time()) + "@pygate.org", 
                                     "password": "newpass", 
                                     "role": "user"
                                 })
        self.assertEqual(response.status_code, 201)

    def test_03_onboard_api(self):
        """Step 3: Onboard an API"""
        if not TestPygate.token:
            self.fail("Auth token is missing")

        TestPygate.api_name = "test" + "".join(random.sample("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", 8))
        
        response = requests.post(f"{self.base_url}/platform/api", 
                                 headers={"Authorization": f"Bearer {TestPygate.token}"},
                                 json={
                                     "api_name": TestPygate.api_name,
                                     "api_version": "v1", 
                                     "api_description": "Test API", 
                                     "api_servers": ["https://fake-json-api.mock.beeceptor.com/"], 
                                     "api_type": "REST"
                                 })
        self.assertEqual(response.status_code, 201)

    def test_04_onboard_endpoint(self):
        if not TestPygate.token:
            self.fail("Auth token is missing")

        TestPygate.endpoint_path = "/users"

        response = requests.post(f"{self.base_url}/platform/endpoint", 
                                 headers={"Authorization": f"Bearer {TestPygate.token}"},
                                 json={
                                     "api_name": TestPygate.api_name,
                                     "api_version": "v1", 
                                     "endpoint_uri": TestPygate.endpoint_path,
                                     "endpoint_method": "GET"
                                 })
        self.assertEqual(response.status_code, 201)

    def test_05_gateway_call(self):
        response = requests.get(f"{self.base_url}/api/rest/" + TestPygate.api_name + "/v1" + TestPygate.endpoint_path.replace("{userId}", "2"))
        self.assertEqual(response.status_code, 200)

    def test_06_get_api(self):
        response = requests.get(f"{self.base_url}/platform/api/" + TestPygate.api_name + "/v1",
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

    def test_07_get_all_apis(self):
        response = requests.get(f"{self.base_url}/platform/api/all",
                                headers={"Authorization": f"Bearer {TestPygate.token}"},
                                params={"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, 200)

    def test_08_api_endpoints(self):
        response = requests.get(f"{self.base_url}/platform/endpoint/api/" + TestPygate.api_name + "/v1",
                                headers={"Authorization": f"Bearer {TestPygate.token}"}) 
        self.assertEqual(response.status_code, 200)

    def test_09_create_group(self):
        TestPygate.group_name = "testgroup" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/group", 
                                 headers={"Authorization": f"Bearer {TestPygate.token}"},
                                    json={
                                        "group_name": TestPygate.group_name, 
                                        "group_description": "Test group"
                                    })
        
        self.assertEqual(response.status_code, 201)

    def test_10_get_groups(self):
        response = requests.get(f"{self.base_url}/platform/group/all",
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

    def test_11_get_group(self):
        response = requests.get(f"{self.base_url}/platform/group/" + TestPygate.group_name,
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

    def test_12_create_role(self):
        TestPygate.role_name = "testrole" + str(time.time())
        response = requests.post(f"{self.base_url}/platform/role", 
                                 headers={"Authorization": f"Bearer {TestPygate.token}"},
                                    json={
                                        "role_name": TestPygate.role_name,
                                        "role_description": "Test role",
                                        "manage_users": False,
                                        "manage_apis": False,
                                        "manage_endpoints": False,
                                        "manage_groups": False,
                                        "manage_roles": False
                                    })
        self.assertEqual(response.status_code, 201)

    def test_13_get_roles(self):
        response = requests.get(f"{self.base_url}/platform/role/all",
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

    def test_14_get_role(self):
        response = requests.get(f"{self.base_url}/platform/role/" + TestPygate.role_name,
                                headers={"Authorization": f"Bearer {TestPygate.token}"})
        self.assertEqual(response.status_code, 200)

def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(TestPygate("test_01_auth_calls"))
    test_suite.addTest(TestPygate("test_02_create_user"))
    test_suite.addTest(TestPygate("test_03_onboard_api"))
    test_suite.addTest(TestPygate("test_04_onboard_endpoint"))
    test_suite.addTest(TestPygate("test_05_gateway_call"))
    test_suite.addTest(TestPygate("test_06_get_api"))
    test_suite.addTest(TestPygate("test_07_get_all_apis"))
    test_suite.addTest(TestPygate("test_08_api_endpoints"))
    test_suite.addTest(TestPygate("test_09_create_group"))
    test_suite.addTest(TestPygate("test_10_get_groups"))
    test_suite.addTest(TestPygate("test_11_get_group"))
    test_suite.addTest(TestPygate("test_12_create_role"))
    test_suite.addTest(TestPygate("test_13_get_roles"))
    test_suite.addTest(TestPygate("test_14_get_role"))
    return test_suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())