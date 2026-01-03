'use client'

import React, { useState } from 'react'

interface APIMetrics {
  api: string
  count: number
  avg_latency?: number
  error_rate?: number
  error_count?: number
  top_users?: string[]
}

interface TopAPIsTableProps {
  data: APIMetrics[]
  onAPIClick?: (api: string) => void
  onExport?: (format: 'csv' | 'json') => void
}

type SortField = 'api' | 'count' | 'avg_latency' | 'error_rate'
type SortDirection = 'asc' | 'desc'

export default function TopAPIsTable({ data, onAPIClick, onExport }: TopAPIsTableProps) {
  const [sortField, setSortField] = useState<SortField>('count')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [searchTerm, setSearchTerm] = useState('')

  // Format helpers
  const formatNumber = (num?: number): string => {
    if (num === undefined || Number.isNaN(num)) return '0'
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toLocaleString()
  }

  const formatLatency = (ms?: number): string => {
    if (ms === undefined) return 'N/A'
    return `${ms.toFixed(1)}ms`
  }

  const formatErrorRate = (rate?: number): string => {
    if (rate === undefined) return 'N/A'
    return `${(rate * 100).toFixed(2)}%`
  }

  // Sorting logic
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const sortedData = [...data]
    .filter(item => 
      searchTerm === '' || 
      item.api.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      let aVal: any = a[sortField]
      let bVal: any = b[sortField]

      // Handle undefined values
      if (aVal === undefined) aVal = 0
      if (bVal === undefined) bVal = 0

      if (sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1
      } else {
        return aVal < bVal ? 1 : -1
      }
    })

  // Export functionality
  const handleExport = (format: 'csv' | 'json') => {
    if (format === 'csv') {
      const headers = ['API', 'Total Requests', 'Avg Latency (ms)', 'Error Rate', 'Error Count']
      const rows = sortedData.map(item => [
        item.api,
        item.count.toString(),
        item.avg_latency?.toFixed(2) || 'N/A',
        item.error_rate ? (item.error_rate * 100).toFixed(2) + '%' : 'N/A',
        item.error_count?.toString() || '0'
      ])
      
      const csv = [headers, ...rows].map(row => row.join(',')).join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `top-apis-${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      const json = JSON.stringify(sortedData, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `top-apis-${new Date().toISOString().split('T')[0]}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    if (onExport) {
      onExport(format)
    }
  }

  // Sort icon
  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return (
        <svg className="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      )
    }
    return sortDirection === 'asc' ? (
      <svg className="h-4 w-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="h-4 w-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with search and export */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <input
              type="text"
              placeholder="Search APIs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => handleExport('csv')}
            className="btn btn-outline btn-sm"
          >
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            className="btn btn-outline btn-sm"
          >
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export JSON
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="w-12">#</th>
              <th>
                <button
                  onClick={() => handleSort('api')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  API Name
                  <SortIcon field="api" />
                </button>
              </th>
              <th>
                <button
                  onClick={() => handleSort('count')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Total Requests
                  <SortIcon field="count" />
                </button>
              </th>
              <th>
                <button
                  onClick={() => handleSort('avg_latency')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Avg Latency
                  <SortIcon field="avg_latency" />
                </button>
              </th>
              <th>
                <button
                  onClick={() => handleSort('error_rate')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Error Rate
                  <SortIcon field="error_rate" />
                </button>
              </th>
              <th>Top Users</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-gray-500 dark:text-gray-400">
                  No APIs found
                </td>
              </tr>
            ) : (
              sortedData.map((item, index) => (
                <tr key={item.api} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  <td className="font-medium text-gray-500 dark:text-gray-400">
                    #{index + 1}
                  </td>
                  <td>
                    <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">
                      {item.api}
                    </span>
                  </td>
                  <td>
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {formatNumber(item.count)}
                    </span>
                  </td>
                  <td>
                    <span className="text-gray-700 dark:text-gray-300">
                      {formatLatency(item.avg_latency)}
                    </span>
                  </td>
                  <td>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      (item.error_rate || 0) > 0.05
                        ? 'bg-error-100 text-error-800 dark:bg-error-900/20 dark:text-error-400'
                        : 'bg-success-100 text-success-800 dark:bg-success-900/20 dark:text-success-400'
                    }`}>
                      {formatErrorRate(item.error_rate)}
                    </span>
                  </td>
                  <td>
                    {item.top_users && item.top_users.length > 0 ? (
                      <div className="flex -space-x-2">
                        {item.top_users.slice(0, 3).map((user, i) => (
                          <div
                            key={i}
                            className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-primary-100 dark:bg-primary-900/20 border-2 border-white dark:border-gray-800 text-xs font-medium text-primary-800 dark:text-primary-400"
                            title={user}
                          >
                            {user.substring(0, 2).toUpperCase()}
                          </div>
                        ))}
                        {item.top_users.length > 3 && (
                          <div className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-gray-100 dark:bg-gray-700 border-2 border-white dark:border-gray-800 text-xs font-medium text-gray-600 dark:text-gray-400">
                            +{item.top_users.length - 3}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-500 text-sm">N/A</span>
                    )}
                  </td>
                  <td>
                    <button
                      onClick={() => onAPIClick && onAPIClick(item.api)}
                      className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 font-medium text-sm"
                    >
                      View Details →
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Results count */}
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Showing {sortedData.length} of {data.length} APIs
      </div>
    </div>
  )
}
