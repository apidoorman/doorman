'use client'

import React, { useState } from 'react'
import InfoTooltip from '@/components/InfoTooltip'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'

interface CorsResult {
  config: {
    allowed_origins: string[]
    effective_allowed_origins: string[]
    allow_credentials: boolean
    allow_methods: string[]
    allow_headers: string[]
    cors_strict: boolean
  }
  input: {
    origin: string
    method: string
    request_headers: string[]
    with_credentials: boolean
  }
  preflight: {
    allowed: boolean
    allow_origin: boolean
    method_allowed: boolean
    headers_allowed: boolean
    not_allowed_headers: string[]
    response_headers: Record<string, string | null>
  }
  actual: {
    allowed: boolean
    response_headers: Record<string, string | null>
  }
  notes: string[]
}

const ToolsPage = () => {
  const [origin, setOrigin] = useState('http://localhost:3000')
  const [method, setMethod] = useState('GET')
  const [headersText, setHeadersText] = useState('Content-Type, Authorization')
  const [withCredentials, setWithCredentials] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CorsResult | null>(null)

  const onCheck = async () => {
    try {
      setLoading(true)
      setError(null)
      setResult(null)
      const payload = {
        origin: origin.trim(),
        method: method.trim().toUpperCase(),
        request_headers: headersText.split(',').map(h => h.trim()).filter(Boolean),
        with_credentials: withCredentials,
      }
      const data = await postJson<CorsResult>(`${SERVER_URL}/platform/tools/cors/check`, payload)
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ProtectedRoute>
      <Layout>
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Tools</h1>
            <p className="text-sm text-gray-600 dark:text-gray-300">Diagnostics and helpers for operating your gateway.</p>
          </div>

          <section className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-3">CORS Checker</h2>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">For /api/* routes, Doorman applies per-API CORS. Platform routes (/platform/*) use environment settings.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Origin <InfoTooltip text="The requesting site (scheme + host + port)." />
                </label>
                <input className="mt-1 w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={origin} onChange={e => setOrigin(e.target.value)} placeholder="https://app.example.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Method <InfoTooltip text="The intended request method (e.g., GET, POST) used for preflight validation." />
                </label>
                <input className="mt-1 w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={method} onChange={e => setMethod(e.target.value)} placeholder="GET" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Request Headers (comma-separated) <InfoTooltip text="Headers sent by the browser (Access-Control-Request-Headers). Case-insensitive." />
                </label>
                <input className="mt-1 w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white" value={headersText} onChange={e => setHeadersText(e.target.value)} placeholder="Content-Type, Authorization" />
              </div>
              <div className="flex items-center space-x-2">
                <input id="withCreds" type="checkbox" checked={withCredentials} onChange={e => setWithCredentials(e.target.checked)} className="rounded border-gray-300 dark:border-gray-600" />
                <label htmlFor="withCreds" className="text-sm text-gray-700 dark:text-gray-200">
                  With Credentials <InfoTooltip text="Simulate credentialed requests (cookies/Authorization). With credentials, avoid wildcard origins and headers." />
                </label>
              </div>
            </div>
            <div className="mt-4">
              <button onClick={onCheck} disabled={loading} className="px-4 py-2 rounded-md bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">{loading ? 'Checking…' : 'Check'}</button>
            </div>

            {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

            {result && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3 rounded bg-gray-50 dark:bg-gray-900">
                  <h3 className="font-medium text-gray-900 dark:text-white">Preflight</h3>
                  <div className="text-sm text-gray-700 dark:text-gray-200 mt-1">
                    <div>Allowed: <span className={result.preflight.allowed ? 'text-green-600' : 'text-red-600'}>{String(result.preflight.allowed)}</span></div>
                    <div>Origin Allowed: {String(result.preflight.allow_origin)}</div>
                    <div>Method Allowed: {String(result.preflight.method_allowed)}</div>
                    <div>Headers Allowed: {String(result.preflight.headers_allowed)}</div>
                    {result.preflight.not_allowed_headers?.length > 0 && (
                      <div>Not Allowed Headers: {result.preflight.not_allowed_headers.join(', ')}</div>
                    )}
                    <div className="mt-2">
                      <div className="font-medium">Response Headers</div>
                      <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(result.preflight.response_headers, null, 2)}</pre>
                    </div>
                  </div>
                </div>
                <div className="p-3 rounded bg-gray-50 dark:bg-gray-900">
                  <h3 className="font-medium text-gray-900 dark:text-white">Actual Request</h3>
                  <div className="text-sm text-gray-700 dark:text-gray-200 mt-1">
                    <div>Allowed: <span className={result.actual.allowed ? 'text-green-600' : 'text-red-600'}>{String(result.actual.allowed)}</span></div>
                    <div className="mt-2">
                      <div className="font-medium">Response Headers</div>
                      <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(result.actual.response_headers, null, 2)}</pre>
                    </div>
                  </div>
                </div>

                <div className="md:col-span-2 p-3 rounded bg-gray-50 dark:bg-gray-900">
                  <h3 className="font-medium text-gray-900 dark:text-white">Effective Config</h3>
                  <pre className="text-xs text-gray-800 dark:text-gray-200">{JSON.stringify(result.config, null, 2)}</pre>
                  {result.notes?.length > 0 && (
                    <div className="mt-2 text-xs text-gray-700 dark:text-gray-300">
                      <div className="font-medium">Notes</div>
                      <ul className="list-disc ml-5">
                        {result.notes.map((n, i) => <li key={i}>{n}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

export default ToolsPage
