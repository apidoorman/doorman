'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { getJson, delJson } from '@/utils/api'

interface TierLimits {
  requests_per_second?: number
  requests_per_minute?: number
  requests_per_hour?: number
  requests_per_day?: number
  requests_per_month?: number
  burst_per_second: number
  burst_per_minute: number
  burst_per_hour: number
  monthly_request_quota?: number
  daily_request_quota?: number
  monthly_bandwidth_quota?: number
}

interface Tier {
  tier_id: string
  name: string
  display_name: string
  description?: string
  limits: TierLimits
  price_monthly?: number
  price_yearly?: number
  features: string[]
  is_default: boolean
  enabled: boolean
  created_at?: string
  updated_at?: string
}

interface TierStats {
  tier_id: string
  tier_name: string
  total_users: number
  active_users: number
  inactive_users: number
}

export default function TiersPage() {
  const router = useRouter()
  const [tiers, setTiers] = useState<Tier[]>([])
  const [stats, setStats] = useState<TierStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'list' | 'comparison'>('list')

  useEffect(() => {
    fetchTiers()
    fetchStats()
  }, [])

  const fetchTiers = async () => {
    try {
      setLoading(true)
      const data = await getJson('/platform/tiers')
      setTiers(data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch tiers:', err)
      setError('Failed to load tiers')
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const data = await getJson('/platform/tiers/statistics/all')
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }

  const handleDelete = async (tierId: string) => {
    if (!confirm('Are you sure you want to delete this tier?')) return

    try {
      await delJson(`/platform/tiers/${tierId}`)
      await fetchTiers()
    } catch (err: any) {
      alert(err.message || 'Failed to delete tier')
    }
  }

  const formatNumber = (num?: number) => {
    if (!num) return '-'
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const getTierStats = (tierId: string) => {
    return stats.find(s => s.tier_id === tierId)
  }

  return (
    <ProtectedRoute requiredPermission="manage_tiers">
      <Layout>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Tier Management
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Manage pricing tiers and rate limit plans
              </p>
            </div>
            <div className="flex gap-3">
              <div className="btn-group">
                <button
                  onClick={() => setViewMode('list')}
                  className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-outline'}`}
                >
                  List
                </button>
                <button
                  onClick={() => setViewMode('comparison')}
                  className={`btn btn-sm ${viewMode === 'comparison' ? 'btn-primary' : 'btn-outline'}`}
                >
                  Compare
                </button>
              </div>
              <button
                onClick={() => router.push('/tiers/add')}
                className="btn btn-primary"
              >
                <svg className="h-5 w-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Tier
              </button>
            </div>
          </div>

          {loading ? (
            <div className="card p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-gray-600 dark:text-gray-400">Loading tiers...</p>
            </div>
          ) : error ? (
            <div className="card p-8 text-center text-error-600">{error}</div>
          ) : viewMode === 'list' ? (
            /* List View */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {tiers.map((tier) => {
                const tierStats = getTierStats(tier.tier_id)
                return (
                  <div key={tier.tier_id} className="card p-6 hover:shadow-lg transition-shadow">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                          {tier.display_name}
                        </h3>
                        {tier.is_default && (
                          <span className="inline-block mt-1 px-2 py-1 text-xs font-medium rounded bg-primary-100 text-primary-800 dark:bg-primary-900/20 dark:text-primary-400">
                            Default
                          </span>
                        )}
                      </div>
                      {tier.price_monthly && (
                        <div className="text-right">
                          <p className="text-2xl font-bold text-gray-900 dark:text-white">
                            ${tier.price_monthly}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">per month</p>
                        </div>
                      )}
                    </div>

                    {tier.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                        {tier.description}
                      </p>
                    )}

                    {/* Limits */}
                    <div className="space-y-2 mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
                      {tier.limits.requests_per_minute && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600 dark:text-gray-400">Per Minute:</span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            {formatNumber(tier.limits.requests_per_minute)}
                          </span>
                        </div>
                      )}
                      {tier.limits.requests_per_hour && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600 dark:text-gray-400">Per Hour:</span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            {formatNumber(tier.limits.requests_per_hour)}
                          </span>
                        </div>
                      )}
                      {tier.limits.monthly_request_quota && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600 dark:text-gray-400">Monthly Quota:</span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            {formatNumber(tier.limits.monthly_request_quota)}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Features */}
                    {tier.features.length > 0 && (
                      <div className="mb-4">
                        <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Features:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {tier.features.slice(0, 3).map((feature, idx) => (
                            <span
                              key={idx}
                              className="inline-block px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
                            >
                              {feature}
                            </span>
                          ))}
                          {tier.features.length > 3 && (
                            <span className="inline-block px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-500">
                              +{tier.features.length - 3} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    {tierStats && (
                      <div className="mb-4 p-3 rounded bg-gray-50 dark:bg-gray-800">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-600 dark:text-gray-400">Users:</span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            {tierStats.active_users} active
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => router.push(`/tiers/${tier.tier_id}/edit`)}
                        className="flex-1 btn btn-sm btn-outline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(tier.tier_id)}
                        className="flex-1 btn btn-sm btn-outline text-error-600 hover:bg-error-50 dark:hover:bg-error-900/20"
                        disabled={tier.is_default}
                      >
                        Delete
                      </button>
                    </div>

                    {!tier.enabled && (
                      <p className="mt-2 text-xs text-center text-gray-500 dark:text-gray-400">
                        Disabled
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            /* Comparison View */
            <div className="card overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Feature</th>
                    {tiers.map(tier => (
                      <th key={tier.tier_id} className="text-center">
                        <div className="font-bold">{tier.display_name}</div>
                        {tier.price_monthly && (
                          <div className="text-sm font-normal text-gray-600 dark:text-gray-400">
                            ${tier.price_monthly}/mo
                          </div>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="font-medium">Requests/Minute</td>
                    {tiers.map(tier => (
                      <td key={tier.tier_id} className="text-center">
                        {formatNumber(tier.limits.requests_per_minute)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="font-medium">Requests/Hour</td>
                    {tiers.map(tier => (
                      <td key={tier.tier_id} className="text-center">
                        {formatNumber(tier.limits.requests_per_hour)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="font-medium">Monthly Quota</td>
                    {tiers.map(tier => (
                      <td key={tier.tier_id} className="text-center">
                        {formatNumber(tier.limits.monthly_request_quota)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="font-medium">Burst Allowance</td>
                    {tiers.map(tier => (
                      <td key={tier.tier_id} className="text-center">
                        {tier.limits.burst_per_minute || 0}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="font-medium">Active Users</td>
                    {tiers.map(tier => {
                      const tierStats = getTierStats(tier.tier_id)
                      return (
                        <td key={tier.tier_id} className="text-center">
                          {tierStats?.active_users || 0}
                        </td>
                      )
                    })}
                  </tr>
                  <tr>
                    <td className="font-medium">Actions</td>
                    {tiers.map(tier => (
                      <td key={tier.tier_id} className="text-center">
                        <button
                          onClick={() => router.push(`/tiers/${tier.tier_id}/edit`)}
                          className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                        >
                          Edit
                        </button>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
