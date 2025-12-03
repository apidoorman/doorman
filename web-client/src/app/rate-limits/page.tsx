'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { getJson, postJson, delJson } from '@/utils/api'

interface RateLimitRule {
  rule_id: string
  rule_type: string
  time_window: string
  limit: number
  target_identifier?: string
  burst_allowance: number
  priority: number
  enabled: boolean
  description?: string
  created_at?: string
  updated_at?: string
}

export default function RateLimitsPage() {
  const router = useRouter()
  const [rules, setRules] = useState<RateLimitRule[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [selectedRules, setSelectedRules] = useState<string[]>([])

  useEffect(() => {
    fetchRules()
  }, [filterType])

  const fetchRules = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (filterType !== 'all') {
        params.append('rule_type', filterType)
      }
      
      const data = await getJson(`/platform/rate-limits/rules?${params}`)
      setRules(data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch rules:', err)
      setError('Failed to load rate limit rules')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return

    try {
      await delJson(`/platform/rate-limits/rules/${ruleId}`)
      await fetchRules()
    } catch (err) {
      console.error('Failed to delete rule:', err)
      alert('Failed to delete rule')
    }
  }

  const handleToggleEnabled = async (ruleId: string, enabled: boolean) => {
    try {
      const endpoint = enabled ? 'disable' : 'enable'
      await postJson(`/platform/rate-limits/rules/${ruleId}/${endpoint}`, {})
      await fetchRules()
    } catch (err) {
      console.error('Failed to toggle rule:', err)
      alert('Failed to update rule')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedRules.length === 0) return
    if (!confirm(`Delete ${selectedRules.length} rules?`)) return

    try {
      await postJson('/platform/rate-limits/rules/bulk/delete', { rule_ids: selectedRules })
      setSelectedRules([])
      await fetchRules()
    } catch (err) {
      console.error('Failed to bulk delete:', err)
      alert('Failed to delete rules')
    }
  }

  const handleBulkEnable = async () => {
    if (selectedRules.length === 0) return

    try {
      await postJson('/platform/rate-limits/rules/bulk/enable', { rule_ids: selectedRules })
      setSelectedRules([])
      await fetchRules()
    } catch (err) {
      console.error('Failed to bulk enable:', err)
      alert('Failed to enable rules')
    }
  }

  const handleBulkDisable = async () => {
    if (selectedRules.length === 0) return

    try {
      await postJson('/platform/rate-limits/rules/bulk/disable', { rule_ids: selectedRules })
      setSelectedRules([])
      await fetchRules()
    } catch (err) {
      console.error('Failed to bulk disable:', err)
      alert('Failed to disable rules')
    }
  }

  const handleExport = () => {
    const dataStr = JSON.stringify(rules, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rate-limit-rules-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredRules = rules.filter(rule =>
    searchTerm === '' ||
    rule.rule_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    rule.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    rule.target_identifier?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const toggleSelectRule = (ruleId: string) => {
    setSelectedRules(prev =>
      prev.includes(ruleId) ? prev.filter(id => id !== ruleId) : [...prev, ruleId]
    )
  }

  const toggleSelectAll = () => {
    if (selectedRules.length === filteredRules.length) {
      setSelectedRules([])
    } else {
      setSelectedRules(filteredRules.map(r => r.rule_id))
    }
  }

  return (
    <ProtectedRoute requiredPermission="manage_rate_limits">
      <Layout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Rate Limit Rules
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Manage rate limiting rules for APIs, users, and endpoints
              </p>
            </div>
            <button
              onClick={() => router.push('/rate-limits/add')}
              className="btn btn-primary"
            >
              <svg className="h-5 w-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Rule
            </button>
          </div>

          {/* Filters and Search */}
          <div className="card p-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search rules..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="input w-full"
                />
              </div>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="input"
              >
                <option value="all">All Types</option>
                <option value="per_user">Per User</option>
                <option value="per_api">Per API</option>
                <option value="per_endpoint">Per Endpoint</option>
                <option value="per_ip">Per IP</option>
                <option value="global">Global</option>
              </select>
              <button onClick={handleExport} className="btn btn-outline">
                Export
              </button>
            </div>
          </div>

          {/* Bulk Actions */}
          {selectedRules.length > 0 && (
            <div className="card p-4 bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {selectedRules.length} rule{selectedRules.length !== 1 ? 's' : ''} selected
                </span>
                <div className="flex gap-2">
                  <button onClick={handleBulkEnable} className="btn btn-sm btn-outline">
                    Enable
                  </button>
                  <button onClick={handleBulkDisable} className="btn btn-sm btn-outline">
                    Disable
                  </button>
                  <button onClick={handleBulkDelete} className="btn btn-sm btn-outline text-error-600">
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Rules Table */}
          <div className="card overflow-hidden">
            {loading ? (
              <div className="p-8 text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                <p className="mt-2 text-gray-600 dark:text-gray-400">Loading rules...</p>
              </div>
            ) : error ? (
              <div className="p-8 text-center text-error-600">{error}</div>
            ) : filteredRules.length === 0 ? (
              <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                No rules found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="w-12">
                        <input
                          type="checkbox"
                          checked={selectedRules.length === filteredRules.length}
                          onChange={toggleSelectAll}
                          className="rounded"
                        />
                      </th>
                      <th>Rule ID</th>
                      <th>Type</th>
                      <th>Target</th>
                      <th>Limit</th>
                      <th>Window</th>
                      <th>Burst</th>
                      <th>Priority</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRules.map((rule) => (
                      <tr key={rule.rule_id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedRules.includes(rule.rule_id)}
                            onChange={() => toggleSelectRule(rule.rule_id)}
                            className="rounded"
                          />
                        </td>
                        <td>
                          <div className="font-mono text-sm font-medium">{rule.rule_id}</div>
                          {rule.description && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {rule.description}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700">
                            {rule.rule_type.replace('per_', '')}
                          </span>
                        </td>
                        <td>
                          <span className="text-sm font-mono">
                            {rule.target_identifier || '-'}
                          </span>
                        </td>
                        <td className="font-semibold">{rule.limit}</td>
                        <td>{rule.time_window}</td>
                        <td>{rule.burst_allowance || 0}</td>
                        <td>
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-primary-100 dark:bg-primary-900/20 text-primary-800 dark:text-primary-400">
                            {rule.priority}
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => handleToggleEnabled(rule.rule_id, rule.enabled)}
                            className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                              rule.enabled
                                ? 'bg-success-100 text-success-800 dark:bg-success-900/20 dark:text-success-400'
                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400'
                            }`}
                          >
                            {rule.enabled ? 'Enabled' : 'Disabled'}
                          </button>
                        </td>
                        <td>
                          <div className="flex gap-2">
                            <button
                              onClick={() => router.push(`/rate-limits/${rule.rule_id}/edit`)}
                              className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDelete(rule.rule_id)}
                              className="text-error-600 hover:text-error-700 text-sm font-medium"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
