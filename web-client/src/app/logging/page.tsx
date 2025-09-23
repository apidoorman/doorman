'use client'

import React, { useState, useEffect } from 'react'
import { format } from 'date-fns'
import { ChangeEvent } from 'react'
import Layout from '@/components/Layout'

interface Log {
  timestamp: string
  request_id?: string
  level: string
  message: string
  source: string
  user?: string
  endpoint?: string
  method?: string
  ipAddress?: string
  responseTime?: number
}

interface FilterState {
  startDate: string
  endDate: string
  startTime: string
  endTime: string
  user: string
  endpoint: string
  request_id: string
  method: string
  ipAddress: string
  minResponseTime: string
  maxResponseTime: string
  level: string
}

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [filters, setFilters] = useState<FilterState>(() => {
    const now = new Date()
    const today = now.toISOString().split('T')[0]
    
    const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000)
    const startTime = thirtyMinutesAgo.toTimeString().slice(0, 5)
    const endTime = now.toTimeString().slice(0, 5)
    
    return {
      startDate: today,
      endDate: today,
      startTime: startTime,
      endTime: endTime,
      user: '',
      endpoint: '',
      request_id: '',
      method: '',
      ipAddress: '',
      minResponseTime: '',
      maxResponseTime: '',
      level: ''
    }
  })

  useEffect(() => {
    fetchLogs()
  }, [filters])

  const fetchLogs = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const queryParams = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => {
        if (value) queryParams.append(key, value)
      })
      
      const response = await fetch(`http://localhost:3002/platform/logging?${queryParams}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to fetch logs')
      }
      
      const data = await response.json()
      setLogs(data.logs || [])
    } catch (err) {
      setError('Failed to fetch logs. Please try again later.')
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
  }

  const clearFilters = () => {
    const now = new Date()
    const today = now.toISOString().split('T')[0]
    const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000)
    const startTime = thirtyMinutesAgo.toTimeString().slice(0, 5)
    const endTime = now.toTimeString().slice(0, 5)
    
    setFilters({
      startDate: today,
      endDate: today,
      startTime: startTime,
      endTime: endTime,
      user: '',
      endpoint: '',
      request_id: '',
      method: '',
      ipAddress: '',
      minResponseTime: '',
      maxResponseTime: '',
      level: ''
    })
  }

  const exportLogs = async (format: 'json' | 'csv') => {
    try {
      setExporting(true)
      const queryParams = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => {
        if (value) queryParams.append(key, value)
      })
      queryParams.append('format', format)
      
      const response = await fetch(`http://localhost:3002/platform/logging/export?${queryParams}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to export logs')
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `logs-${new Date().toISOString().split('T')[0]}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError('Failed to export logs. Please try again later.')
    } finally {
      setExporting(false)
    }
  }

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error': return 'text-red-600 dark:text-red-400'
      case 'warn': return 'text-yellow-600 dark:text-yellow-400'
      case 'info': return 'text-blue-600 dark:text-blue-400'
      case 'debug': return 'text-gray-600 dark:text-gray-400'
      default: return 'text-gray-600 dark:text-gray-400'
    }
  }

  const getLevelBgColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error': return 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-200'
      case 'warn': return 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200'
      case 'info': return 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200'
      case 'debug': return 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200'
      default: return 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200'
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Logs</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              View and analyze system logs and API requests
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => exportLogs('json')}
              disabled={exporting}
              className="btn btn-secondary"
            >
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export JSON
            </button>
            <button
              onClick={() => exportLogs('csv')}
              disabled={exporting}
              className="btn btn-secondary"
            >
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export CSV
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Filters</h3>
            <button
              onClick={() => setShowMoreFilters(!showMoreFilters)}
              className="btn btn-ghost btn-sm"
            >
              {showMoreFilters ? 'Show Less' : 'Show More'}
            </button>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  name="startDate"
                  value={filters.startDate}
                  onChange={handleFilterChange}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  name="endDate"
                  value={filters.endDate}
                  onChange={handleFilterChange}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Start Time
                </label>
                <input
                  type="time"
                  name="startTime"
                  value={filters.startTime}
                  onChange={handleFilterChange}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  End Time
                </label>
                <input
                  type="time"
                  name="endTime"
                  value={filters.endTime}
                  onChange={handleFilterChange}
                  className="input"
                />
              </div>
            </div>

            {showMoreFilters && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    User
                  </label>
                  <input
                    type="text"
                    name="user"
                    value={filters.user}
                    onChange={handleFilterChange}
                    placeholder="Filter by user"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Endpoint
                  </label>
                  <input
                    type="text"
                    name="endpoint"
                    value={filters.endpoint}
                    onChange={handleFilterChange}
                    placeholder="Filter by endpoint"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Request ID
                  </label>
                  <input
                    type="text"
                    name="request_id"
                    value={filters.request_id}
                    onChange={handleFilterChange}
                    placeholder="Filter by request ID"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Method
                  </label>
                  <select
                    name="method"
                    value={filters.method}
                    onChange={handleFilterChange}
                    className="input"
                  >
                    <option value="">All Methods</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    IP Address
                  </label>
                  <input
                    type="text"
                    name="ipAddress"
                    value={filters.ipAddress}
                    onChange={handleFilterChange}
                    placeholder="Filter by IP"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Min Response Time (ms)
                  </label>
                  <input
                    type="number"
                    name="minResponseTime"
                    value={filters.minResponseTime}
                    onChange={handleFilterChange}
                    placeholder="Min time"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Max Response Time (ms)
                  </label>
                  <input
                    type="number"
                    name="maxResponseTime"
                    value={filters.maxResponseTime}
                    onChange={handleFilterChange}
                    placeholder="Max time"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Log Level
                  </label>
                  <select
                    name="level"
                    value={filters.level}
                    onChange={handleFilterChange}
                    className="input"
                  >
                    <option value="">All Levels</option>
                    <option value="ERROR">Error</option>
                    <option value="WARN">Warning</option>
                    <option value="INFO">Info</option>
                    <option value="DEBUG">Debug</option>
                  </select>
                </div>
              </div>
            )}

            <div className="flex gap-2 mt-6">
              <button onClick={fetchLogs} className="btn btn-primary">
                Apply Filters
              </button>
              <button onClick={clearFilters} className="btn btn-secondary">
                Clear Filters
              </button>
            </div>
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
                <p className="text-gray-600 dark:text-gray-400">Loading logs...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Logs Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Level</th>
                    <th>Message</th>
                    <th>User</th>
                    <th>Endpoint</th>
                    <th>Method</th>
                    <th>Response Time</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log, index) => (
                    <tr key={index} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors">
                      <td>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {format(new Date(log.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                        </p>
                      </td>
                      <td>
                        <span className={`badge ${getLevelBgColor(log.level)}`}>
                          {log.level}
                        </span>
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {log.message}
                        </p>
                      </td>
                      <td>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {log.user || '-'}
                        </p>
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {log.endpoint || '-'}
                        </p>
                      </td>
                      <td>
                        <span className={`badge ${log.method === 'GET' ? 'badge-success' : log.method === 'POST' ? 'badge-primary' : 'badge-warning'}`}>
                          {log.method || '-'}
                        </span>
                      </td>
                      <td>
                        <p className="text-sm text-gray-900 dark:text-white">
                          {log.responseTime ? `${log.responseTime}ms` : '-'}
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Empty State */}
            {logs.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No logs found</h3>
                <p className="text-gray-600 dark:text-gray-400">
                  Try adjusting your filters or check back later for new logs.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
} 