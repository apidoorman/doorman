'use client'

import React, { useState, useEffect, useCallback } from 'react'
import Pagination from '@/components/Pagination'
import { getCookie } from '@/utils/http'
import { SERVER_URL } from '@/utils/config'
import { format } from 'date-fns'
import { ChangeEvent } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuth } from '@/contexts/AuthContext'

interface Log {
  timestamp: string
  request_id?: string
  level: string
  message: string
  source: string
  user?: string
  endpoint?: string
  method?: string
  ip_address?: string
  response_time?: string
  status_code?: string
  api?: string
  protocol?: string
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

interface GroupedLogs {
  request_id: string
  logs: Log[]
  first_timestamp: string
  last_timestamp: string
  user?: string
  method?: string
  endpoint?: string
  response_time?: string
  has_error: boolean
  expanded_logs?: Log[]
}

type OverrideKey = string

export default function LogsPage() {
  const { permissions } = useAuth()
  const canExport = !!permissions?.export_logs
  const [logs, setLogs] = useState<Log[]>([])
  const [groupedLogs, setGroupedLogs] = useState<GroupedLogs[]>([])
  const [logsPage, setLogsPage] = useState(1)
  const [logsPageSize, setLogsPageSize] = useState(10)
  const [logsHasNext, setLogsHasNext] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [filesLoading, setFilesLoading] = useState(false)
  const [filesError, setFilesError] = useState<string | null>(null)
  const [logFiles, setLogFiles] = useState<string[]>([])
  const [expandedRequests, setExpandedRequests] = useState<Set<string>>(new Set())
  const [loadingExpanded, setLoadingExpanded] = useState<Set<string>>(new Set())
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [filters, setFilters] = useState<FilterState>(() => {
    const now = new Date()
    const today = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0')

    return {
      startDate: today,
      endDate: today,
      startTime: '',
      endTime: '',
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

  const [overrideMap, setOverrideMap] = useState<Record<OverrideKey, boolean>>({})

  const ensureEndpointOverridesLoaded = async (apiPath: string) => {
    try {
      const parts = apiPath.replace(/^\//, '').split('/')
      if (parts.length < 2) return
      const api_name = parts[0]
      const api_version = parts[1]
      const keyPrefix = `${api_name}|${api_version}|`
      if (Object.keys(overrideMap).some(k => k.includes(keyPrefix))) return
      const { fetchJson } = await import('@/utils/http')
      const responseData: any = await fetchJson(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(api_name)}/${encodeURIComponent(api_version)}`)
      const data = responseData
      const eps: any[] = data.endpoints || []
      const next: Record<OverrideKey, boolean> = {}
      eps.forEach(ep => {
        const k: OverrideKey = `${ep.endpoint_method}|${ep.api_name}|${ep.api_version}|${ep.endpoint_uri}`
        next[k] = Array.isArray(ep.endpoint_servers) && ep.endpoint_servers.length > 0
      })
      setOverrideMap(prev => ({ ...prev, ...next }))
    } catch {}
  }

  const toQueryParams = (f: FilterState) => {
    const qp = new URLSearchParams()
    const map: Record<string,string> = {
      startDate: 'start_date',
      endDate: 'end_date',
      startTime: 'start_time',
      endTime: 'end_time',
      request_id: 'request_id',
      ipAddress: 'ip_address',
      minResponseTime: 'min_response_time',
      maxResponseTime: 'max_response_time',
      user: 'user',
      endpoint: 'endpoint',
      method: 'method',
      level: 'level'
    }
    Object.entries(f).forEach(([k,v]) => {
      if (!v) return
      const key = (map as any)[k] || k
      qp.append(key, v)
    })
    return qp
  }

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const queryParams = toQueryParams(filters)
      queryParams.append('limit', String(logsPageSize))
      queryParams.append('offset', String((logsPage - 1) * logsPageSize))

      const { fetchJson } = await import('@/utils/http')
      const csrf = getCookie('csrf_token')
      const response = await fetch(`${SERVER_URL}/platform/logging/logs?${queryParams}`, { credentials: 'include', headers: { 'Accept':'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }})

      if (!response.ok) {
        throw new Error('Failed to fetch logs')
      }

      const responseRequestId = response.headers.get('request_id')
      if (responseRequestId) {
        setCurrentRequestId(responseRequestId)
      }

      const data = await response.json()
      const logList = data.response?.logs || data.logs || []
      const hasMore = (data.response?.has_more ?? data.has_more) ?? (Array.isArray(logList) && logList.length === logsPageSize)
      setLogs(logList)
      setLogsHasNext(!!hasMore)

      const uniqueRequestIds: string[] = Array.from(
        new Set<string>(
          logList
            .map((log: Log): string | undefined => log.request_id)
            .filter((id: string | undefined): id is string => typeof id === 'string' && id.length > 0)
        )
      )

      const completeLogs: Log[] = []
      for (const requestId of uniqueRequestIds) {
        if (requestId && requestId !== responseRequestId) {
          try {
            const completeQueryParams = new URLSearchParams()
            completeQueryParams.append('request_id', requestId)
            completeQueryParams.append('limit', '1000')

            const csrf2 = getCookie('csrf_token')
            const completeResponse = await fetch(`${SERVER_URL}/platform/logging/logs?${completeQueryParams}`, { credentials: 'include', headers: { 'Accept': 'application/json', ...(csrf2 ? { 'X-CSRF-Token': csrf2 } : {}) }})

            if (completeResponse.ok) {
              const completeData = await completeResponse.json()
              const requestLogs = completeData.response?.logs || completeData.logs || []
              completeLogs.push(...requestLogs)
            }
          } catch (error) {
            console.error(`Failed to fetch complete logs for request ${requestId}:`, error)
          }
        }
      }

      const grouped = groupLogsByRequestId(completeLogs)
      setGroupedLogs(grouped)
    } catch (error) {
      setError('Failed to fetch logs. Please try again later.')
      setLogs([])
      setGroupedLogs([])
    } finally {
      setLoading(false)
    }
  }, [filters, logsPage, logsPageSize])

  const fetchLogFiles = useCallback(async () => {
    try {
      setFilesLoading(true)
      setFilesError(null)
      const csrf = getCookie('csrf_token')
      const resp = await fetch(`${SERVER_URL}/platform/logging/logs/files`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }
      })
      if (!resp.ok) throw new Error('Failed to fetch log files')
      const data = await resp.json().catch(() => ({}))
      const files: string[] = data.response?.log_files || data.log_files || []
      setLogFiles(files)
    } catch (e:any) {
      setFilesError(e?.message || 'Failed to fetch log files')
      setLogFiles([])
    } finally {
      setFilesLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLogFiles().catch(() => {})
  }, [fetchLogFiles])

  const fetchLogsForRequestId = useCallback(async (requestId: string) => {
    try {
      setLoadingExpanded(prev => new Set(prev).add(requestId))

      const queryParams = new URLSearchParams()
      queryParams.append('request_id', requestId)
      queryParams.append('limit', '1000')

      const csrf3 = getCookie('csrf_token')
      const response = await fetch(`${SERVER_URL}/platform/logging/logs?${queryParams}`, { credentials: 'include', headers: { 'Accept': 'application/json', ...(csrf3 ? { 'X-CSRF-Token': csrf3 } : {}) }})

      if (!response.ok) {
        throw new Error('Failed to fetch logs for request ID')
      }

      const data = await response.json()
      const allLogsForRequest = data.response?.logs || data.logs || []

      setGroupedLogs(prev => prev.map(group => {
        if (group.request_id === requestId) {
          const sortedExpandedLogs = allLogsForRequest.sort((a: Log, b: Log) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
          const firstLog = sortedExpandedLogs[0]
          const lastLog = sortedExpandedLogs[sortedExpandedLogs.length - 1]

          const responseTimeLog = sortedExpandedLogs.find((log: Log) => log.response_time)
          const userLog = sortedExpandedLogs.find((log: Log) => log.user)
          const endpointLog = sortedExpandedLogs.find((log: Log) => log.endpoint && log.method)
          const hasError = sortedExpandedLogs.some((log: Log) => log.level.toLowerCase() === 'error')

          console.log(`Expanding request ${requestId}:`, {
            totalLogs: allLogsForRequest.length,
            userLog: userLog?.user,
            endpointLog: endpointLog?.endpoint,
            methodLog: endpointLog?.method,
            responseTimeLog: responseTimeLog?.response_time,
            hasError
          })

          return {
            ...group,
            expanded_logs: allLogsForRequest,
            first_timestamp: firstLog?.timestamp || group.first_timestamp,
            last_timestamp: lastLog?.timestamp || group.last_timestamp,
            user: userLog?.user || group.user,
            method: endpointLog?.method || group.method,
            endpoint: endpointLog?.endpoint || group.endpoint,
            response_time: responseTimeLog?.response_time || group.response_time,
            has_error: hasError
          }
        }
        return group
      }))
    } catch (error) {
      console.error('Failed to fetch logs for request ID:', error)
      setError('Failed to fetch detailed logs for this request.')
    } finally {
      setLoadingExpanded(prev => {
        const newSet = new Set(prev)
        newSet.delete(requestId)
        return newSet
      })
    }
  }, [])

  const groupLogsByRequestId = (logList: Log[]): GroupedLogs[] => {
    const groups: { [key: string]: Log[] } = {}

    logList.forEach(log => {
      const requestId = log.request_id || 'no-request-id'
      if (!groups[requestId]) {
        groups[requestId] = []
      }
      groups[requestId].push(log)
    })

    return Object.entries(groups)
      .filter(([requestId, logs]) => {
        if (currentRequestId && requestId === currentRequestId) {
          return false
        }
        return true
      })
      .map(([requestId, logs]) => {
        const sortedLogs = logs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        const firstLog = sortedLogs[0]
        const lastLog = sortedLogs[sortedLogs.length - 1]

        const responseTimeLog = sortedLogs.find(log => log.response_time)
        const userLog = sortedLogs.find(log => log.user)
        const endpointLog = sortedLogs.find(log => log.endpoint && log.method)
        const apiHintLog = sortedLogs.find(log => log.api)?.api
        if (apiHintLog) {
          ensureEndpointOverridesLoaded(apiHintLog as string)
        }
        const hasError = sortedLogs.some(log => log.level.toLowerCase() === 'error')

        return {
          request_id: requestId,
          logs: sortedLogs,
          first_timestamp: firstLog.timestamp,
          last_timestamp: lastLog.timestamp,
          user: userLog?.user,
          method: endpointLog?.method,
          endpoint: endpointLog?.endpoint,
          response_time: responseTimeLog?.response_time,
          has_error: hasError
        }
      }).sort((a, b) => new Date(b.first_timestamp).getTime() - new Date(a.first_timestamp).getTime())
  }

  useEffect(() => {
    if (hasSearched) {
      fetchLogs()
    }
  }, [fetchLogs, hasSearched])

  const handleFilterChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
  }

  const clearFilters = () => {
    const now = new Date()
    const today = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0')
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
    setHasSearched(false)
    setLogs([])
    setGroupedLogs([])
    setError(null)
  }

  const handleSearch = () => {
    setLogsPage(1)
    setHasSearched(true)
  }

  const toggleRequestExpansion = async (requestId: string) => {
    const newExpanded = new Set(expandedRequests)
    if (newExpanded.has(requestId)) {
      newExpanded.delete(requestId)
      setExpandedRequests(newExpanded)
    } else {
      newExpanded.add(requestId)
      setExpandedRequests(newExpanded)

      const group = groupedLogs.find(g => g.request_id === requestId)
      if (!group?.expanded_logs) {
        await fetchLogsForRequestId(requestId)
      }
    }
  }

  const exportLogs = async (format: 'json' | 'csv') => {
    try {
      setExporting(true)
      const queryParams = toQueryParams(filters)
      queryParams.append('format', format)
      const csrf = getCookie('csrf_token')
      const response = await fetch(`${SERVER_URL}/platform/logging/logs/download?${queryParams}`, {
        credentials: 'include',
        headers: { ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }
      })
      if (!response.ok) throw new Error('Failed to download logs')
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') || ''
      const match = /filename="?([^";]+)"?/i.exec(disposition)
      const filename = match?.[1] || `logs-${new Date().toISOString().split('T')[0]}.${format}`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      setError('Failed to download logs. Please try again later.')
    } finally {
      setExporting(false)
    }
  }

  const downloadLatest = async (format: 'json' | 'csv') => {
    try {
      setExporting(true)
      const params = new URLSearchParams()
      params.append('format', format)
      const csrf = getCookie('csrf_token')
      const response = await fetch(`${SERVER_URL}/platform/logging/logs/download?${params.toString()}`, {
        credentials: 'include',
        headers: { ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }
      })
      if (!response.ok) throw new Error('Failed to download latest logs')
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') || ''
      const match = /filename="?([^";]+)"?/i.exec(disposition)
      const filename = match?.[1] || `logs-latest.${format === 'json' ? 'json' : 'csv'}`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (e) {
      setError('Failed to download latest logs.')
    } finally {
      setExporting(false)
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
    <ProtectedRoute requiredPermission="view_logs">
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Logs</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              View and analyze system logs and API requests
            </p>
          </div>
          <div className="flex gap-2" />
          {logFiles.length > 0 && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              <div className="flex flex-wrap gap-2">
                {logFiles.slice(0, 10).map((f, i) => (
                  <span key={i} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded font-mono">{f}</span>
                ))}
                {logFiles.length > 10 && <span className="italic">+{logFiles.length - 10} more</span>}
              </div>
            </div>
          )}
        </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Filters</h3>
            </div>
            <div className="p-6">
              <div className="mb-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button onClick={fetchLogFiles} className="btn btn-secondary" disabled={filesLoading}>
                    <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    {filesLoading ? 'Refreshing Files...' : 'Refresh Files'}
                  </button>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {filesError ? <span className="text-error-600">{filesError}</span> : (
                      <>
                        <span className="mr-2">Available log files:</span>
                        <span className="font-mono">{logFiles.length}</span>
                      </>
                    )}
                  </div>
                </div>
                {canExport && (
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => exportLogs('json')} disabled={exporting} className="btn btn-secondary">Download JSON</button>
                    <button onClick={() => exportLogs('csv')} disabled={exporting} className="btn btn-secondary">Download CSV</button>
                    <button onClick={() => downloadLatest('json')} disabled={exporting} className="btn btn-outline">Latest JSON</button>
                    <button onClick={() => downloadLatest('csv')} disabled={exporting} className="btn btn-outline">Latest CSV</button>
                  </div>
                )}
              </div>
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
              <button onClick={handleSearch} className="btn btn-primary">
                Search Logs
              </button>
              <button
                onClick={() => setShowMoreFilters(!showMoreFilters)}
                className="btn btn-outline"
              >
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.207A1 1 0 013 6.5V4z" />
                </svg>
                {showMoreFilters ? 'Hide Advanced Filters' : 'Show Advanced Filters'}
              </button>
              <button onClick={clearFilters} className="btn btn-secondary">
                Clear Filters
              </button>
            </div>
          </div>
        </div>

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
          /* Grouped Logs Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Request ID</th>
                    <th>Start Time</th>
                    <th>Duration</th>
                    <th>User</th>
                    <th>Endpoint</th>
                    <th>Routing</th>
                    <th>Method</th>
                    <th>Response Time</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {groupedLogs.map((group) => (
                    <React.Fragment key={group.request_id}>
                      <tr
                        onClick={() => toggleRequestExpansion(group.request_id)}
                        className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                      >
                        <td>
                          <button className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                            <svg
                              className={`h-4 w-4 transform transition-transform ${expandedRequests.has(group.request_id) ? 'rotate-90' : ''}`}
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        </td>
                        <td>
                          <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                            {group.request_id}
                          </p>
                        </td>
                        <td>
                          <p className="text-sm text-gray-900 dark:text-white">
                            {format(new Date(group.first_timestamp), 'MMM dd, yyyy HH:mm:ss')}
                          </p>
                        </td>
                        <td>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            {(group.expanded_logs || group.logs).length} log{(group.expanded_logs || group.logs).length !== 1 ? 's' : ''}
                          </p>
                        </td>
                        <td>
                          <p className="text-sm text-gray-900 dark:text-white">
                            {group.user || '-'}
                          </p>
                        </td>
                        <td>
                          <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                            {group.endpoint || '-'}
                          </p>
                        </td>
                        <td>
                          {(() => {
                            if (!group.endpoint || !group.method) return '-'
                            const m = (group.endpoint || '').match(/^\/?([^/]+\/v\d+)(?:\/(.*))?$/)
                            if (!m) return '-'
                            const apiPath = m[1]
                            const epUri = '/' + (m[2] || '')
                            const parts = apiPath.split('/')
                            if (parts.length < 2) return '-'
                            const api_name = parts[0]
                            const api_version = parts[1]
                            const k: OverrideKey = `${group.method}|${api_name}|${api_version}|${epUri}`
                            const hasOverride = !!overrideMap[k]
                            return (
                              <span className={`badge ${hasOverride ? 'badge-primary' : 'badge-gray'}`} title="Routing precedence: client-key → endpoint → API">
                                {hasOverride ? 'Endpoint override' : 'API default'}
                              </span>
                            )
                          })()}
                        </td>
                        <td>
                          <span className={`badge ${group.method === 'GET' ? 'badge-success' : group.method === 'POST' ? 'badge-primary' : 'badge-warning'}`}>
                            {group.method || '-'}
                          </span>
                        </td>
                        <td>
                          <p className="text-sm text-gray-900 dark:text-white">
                            {group.response_time ? `${parseFloat(group.response_time).toFixed(2)}ms` : '-'}
                          </p>
                        </td>
                        <td>
                          <span className={`badge ${group.has_error ? 'badge-error' : 'badge-success'}`}>
                            {group.has_error ? 'Error' : 'Success'}
                          </span>
                        </td>
                      </tr>

                      {expandedRequests.has(group.request_id) && (
                        <tr>
                          <td colSpan={10} className="p-0">
                            <div className="bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                              <div className="p-4">
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                                  All Logs for Request: {group.request_id}
                                </h4>

                                {loadingExpanded.has(group.request_id) ? (
                                  <div className="flex items-center justify-center py-8">
                                    <div className="spinner mr-3"></div>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">Loading all logs for this request...</p>
                                  </div>
                                ) : (
                                  <div className="space-y-2">
                                    {((group.expanded_logs || group.logs) || []).map((log, index) => (
                                      <div key={index} className="flex items-start space-x-4 p-2 bg-white dark:bg-gray-900 rounded border">
                                        <div className="flex-shrink-0">
                                          <span className={`badge ${getLevelBgColor(log.level)}`}>
                                            {log.level}
                                          </span>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <div className="flex items-center space-x-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                                            <span>{format(new Date(log.timestamp), 'HH:mm:ss.SSS')}</span>
                                            <span>•</span>
                                            <span>{log.source}</span>
                                          </div>
                                          <p className="text-sm text-gray-900 dark:text-white">
                                            {log.message}
                                          </p>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              page={logsPage}
              pageSize={logsPageSize}
              onPageChange={setLogsPage}
              onPageSizeChange={(s) => { setLogsPageSize(s); setLogsPage(1) }}
              hasNext={logsHasNext}
            />

            {!hasSearched ? (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">Ready to search logs</h3>
                <p className="text-gray-600 dark:text-gray-400">
                  Use the filters above to search for specific logs and click "Search Logs" to get started.
                </p>
              </div>
            ) : groupedLogs.length === 0 && !loading && (
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
    </ProtectedRoute>
  )
}
