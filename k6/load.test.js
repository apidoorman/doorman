// k6 load test for /api/rest/* and /platform/* with thresholds and JUnit output
// Usage:
//   k6 run k6/load.test.js \
//     -e BASE_URL=http://localhost:5001 \
//     -e RPS=50 \
//     -e DURATION=1m \
//     -e REST_PATHS='["/api/rest/health"]' \
//     -e PLATFORM_PATHS='["/platform/authorization/status"]'
//
// Thresholds:
// - p95 < 250ms (per group: rest, platform)
// - error_rate < 1% (global)
// - RPS >= X (per group; X comes from env RPS)
//
// The test writes a JUnit XML summary to junit.xml for CI and exits non-zero
// if any threshold fails (k6 default behavior), causing the CI job to fail.

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Trend, Rate, Counter } from 'k6/metrics'

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5001'
const DURATION = __ENV.DURATION || '1m'
const RPS = Number(__ENV.RPS || 20)
const REST_PATHS = (function () {
  try { return JSON.parse(__ENV.REST_PATHS || '[]') } catch (_) { return [] }
})()
const PLATFORM_PATHS = (function () {
  try { return JSON.parse(__ENV.PLATFORM_PATHS || '["/platform/authorization/status"]') } catch (_) { return ['/platform/authorization/status'] }
})()

// Per-group request counters so we can assert RPS via thresholds
const restRequests = new Counter('rest_http_reqs')
const platformRequests = new Counter('platform_http_reqs')

// Optional: capture durations per group (not strictly needed for thresholds)
export const options = {
  scenarios: {
    rest: REST_PATHS.length > 0 ? {
      executor: 'constant-arrival-rate',
      rate: RPS,            // RPS for /api/rest/*
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(1, Math.min(100, RPS * 2)),
      maxVUs: Math.max(10, RPS * 5),
      exec: 'restScenario',
    } : undefined,
    platform: {
      executor: 'constant-arrival-rate',
      rate: RPS,            // RPS for /platform/*
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(1, Math.min(100, RPS * 2)),
      maxVUs: Math.max(10, RPS * 5),
      exec: 'platformScenario',
    },
  },
  thresholds: {
    // Error rate across all requests
    'http_req_failed': ['rate<0.01'],

    // Latency p95 per group
    'http_req_duration{group:rest}': ['p(95)<250'],
    'http_req_duration{group:platform}': ['p(95)<250'],

    // Throughput (RPS) per group; use the provided RPS as the minimum rate
    ...(RPS > 0 ? {
      'rest_http_reqs': [`rate>=${RPS}`],
      'platform_http_reqs': [`rate>=${RPS}`],
    } : {}),
  },
}

export function restScenario () {
  group('rest', function () {
    if (REST_PATHS.length === 0) {
      sleep(1)
      return
    }
    const path = REST_PATHS[Math.floor(Math.random() * REST_PATHS.length)]
    const res = http.get(`${BASE_URL}${path}`, { tags: { endpoint: path } })
    restRequests.add(1)
    check(res, {
      'status is 2xx/3xx': r => r.status >= 200 && r.status < 400,
    })
  })
}

export function platformScenario () {
  group('platform', function () {
    const path = PLATFORM_PATHS[Math.floor(Math.random() * PLATFORM_PATHS.length)]
    const res = http.get(`${BASE_URL}${path}`, { tags: { endpoint: path } })
    platformRequests.add(1)
    check(res, {
      'status is 2xx/3xx': r => r.status >= 200 && r.status < 400,
    })
  })
}

// Produce a minimal JUnit XML from threshold results for CI consumption
export function handleSummary (data) {
  const testcases = []
  // Encode threshold results as testcases
  for (const [metric, th] of Object.entries(data.thresholds || {})) {
    // Each entry can be: { ok: boolean, thresholds: [ 'p(95)<250', ... ] }
    const name = `threshold: ${metric}`
    const ok = th.ok === true
    const expr = Array.isArray(th.thresholds) ? th.thresholds.join('; ') : ''
    const tc = {
      name,
      classname: 'k6.thresholds',
      time: (data.state?.testRunDurationMs || 0) / 1000.0,
      failure: ok ? null : `Failed: ${expr}`,
    }
    testcases.push(tc)
  }

  const total = testcases.length
  const failures = testcases.filter(t => !!t.failure).length
  const tsName = 'k6 thresholds'
  const xmlParts = []
  xmlParts.push(`<?xml version="1.0" encoding="UTF-8"?>`)
  xmlParts.push(`<testsuite name="${tsName}" tests="${total}" failures="${failures}">`)
  for (const tc of testcases) {
    xmlParts.push(`  <testcase classname="${tc.classname}" name="${escapeXml(tc.name)}" time="${tc.time}">`)
    if (tc.failure) {
      xmlParts.push(`    <failure message="${escapeXml(tc.failure)}"/>`)
    }
    xmlParts.push('  </testcase>')
  }
  xmlParts.push('</testsuite>')
  const junitXml = xmlParts.join('\n')

  return {
    'junit.xml': junitXml,
    'summary.json': JSON.stringify(data, null, 2),
  }
}

function escapeXml (s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

