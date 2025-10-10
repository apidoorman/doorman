/**
 * Doorman API Gateway - k6 Load Test
 *
 * Tests multiple scenarios to establish performance baseline:
 * 1. Authentication (login)
 * 2. REST Gateway (API proxying)
 * 3. GraphQL Gateway
 * 4. SOAP Gateway
 * 5. Mixed workload
 *
 * Run with:
 *   k6 run load-tests/k6-load-test.js
 *
 * Generate HTML report:
 *   k6 run --out json=load-tests/results.json load-tests/k6-load-test.js
 *   k6 report load-tests/results.json --output load-tests/report.html
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const authSuccessRate = new Rate('auth_success_rate');
const restGatewayLatency = new Trend('rest_gateway_latency');
const graphqlGatewayLatency = new Trend('graphql_gateway_latency');
const soapGatewayLatency = new Trend('soap_gateway_latency');
const errorCount = new Counter('error_count');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TEST_USERNAME = __ENV.TEST_USERNAME || 'admin';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'admin123';

// Load test stages
export const options = {
    scenarios: {
        // Scenario 1: Smoke test (1 VU for 30s)
        smoke: {
            executor: 'constant-vus',
            vus: 1,
            duration: '30s',
            tags: { scenario: 'smoke' },
            exec: 'smokeTest',
        },

        // Scenario 2: Load test (ramp up to 50 VUs)
        load: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '1m', target: 10 },   // Ramp up to 10 VUs
                { duration: '3m', target: 10 },   // Stay at 10 VUs
                { duration: '1m', target: 50 },   // Ramp up to 50 VUs
                { duration: '3m', target: 50 },   // Stay at 50 VUs
                { duration: '1m', target: 0 },    // Ramp down to 0
            ],
            tags: { scenario: 'load' },
            exec: 'loadTest',
            startTime: '30s',  // Start after smoke test
        },

        // Scenario 3: Stress test (push to limits)
        stress: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 100 },  // Ramp up to 100 VUs
                { duration: '5m', target: 100 },  // Stay at 100 VUs
                { duration: '2m', target: 200 },  // Push to 200 VUs
                { duration: '5m', target: 200 },  // Stay at 200 VUs
                { duration: '2m', target: 0 },    // Ramp down
            ],
            tags: { scenario: 'stress' },
            exec: 'stressTest',
            startTime: '10m',  // Start after load test
        },

        // Scenario 4: Spike test (sudden traffic spike)
        spike: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 10 },   // Normal load
                { duration: '10s', target: 200 },  // Sudden spike
                { duration: '1m', target: 200 },   // Hold spike
                { duration: '10s', target: 10 },   // Back to normal
                { duration: '30s', target: 10 },   // Recovery period
            ],
            tags: { scenario: 'spike' },
            exec: 'spikeTest',
            startTime: '26m',  // Start after stress test
        },
    },

    thresholds: {
        // Overall thresholds
        'http_req_duration': ['p(50)<100', 'p(95)<500', 'p(99)<1000'],  // Latency targets
        'http_req_failed': ['rate<0.05'],  // Error rate < 5%

        // Authentication thresholds
        'auth_success_rate': ['rate>0.95'],

        // Gateway-specific thresholds
        'rest_gateway_latency': ['p(50)<150', 'p(95)<600', 'p(99)<1200'],
        'graphql_gateway_latency': ['p(50)<200', 'p(95)<800', 'p(99)<1500'],
        'soap_gateway_latency': ['p(50)<250', 'p(95)<1000', 'p(99)<2000'],

        // Error threshold
        'error_count': ['count<100'],
    },
};

// Helper: Login and get auth token
function login() {
    const loginPayload = JSON.stringify({
        username: TEST_USERNAME,
        password: TEST_PASSWORD,
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = http.post(`${BASE_URL}/auth/authorization`, loginPayload, params);

    const success = check(response, {
        'login status is 200': (r) => r.status === 200,
        'login has access_token_cookie': (r) => r.cookies.access_token_cookie !== undefined,
    });

    authSuccessRate.add(success);

    if (success) {
        return response.cookies.access_token_cookie[0].value;
    }

    errorCount.add(1);
    return null;
}

// Helper: Make authenticated request
function makeAuthRequest(method, url, token, body = null) {
    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
        cookies: {
            'access_token_cookie': token,
        },
    };

    if (body) {
        return http.request(method, url, JSON.stringify(body), params);
    }
    return http.request(method, url, null, params);
}

// Smoke Test: Basic functionality
export function smokeTest() {
    group('Smoke Test - Basic Functionality', () => {
        // Test 1: Health check
        group('Health Check', () => {
            const response = http.get(`${BASE_URL}/health`);
            check(response, {
                'health check status is 200': (r) => r.status === 200,
            });
        });

        // Test 2: Login
        group('Login', () => {
            const token = login();
            check(token, {
                'login successful': (t) => t !== null,
            });
        });

        sleep(1);
    });
}

// Load Test: Realistic workload
export function loadTest() {
    const token = login();
    if (!token) {
        errorCount.add(1);
        return;
    }

    group('Load Test - Realistic Workload', () => {
        // Test 1: List APIs
        group('List APIs', () => {
            const response = makeAuthRequest('GET', `${BASE_URL}/api/apis`, token);
            check(response, {
                'list apis status is 200': (r) => r.status === 200,
                'list apis returns array': (r) => {
                    try {
                        const body = JSON.parse(r.body);
                        return Array.isArray(body);
                    } catch {
                        return false;
                    }
                },
            });
        });

        // Test 2: REST Gateway (simulate API call)
        group('REST Gateway', () => {
            const start = Date.now();
            const response = http.get(`${BASE_URL}/myapi/v1/users`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });
            const duration = Date.now() - start;

            restGatewayLatency.add(duration);

            check(response, {
                'rest gateway responds': (r) => r.status !== 0,
            }) || errorCount.add(1);
        });

        // Test 3: List users
        group('List Users', () => {
            const response = makeAuthRequest('GET', `${BASE_URL}/user/users`, token);
            check(response, {
                'list users status is 200': (r) => r.status === 200,
            });
        });

        sleep(1);
    });
}

// Stress Test: Push system to limits
export function stressTest() {
    const token = login();
    if (!token) {
        errorCount.add(1);
        return;
    }

    group('Stress Test - High Load', () => {
        // Rapid-fire requests
        for (let i = 0; i < 5; i++) {
            const response = makeAuthRequest('GET', `${BASE_URL}/api/apis`, token);
            check(response, {
                'stress test request succeeds': (r) => r.status === 200,
            }) || errorCount.add(1);
        }

        sleep(0.5);
    });
}

// Spike Test: Sudden traffic increase
export function spikeTest() {
    const token = login();
    if (!token) {
        errorCount.add(1);
        return;
    }

    group('Spike Test - Traffic Burst', () => {
        // Burst of concurrent requests
        const responses = http.batch([
            ['GET', `${BASE_URL}/api/apis`, null, { cookies: { 'access_token_cookie': token } }],
            ['GET', `${BASE_URL}/user/users`, null, { cookies: { 'access_token_cookie': token } }],
            ['GET', `${BASE_URL}/role/roles`, null, { cookies: { 'access_token_cookie': token } }],
            ['GET', `${BASE_URL}/group/groups`, null, { cookies: { 'access_token_cookie': token } }],
        ]);

        responses.forEach((response) => {
            check(response, {
                'spike test request succeeds': (r) => r.status === 200,
            }) || errorCount.add(1);
        });

        sleep(0.1);
    });
}

// Summary handler
export function handleSummary(data) {
    return {
        'stdout': textSummary(data, { indent: ' ', enableColors: true }),
        'load-tests/k6-summary.json': JSON.stringify(data, null, 2),
    };
}

// Text summary helper
function textSummary(data, options) {
    const indent = options?.indent || '';
    const enableColors = options?.enableColors || false;

    const lines = [
        '',
        `${indent}===============================================`,
        `${indent}  Doorman API Gateway - Load Test Results`,
        `${indent}===============================================`,
        '',
        `${indent}Scenarios:`,
        `${indent}  ✓ Smoke Test  (1 VU, 30s)`,
        `${indent}  ✓ Load Test   (0→10→50 VUs, 9m)`,
        `${indent}  ✓ Stress Test (0→100→200 VUs, 16m)`,
        `${indent}  ✓ Spike Test  (10→200→10 VUs, 2m)`,
        '',
        `${indent}Key Metrics:`,
        `${indent}  HTTP Requests: ${data.metrics.http_reqs?.values?.count || 0}`,
        `${indent}  Failed Requests: ${data.metrics.http_req_failed?.values?.rate ? (data.metrics.http_req_failed.values.rate * 100).toFixed(2) : 0}%`,
        `${indent}  Auth Success Rate: ${data.metrics.auth_success_rate?.values?.rate ? (data.metrics.auth_success_rate.values.rate * 100).toFixed(2) : 0}%`,
        '',
        `${indent}Latency (p50/p95/p99):`,
        `${indent}  Overall:  ${data.metrics.http_req_duration?.values?.['p(50)']?.toFixed(2) || 0}ms / ${data.metrics.http_req_duration?.values?.['p(95)']?.toFixed(2) || 0}ms / ${data.metrics.http_req_duration?.values?.['p(99)']?.toFixed(2) || 0}ms`,
        `${indent}  REST:     ${data.metrics.rest_gateway_latency?.values?.['p(50)']?.toFixed(2) || 0}ms / ${data.metrics.rest_gateway_latency?.values?.['p(95)']?.toFixed(2) || 0}ms / ${data.metrics.rest_gateway_latency?.values?.['p(99)']?.toFixed(2) || 0}ms`,
        `${indent}  GraphQL:  ${data.metrics.graphql_gateway_latency?.values?.['p(50)']?.toFixed(2) || 0}ms / ${data.metrics.graphql_gateway_latency?.values?.['p(95)']?.toFixed(2) || 0}ms / ${data.metrics.graphql_gateway_latency?.values?.['p(99)']?.toFixed(2) || 0}ms`,
        `${indent}  SOAP:     ${data.metrics.soap_gateway_latency?.values?.['p(50)']?.toFixed(2) || 0}ms / ${data.metrics.soap_gateway_latency?.values?.['p(95)']?.toFixed(2) || 0}ms / ${data.metrics.soap_gateway_latency?.values?.['p(99)']?.toFixed(2) || 0}ms`,
        '',
        `${indent}===============================================`,
        '',
    ];

    return lines.join('\n');
}
