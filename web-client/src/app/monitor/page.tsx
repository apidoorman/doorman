'use client'

import React, { useState, useEffect } from 'react'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'

interface Metric {
  timestamp: string
  value: number
}

interface Metrics {
  totalRequests: Metric[]
  errorRate: Metric[]
  avgResponseTime: Metric[]
  activeUsers: Metric[]
  bandwidthUsage: Metric[]
  cpuUsage: Metric[]
  memoryUsage: Metric[]
  statusCodes: {
    [key: string]: number
  }
}

const MonitorPage: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<any | null>(null)
  const [timeRange, setTimeRange] = useState('24h')

  useEffect(() => {
    fetchMetrics()
  }, [timeRange])

  const fetchMetrics = async () => {
    try {
      setLoading(true)
      setError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/monitor/metrics?range=${encodeURIComponent(timeRange)}`)
      setMetrics(payload)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('An unknown error occurred')
      }
      setMetrics(null)
    } finally {
      setLoading(false)
    }
  }

  const renderMetricChart = (data: Metric[], title: string): React.ReactNode => {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">{title}</h3>
        </div>
        <div className="p-6">
          <div className="h-48 bg-gray-50 dark:bg-gray-800 rounded-lg flex items-center justify-center">
            <p className="text-gray-500 dark:text-gray-400">{title} chart will be implemented here</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <ProtectedRoute requiredPermission="manage_gateway">
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Monitor</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Real-time system metrics and performance monitoring
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="input"
            >
              <option value="1h">Last Hour</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
            <button onClick={fetchMetrics} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
            <div className="flex">
              <svg className="h-5 w-5 text-error-400 dark:text-error-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="ml-3">
                <p className="text-sm text-error-700 dark:text-error-300">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="card">
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="spinner mx-auto mb-4"></div>
                <p className="text-gray-600 dark:text-gray-400">Loading metrics...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Metrics Grid */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Total Requests */}
            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Total Requests</p>
                  <p className="stats-value">{metrics?.total_requests ?? 0}</p>
                  <p className="stats-change">&nbsp;</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Error Rate */}
            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Error Rate</p>
                  <p className="stats-value">
                    {(() => {
                      const series = metrics?.series || []
                      const total = series.reduce((a: number, b: any) => a + (b.count || 0), 0)
                      const errs = series.reduce((a: number, b: any) => a + (b.error_count || 0), 0)
                      if (!total) return '0%'
                      return `${((errs / total) * 100).toFixed(2)}%`
                    })()}
                  </p>
                  <p className="stats-change">&nbsp;</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Average Response Time */}
            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Avg Response Time</p>
                  <p className="stats-value">{Math.round(metrics?.avg_response_ms ?? 0)}ms</p>
                  <p className="stats-change">&nbsp;</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Active Users */}
            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Active Users</p>
                  <p className="stats-value">--</p>
                  <p className="stats-change">&nbsp;</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <div className="card-header"><h3 className="card-title">Status Codes</h3></div>
            <div className="p-6">
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(metrics?.status_counts || {}).map(([code, count]) => (
                  <div key={code} className="flex justify-between text-sm"><span>{code}</span><span>{count as any}</span></div>
                ))}
                {(!metrics || !metrics.status_counts || Object.keys(metrics.status_counts).length === 0) && (
                  <p className="text-gray-500 dark:text-gray-400">No data</p>
                )}
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-header"><h3 className="card-title">Request Volume (per minute)</h3></div>
            <div className="p-6">
              <div className="h-48 overflow-y-auto">
                <ul className="text-sm space-y-1">
                  {(metrics?.series || []).slice().reverse().map((pt: any) => (
                    <li key={pt.timestamp} className="flex justify-between">
                      <span>{new Date(pt.timestamp * 1000).toLocaleTimeString()}</span>
                      <span>{pt.count} req • avg {Math.round(pt.avg_ms)}ms • {pt.error_count} errs</span>
                    </li>
                  ))}
                </ul>
                {(!metrics || !metrics.series || metrics.series.length === 0) && (
                  <p className="text-gray-500 dark:text-gray-400">No data</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">System Status</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="h-3 w-3 bg-green-500 rounded-full mr-3"></div>
                <div>
                  <p className="font-medium text-green-900 dark:text-green-100">API Gateway</p>
                  <p className="text-sm text-green-600 dark:text-green-400">Operational</p>
                </div>
              </div>
              <div className="flex items-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="h-3 w-3 bg-green-500 rounded-full mr-3"></div>
                <div>
                  <p className="font-medium text-green-900 dark:text-green-100">Database</p>
                  <p className="text-sm text-green-600 dark:text-green-400">Operational</p>
                </div>
              </div>
              <div className="flex items-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="h-3 w-3 bg-green-500 rounded-full mr-3"></div>
                <div>
                  <p className="font-medium text-green-900 dark:text-green-100">Cache</p>
                  <p className="text-sm text-green-600 dark:text-green-400">Operational</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
    </ProtectedRoute>
  )
}

export default MonitorPage 
