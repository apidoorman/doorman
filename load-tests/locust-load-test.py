"""
Doorman API Gateway - Locust Load Test

Alternative to k6 using Python-based locust framework.

Tests multiple scenarios:
1. Authentication (login)
2. API Management (CRUD operations)
3. REST Gateway (API proxying)
4. User Management
5. Mixed workload

Run with:
    locust -f load-tests/locust-load-test.py --host=http://localhost:8000

Run headless (no UI):
    locust -f load-tests/locust-load-test.py --host=http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 5m --headless

Run specific scenario:
    locust -f load-tests/locust-load-test.py --host=http://localhost:8000 \
           --tags authentication

Generate HTML report:
    locust -f load-tests/locust-load-test.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 10m --headless \
           --html load-tests/locust-report.html
"""

import json
import random
import time
from typing import Optional

from locust import HttpUser, task, tag, between, events
from locust.contrib.fasthttp import FastHttpUser


class DoormanUser(FastHttpUser):
    """
    Simulated user for Doorman API Gateway load testing.

    Uses FastHttpUser for better performance (gevent-based).
    """

    # Wait 1-3 seconds between tasks to simulate realistic user behavior
    wait_time = between(1, 3)

    # Authentication token
    auth_token: Optional[str] = None

    # Test credentials (read from env for safety; defaults for dev only)
    import os
    username = os.getenv("TEST_USERNAME", "admin")
    password = os.getenv("TEST_PASSWORD", "change-me")

    def on_start(self):
        """Called when a user starts - perform login"""
        self.login()

    def login(self):
        """Authenticate and store token"""
        response = self.client.post(
            "/auth/authorization",
            json={
                "username": self.username,
                "password": self.password,
            },
            catch_response=True,
        )

        if response.status_code == 200:
            # Extract token from cookie
            cookies = response.cookies.get_dict()
            self.auth_token = cookies.get("access_token_cookie")

            if self.auth_token:
                response.success()
            else:
                response.failure("No auth token in response")
        else:
            response.failure(f"Login failed with status {response.status_code}")

    def get_auth_headers(self):
        """Get headers with authentication token"""
        if self.auth_token:
            return {"Cookie": f"access_token_cookie={self.auth_token}"}
        return {}

    @task(10)
    @tag('authentication', 'smoke')
    def test_login(self):
        """Test authentication endpoint (10% of traffic)"""
        with self.client.post(
            "/auth/authorization",
            json={
                "username": self.username,
                "password": self.password,
            },
            catch_response=True,
            name="/auth/authorization [login]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")

    @task(20)
    @tag('api-management', 'load')
    def test_list_apis(self):
        """Test listing APIs (20% of traffic)"""
        with self.client.get(
            "/api/apis",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="/api/apis [list]",
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        response.success()
                    else:
                        response.failure("Response not a list")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"List APIs failed: {response.status_code}")

    @task(15)
    @tag('user-management', 'load')
    def test_list_users(self):
        """Test listing users (15% of traffic)"""
        with self.client.get(
            "/user/users",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="/user/users [list]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List users failed: {response.status_code}")

    @task(15)
    @tag('role-management', 'load')
    def test_list_roles(self):
        """Test listing roles (15% of traffic)"""
        with self.client.get(
            "/role/roles",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="/role/roles [list]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List roles failed: {response.status_code}")

    @task(15)
    @tag('group-management', 'load')
    def test_list_groups(self):
        """Test listing groups (15% of traffic)"""
        with self.client.get(
            "/group/groups",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="/group/groups [list]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List groups failed: {response.status_code}")

    @task(25)
    @tag('gateway', 'load', 'stress')
    def test_rest_gateway(self):
        """Test REST gateway (25% of traffic)"""
        # Simulate API call through gateway
        api_paths = [
            "/myapi/v1/users",
            "/myapi/v1/products",
            "/myapi/v1/orders",
        ]

        path = random.choice(api_paths)

        with self.client.get(
            path,
            headers={
                "Authorization": f"Bearer {self.auth_token}",
            },
            catch_response=True,
            name="/gateway/rest [proxy]",
        ) as response:
            # Gateway may return various status codes depending on upstream
            # Consider 200, 404 (API not found), 401 (auth required) as valid
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Gateway error: {response.status_code}")

    @task(5)
    @tag('health', 'smoke')
    def test_health_check(self):
        """Test health check endpoint (5% of traffic)"""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health [check]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class StressTestUser(FastHttpUser):
    """
    Stress test user - rapid-fire requests without delays.

    Use this class for stress testing scenarios.
    """

    wait_time = between(0.1, 0.5)  # Minimal wait time
    auth_token: Optional[str] = None
    username = "admin"
    password = "admin123"

    def on_start(self):
        """Login on start"""
        response = self.client.post(
            "/auth/authorization",
            json={"username": self.username, "password": self.password},
        )
        if response.status_code == 200:
            cookies = response.cookies.get_dict()
            self.auth_token = cookies.get("access_token_cookie")

    @task
    @tag('stress')
    def rapid_fire_requests(self):
        """Rapid-fire requests to stress test the system"""
        headers = {"Cookie": f"access_token_cookie={self.auth_token}"} if self.auth_token else {}

        # Batch of rapid requests
        endpoints = [
            "/api/apis",
            "/user/users",
            "/role/roles",
            "/group/groups",
        ]

        for endpoint in endpoints:
            self.client.get(endpoint, headers=headers, name=f"{endpoint} [stress]")


# Custom performance metrics tracking
latency_p50 = []
latency_p95 = []
latency_p99 = []


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track request metrics for custom reporting"""
    if not exception:
        latency_p50.append(response_time)
        latency_p95.append(response_time)
        latency_p99.append(response_time)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print custom performance summary at test end"""
    if latency_p50:
        latency_p50.sort()
        latency_p95.sort()
        latency_p99.sort()

        p50 = latency_p50[int(len(latency_p50) * 0.5)]
        p95 = latency_p95[int(len(latency_p95) * 0.95)]
        p99 = latency_p99[int(len(latency_p99) * 0.99)]

        print("\n" + "=" * 60)
        print("  Doorman API Gateway - Performance Summary")
        print("=" * 60)
        print(f"\nLatency Percentiles:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")
        print("\n" + "=" * 60 + "\n")


# Load test shapes (custom load patterns)
from locust import LoadTestShape


class StepLoadShape(LoadTestShape):
    """
    Step load pattern: gradually increase load in steps.

    Use with: locust -f locust-load-test.py --shape StepLoadShape
    """

    step_time = 60  # seconds per step
    step_load = 10  # users to add per step
    spawn_rate = 5  # users per second
    time_limit = 600  # total test duration (10 minutes)

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = run_time // self.step_time
        return (current_step * self.step_load, self.spawn_rate)


class SpikeLoadShape(LoadTestShape):
    """
    Spike load pattern: sudden traffic spike.

    Use with: locust -f locust-load-test.py --shape SpikeLoadShape
    """

    def tick(self):
        run_time = self.get_run_time()

        if run_time < 60:
            # Normal load: 10 users
            return (10, 5)
        elif run_time < 120:
            # Spike: 200 users
            return (200, 50)
        elif run_time < 180:
            # Recovery: back to 10 users
            return (10, 10)
        else:
            # End test
            return None


class WaveLoadShape(LoadTestShape):
    """
    Wave load pattern: load increases and decreases in waves.

    Use with: locust -f locust-load-test.py --shape WaveLoadShape
    """

    def tick(self):
        run_time = self.get_run_time()

        if run_time > 600:  # 10 minutes
            return None

        # Create wave pattern using sine function
        import math
        amplitude = 50
        period = 120  # 2-minute waves
        baseline = 25

        users = int(baseline + amplitude * math.sin(2 * math.pi * run_time / period))
        spawn_rate = 5

        return (users, spawn_rate)
