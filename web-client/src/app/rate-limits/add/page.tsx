'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { postJson } from '@/utils/api'

export default function AddRateLimitRulePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    rule_id: '',
    rule_type: 'per_user',
    time_window: 'minute',
    limit: 100,
    target_identifier: '',
    burst_allowance: 0,
    priority: 0,
    enabled: true,
    description: ''
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await postJson('/platform/rate-limits/rules', formData)
      router.push('/rate-limits')
    } catch (err: any) {
      console.error('Failed to create rule:', err)
      setError(err.message || 'Failed to create rate limit rule')
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : 
              type === 'number' ? parseInt(value) || 0 : value
    }))
  }

  const needsTarget = ['per_user', 'per_api', 'per_endpoint', 'per_ip'].includes(formData.rule_type)

  return (
    <ProtectedRoute requiredPermission="manage_rate_limits">
      <Layout>
        <div className="max-w-3xl mx-auto space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Add Rate Limit Rule</h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">Create a new rate limiting rule</p>
          </div>

          {error && (
            <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
              <p className="text-sm text-error-700 dark:text-error-300">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="card p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Rule ID *
                </label>
                <input
                  type="text"
                  name="rule_id"
                  value={formData.rule_id}
                  onChange={handleChange}
                  required
                  className="input w-full"
                  placeholder="e.g., rule_user_limit"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Rule Type *
                </label>
                <select
                  name="rule_type"
                  value={formData.rule_type}
                  onChange={handleChange}
                  className="input w-full"
                >
                  <option value="per_user">Per User</option>
                  <option value="per_api">Per API</option>
                  <option value="per_endpoint">Per Endpoint</option>
                  <option value="per_ip">Per IP</option>
                  <option value="global">Global</option>
                </select>
              </div>

              {needsTarget && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Target Identifier *
                  </label>
                  <input
                    type="text"
                    name="target_identifier"
                    value={formData.target_identifier}
                    onChange={handleChange}
                    required={needsTarget}
                    className="input w-full"
                    placeholder={
                      formData.rule_type === 'per_user' ? 'Username' :
                      formData.rule_type === 'per_api' ? 'API name' :
                      formData.rule_type === 'per_endpoint' ? 'Endpoint URI' :
                      'IP address'
                    }
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Time Window *
                </label>
                <select
                  name="time_window"
                  value={formData.time_window}
                  onChange={handleChange}
                  className="input w-full"
                >
                  <option value="second">Second</option>
                  <option value="minute">Minute</option>
                  <option value="hour">Hour</option>
                  <option value="day">Day</option>
                  <option value="month">Month</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Limit *
                </label>
                <input
                  type="number"
                  name="limit"
                  value={formData.limit}
                  onChange={handleChange}
                  required
                  min="1"
                  className="input w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Burst Allowance
                </label>
                <input
                  type="number"
                  name="burst_allowance"
                  value={formData.burst_allowance}
                  onChange={handleChange}
                  min="0"
                  className="input w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Priority
                </label>
                <input
                  type="number"
                  name="priority"
                  value={formData.priority}
                  onChange={handleChange}
                  className="input w-full"
                />
                <p className="mt-1 text-xs text-gray-500">Higher priority rules are checked first</p>
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Description
                </label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  rows={3}
                  className="input w-full"
                  placeholder="Optional description"
                />
              </div>

              <div className="md:col-span-2">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    name="enabled"
                    checked={formData.enabled}
                    onChange={handleChange}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                    Enable rule immediately
                  </span>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button
                type="button"
                onClick={() => router.back()}
                className="btn btn-outline"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Rule'}
              </button>
            </div>
          </form>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
