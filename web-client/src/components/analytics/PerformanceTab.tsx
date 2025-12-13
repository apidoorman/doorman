'use client'

import React, { useState } from 'react'
import LatencyChart from './LatencyChart'
import LatencyDistribution from './LatencyDistribution'
import TimeSeriesChart from './TimeSeriesChart'

interface PerformanceMetrics {
  percentiles: {
    p50: number
    p75: number
    p90: number
    p95: number
    p99: number
    min: number
    max: number
  }
  avg_response_ms: number
}

interface TimeSeriesData {
  series: Array<{
    timestamp: number
    count: number
    error_count: number
    error_rate: number
    avg_ms: number
    percentiles: {
      p50: number
      p75: number
      p90: number
      p95: number
      p99: number
    }
  }>
}

interface EndpointPerformance {
  endpoint_uri: string
  method: string
  count: number
  avg_ms: number
  p95_ms: number
  error_rate: number
}

interface PerformanceTabProps {
  overview: PerformanceMetrics
  timeSeries: TimeSeriesData | null
  endpoints?: EndpointPerformance[]
}

// Latency thresholds (in ms)
const THRESHOLDS = {
  excellent: 100,
  good: 300,
  acceptable: 1000
}

export default function PerformanceTab({ overview, timeSeries, endpoints = [] }: PerformanceTabProps) {
  const [comparisonMode, setComparisonMode] = useState(false)
  const [sortField, setSortField] = useState<'avg_ms' | 'p95_ms' | 'count'>('p95_ms')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  // Format helpers
  const formatMs = (ms: number): string => {
    return `${ms.toFixed(1)}ms`
  }

  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toLocaleString()
  }

  // Get performance status based on latency
  const getPerformanceStatus = (latency: number): { label: string; color: string; bgColor: string } => {
    if (latency <= THRESHOLDS.excellent) {
      return { label: 'Excellent', color: 'text-success-700 dark:text-success-400', bgColor: 'bg-success-100 dark:bg-success-900/20' }
    } else if (latency <= THRESHOLDS.good) {
      return { label: 'Good', color: 'text-blue-700 dark:text-blue-400', bgColor: 'bg-blue-100 dark:bg-blue-900/20' }
    } else if (latency <= THRESHOLDS.acceptable) {
      return { label: 'Acceptable', color: 'text-warning-700 dark:text-warning-400', bgColor: 'bg-warning-100 dark:bg-warning-900/20' }
    } else {
      return { label: 'Slow', color: 'text-error-700 dark:text-error-400', bgColor: 'bg-error-100 dark:bg-error-900/20' }
    }
  }

  // Sort endpoints
  const sortedEndpoints = [...endpoints].sort((a, b) => {
    const aVal = a[sortField]
    const bVal = b[sortField]
    return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
  })

  const handleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const avgStatus = getPerformanceStatus(overview.avg_response_ms)
  const p95Status = getPerformanceStatus(overview.percentiles.p95)
  const p99Status = getPerformanceStatus(overview.percentiles.p99)

  return (
    <div className="space-y-6">
      {/* Performance Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Average Latency */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Avg Latency
            </p>
            <span className={`text-xs px-2 py-1 rounded-full ${avgStatus.bgColor} ${avgStatus.color} font-medium`}>
              {avgStatus.label}
            </span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatMs(overview.avg_response_ms)}
          </p>
        </div>

        {/* p95 Latency */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              p95 Latency
            </p>
            <span className={`text-xs px-2 py-1 rounded-full ${p95Status.bgColor} ${p95Status.color} font-medium`}>
              {p95Status.label}
            </span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatMs(overview.percentiles.p95)}
          </p>
        </div>

        {/* p99 Latency */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              p99 Latency
            </p>
            <span className={`text-xs px-2 py-1 rounded-full ${p99Status.bgColor} ${p99Status.color} font-medium`}>
              {p99Status.label}
            </span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatMs(overview.percentiles.p99)}
          </p>
        </div>

        {/* Latency Range */}
        <div className="card p-4">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
            Latency Range
          </p>
          <div className="flex items-baseline gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {formatMs(overview.percentiles.min)}
            </span>
            <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <span className="text-lg font-bold text-gray-900 dark:text-white">
              {formatMs(overview.percentiles.max)}
            </span>
          </div>
        </div>
      </div>

      {/* Performance Thresholds Legend */}
      <div className="card p-4">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          Performance Thresholds
        </h4>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-success-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Excellent (&lt; {THRESHOLDS.excellent}ms)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Good ({THRESHOLDS.excellent}-{THRESHOLDS.good}ms)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-warning-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Acceptable ({THRESHOLDS.good}-{THRESHOLDS.acceptable}ms)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-error-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              Slow (&gt; {THRESHOLDS.acceptable}ms)
            </span>
          </div>
        </div>
      </div>

      {/* Charts */}
      {timeSeries && timeSeries.series && timeSeries.series.length > 0 && (
        <div className="space-y-6">
          {/* Latency Percentiles Over Time */}
          <div className="card p-6">
            <LatencyChart
              data={timeSeries.series}
              title="Latency Percentiles Over Time"
              height={350}
            />
          </div>

          {/* Response Time Distribution */}
          <div className="card p-6">
            <LatencyDistribution
              data={timeSeries.series}
              title="Response Time Distribution"
              height={300}
            />
          </div>

          {/* Average Response Time Trend */}
          <div className="card p-6">
            <TimeSeriesChart
              data={timeSeries.series}
              title="Average Response Time Trend"
              dataKey="avg_ms"
              color="#10b981"
              height={300}
            />
          </div>
        </div>
      )}

      {/* Slowest Endpoints Table */}
      {endpoints.length > 0 && (
        <div className="card">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Slowest Endpoints
              </h3>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Top {Math.min(endpoints.length, 10)} by p95 latency
              </span>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th className="w-12">#</th>
                  <th>Endpoint</th>
                  <th>Method</th>
                  <th>
                    <button
                      onClick={() => handleSort('count')}
                      className="flex items-center gap-1 hover:text-primary-600"
                    >
                      Requests
                      {sortField === 'count' && (
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sortDirection === 'asc' ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th>
                    <button
                      onClick={() => handleSort('avg_ms')}
                      className="flex items-center gap-1 hover:text-primary-600"
                    >
                      Avg Latency
                      {sortField === 'avg_ms' && (
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sortDirection === 'asc' ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th>
                    <button
                      onClick={() => handleSort('p95_ms')}
                      className="flex items-center gap-1 hover:text-primary-600"
                    >
                      p95 Latency
                      {sortField === 'p95_ms' && (
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={sortDirection === 'asc' ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
                        </svg>
                      )}
                    </button>
                  </th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sortedEndpoints.slice(0, 10).map((endpoint, index) => {
                  const status = getPerformanceStatus(endpoint.p95_ms)
                  return (
                    <tr key={`${endpoint.method}:${endpoint.endpoint_uri}`}>
                      <td className="font-medium text-gray-500 dark:text-gray-400">
                        #{index + 1}
                      </td>
                      <td>
                        <span className="font-mono text-sm text-gray-900 dark:text-white">
                          {endpoint.endpoint_uri}
                        </span>
                      </td>
                      <td>
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                          {endpoint.method}
                        </span>
                      </td>
                      <td className="text-gray-700 dark:text-gray-300">
                        {formatNumber(endpoint.count)}
                      </td>
                      <td className="text-gray-700 dark:text-gray-300">
                        {formatMs(endpoint.avg_ms)}
                      </td>
                      <td className="font-semibold text-gray-900 dark:text-white">
                        {formatMs(endpoint.p95_ms)}
                      </td>
                      <td>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.bgColor} ${status.color}`}>
                          {status.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Comparison Mode Toggle (Placeholder) */}
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
              Time Period Comparison
            </h4>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Compare performance across different time periods
            </p>
          </div>
          <button
            onClick={() => setComparisonMode(!comparisonMode)}
            className="btn btn-outline btn-sm"
            disabled
          >
            {comparisonMode ? 'Disable' : 'Enable'} Comparison
          </button>
        </div>
        {comparisonMode && (
          <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Comparison mode will be available in a future update. This feature will allow you to:
            </p>
            <ul className="list-disc list-inside text-sm text-gray-500 dark:text-gray-500 mt-2 space-y-1">
              <li>Compare current period vs previous period</li>
              <li>Compare week-over-week or month-over-month</li>
              <li>Identify performance regressions</li>
              <li>Track improvement trends</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
