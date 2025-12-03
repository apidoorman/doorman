'use client'

import React, { useState } from 'react'

interface UserMetrics {
  user: string
  count: number
  apis_used?: string[]
  quota_usage?: number
  quota_limit?: number
  last_active?: number
  avg_latency?: number
  error_count?: number
}

interface TopUsersTableProps {
  data: UserMetrics[]
  onUserClick?: (username: string) => void
  onExport?: (format: 'csv' | 'json') => void
}

type SortField = 'user' | 'count' | 'apis_used' | 'quota_usage' | 'last_active'
type SortDirection = 'asc' | 'desc'

export default function TopUsersTable({ data, onUserClick, onExport }: TopUsersTableProps) {
  const [sortField, setSortField] = useState<SortField>('count')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [searchTerm, setSearchTerm] = useState('')

  // Format helpers
  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toLocaleString()
  }

  const formatQuota = (used?: number, limit?: number): string => {
    if (used === undefined || limit === undefined) return 'N/A'
    const percentage = (used / limit) * 100
    return `${percentage.toFixed(0)}%`
  }

  const formatLastActive = (timestamp?: number): string => {
    if (!timestamp) return 'N/A'
    const date = new Date(timestamp * 1000)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
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
      item.user.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      let aVal: any = a[sortField]
      let bVal: any = b[sortField]

      // Special handling for arrays
      if (sortField === 'apis_used') {
        aVal = a.apis_used?.length || 0
        bVal = b.apis_used?.length || 0
      }

      // Special handling for quota
      if (sortField === 'quota_usage') {
        aVal = a.quota_usage && a.quota_limit ? (a.quota_usage / a.quota_limit) : 0
        bVal = b.quota_usage && b.quota_limit ? (b.quota_usage / b.quota_limit) : 0
      }

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
      const headers = ['Username', 'Total Requests', 'APIs Used', 'Quota Usage', 'Last Active']
      const rows = sortedData.map(item => [
        item.user,
        item.count.toString(),
        item.apis_used?.length.toString() || '0',
        formatQuota(item.quota_usage, item.quota_limit),
        formatLastActive(item.last_active)
      ])
      
      const csv = [headers, ...rows].map(row => row.join(',')).join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `top-users-${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      const json = JSON.stringify(sortedData, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `top-users-${new Date().toISOString().split('T')[0]}.json`
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
              placeholder="Search users..."
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
                  onClick={() => handleSort('user')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Username
                  <SortIcon field="user" />
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
                  onClick={() => handleSort('apis_used')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  APIs Used
                  <SortIcon field="apis_used" />
                </button>
              </th>
              <th>
                <button
                  onClick={() => handleSort('quota_usage')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Quota Usage
                  <SortIcon field="quota_usage" />
                </button>
              </th>
              <th>
                <button
                  onClick={() => handleSort('last_active')}
                  className="flex items-center gap-2 hover:text-primary-600"
                >
                  Last Active
                  <SortIcon field="last_active" />
                </button>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-gray-500 dark:text-gray-400">
                  No users found
                </td>
              </tr>
            ) : (
              sortedData.map((item, index) => {
                const quotaPercentage = item.quota_usage && item.quota_limit 
                  ? (item.quota_usage / item.quota_limit) * 100 
                  : 0

                return (
                  <tr key={item.user} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="font-medium text-gray-500 dark:text-gray-400">
                      #{index + 1}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-full bg-primary-100 dark:bg-primary-900/20 flex items-center justify-center">
                          <span className="text-sm font-medium text-primary-800 dark:text-primary-400">
                            {item.user.substring(0, 2).toUpperCase()}
                          </span>
                        </div>
                        <span className="font-medium text-gray-900 dark:text-white">
                          {item.user}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {formatNumber(item.count)}
                      </span>
                    </td>
                    <td>
                      <span className="text-gray-700 dark:text-gray-300">
                        {item.apis_used?.length || 0} APIs
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              quotaPercentage > 90
                                ? 'bg-error-500'
                                : quotaPercentage > 70
                                ? 'bg-warning-500'
                                : 'bg-success-500'
                            }`}
                            style={{ width: `${Math.min(quotaPercentage, 100)}%` }}
                          />
                        </div>
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                          {formatQuota(item.quota_usage, item.quota_limit)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        {formatLastActive(item.last_active)}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => onUserClick && onUserClick(item.user)}
                        className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 font-medium text-sm"
                      >
                        View Details →
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Results count */}
      <div className="text-sm text-gray-600 dark:text-gray-400">
        Showing {sortedData.length} of {data.length} users
      </div>
    </div>
  )
}
