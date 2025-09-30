'use client'

import React, { useState, useEffect } from 'react'
import { fetchJson } from '@/utils/http'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { SERVER_URL } from '@/utils/config'

interface DashboardData {
  totalRequests: number
  activeUsers: number
  newApis: number
  monthlyUsage: Record<string, number>
  activeUsersList: Array<{
    username: string
    requests: string
    subscribers: number
  }>
  popularApis: Array<{
    name: string
    requests: string
    subscribers: number
  }>
}

const Dashboard = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    totalRequests: 0,
    activeUsers: 0,
    newApis: 0,
    monthlyUsage: {},
    activeUsersList: [],
    popularApis: []
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const { fetchJson } = await import('@/utils/http')
      const data = await fetchJson<DashboardData>(`${SERVER_URL}/platform/dashboard`)
      setDashboardData(data as any)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('An unknown error occurred')
      }
    } finally {
      setLoading(false)
    }
  }

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  return (
    <ProtectedRoute>
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Dashboard</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                Overview of your API gateway performance and usage
              </p>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="btn btn-secondary"
            >
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
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

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Total Monthly Requests</p>
                  <p className="stats-value">{dashboardData.totalRequests.toLocaleString()}</p>
                  <p className="stats-change positive">+17% this month</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-primary-100 dark:bg-primary-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
              </div>
            </div>

            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">Active Monthly Users</p>
                  <p className="stats-value">{dashboardData.activeUsers}</p>
                  <p className="stats-change positive">+4% this month</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-success-100 dark:bg-success-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-success-600 dark:text-success-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                  </svg>
                </div>
              </div>
            </div>

            <div className="stats-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="stats-label">New APIs This Month</p>
                  <p className="stats-value">{dashboardData.newApis}</p>
                  <p className="stats-change positive">+25% this month</p>
                </div>
                <div className="h-12 w-12 rounded-lg bg-warning-100 dark:bg-warning-900/20 flex items-center justify-center">
                  <svg className="h-6 w-6 text-warning-600 dark:text-warning-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 card">
              <div className="card-header">
                <h3 className="card-title">Monthly Usage</h3>
              </div>
              <div className="h-64 flex items-end justify-between gap-2 px-4 pb-8">
                {(() => {
                  const values = months.map(month => dashboardData.monthlyUsage[month] || 0)
                  const maxValue = Math.max(...values, 1)
                  const chartHeight = 200

                  return months.map((month) => {
                    const value = dashboardData.monthlyUsage[month] || 0
                    const barHeight = maxValue > 0 ? (value / maxValue) * chartHeight : 4

                    return (
                      <div key={month} className="flex-1 flex flex-col items-center">
                        <div
                          className="w-full bg-gradient-to-t from-primary-500 to-primary-600 rounded-t-lg transition-all duration-300 hover:from-primary-600 hover:to-primary-700"
                          style={{
                            height: `${Math.max(barHeight, 4)}px`
                          }}
                        ></div>
                        <span className="text-xs text-gray-500 dark:text-gray-400 mt-2">{month}</span>
                      </div>
                    )
                  })
                })()}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Most Active Users</h3>
              </div>
              <div className="space-y-4">
                {dashboardData.activeUsersList.map((user, index) => (
                  <div key={user.username} className="flex items-center space-x-3">
                    <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-sm font-medium">
                      {user.username.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {user.username}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        Requests: {user.requests}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        Subscribers: {user.subscribers}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Popular APIs This Month</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Requests</th>
                    <th>Subscribers</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.popularApis.map((api, index) => (
                    <tr key={index}>
                      <td className="font-medium">{api.name}</td>
                      <td>{api.requests}</td>
                      <td>{api.subscribers}</td>
                      <td>
                        <button className="btn btn-ghost btn-sm">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

export default Dashboard
