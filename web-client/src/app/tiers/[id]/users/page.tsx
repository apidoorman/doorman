'use client'

import React, { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { getJson, postJson, delJson, fetchAllPaginated } from '@/utils/api'
import SearchableSelect from '@/components/SearchableSelect'
import { SERVER_URL } from '@/utils/config'

interface TierAssignment {
  user_id: string
  tier_id: string
  effective_from?: string
  expiration_date?: string
  notes?: string
}

interface Tier {
  tier_id: string
  name: string
  display_name: string
  requests_per_minute?: number
  requests_per_hour?: number
  monthly_request_quota?: number
}

export default function TierUsersPage() {
  const params = useParams()
  const router = useRouter()
  const tierId = params.id as string
  
  const [tier, setTier] = useState<Tier | null>(null)
  const [assignments, setAssignments] = useState<TierAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [newUserId, setNewUserId] = useState('')
  const [expirationDate, setExpirationDate] = useState('')
  const [notes, setNotes] = useState('')
  const [assigning, setAssigning] = useState(false)
  
  const fetchUserOptions = async (): Promise<string[]> => {
    try {
      const users = await fetchAllPaginated<any>(
        (page, size) => `${SERVER_URL}/platform/user/all?page=${page}&page_size=${size}`,
        (data) => (data?.users || data?.response?.users || []),
        undefined,
        undefined,
        'cache:users:all'
      )
      return users.map((u: any) => u?.username).filter(Boolean)
    } catch (e) {
      console.error('Failed to fetch users:', e)
      return []
    }
  }

  useEffect(() => {
    fetchData()
  }, [tierId])

  const fetchData = async () => {
    try {
      setLoading(true)
      
      // Fetch tier details
      const tierData = await getJson(`${SERVER_URL}/platform/tiers/${tierId}`)
      setTier(tierData)
      
      // Fetch users assigned to this tier
      const assignmentsData = await getJson(`${SERVER_URL}/platform/tiers/${tierId}/users`)
      setAssignments(assignmentsData || [])
      
      setError(null)
    } catch (err: any) {
      console.error('Failed to fetch tier data:', err)
      setError(err.message || 'Failed to load tier data')
    } finally {
      setLoading(false)
    }
  }

  const handleAssignUser = async () => {
    if (!newUserId.trim()) {
      alert('Please enter a user ID')
      return
    }

    try {
      setAssigning(true)
      
      await postJson(`${SERVER_URL}/platform/tiers/assignments`, {
        user_id: newUserId.trim(),
        tier_id: tierId,
        expiration_date: expirationDate || undefined,
        notes: notes || undefined
      })
      
      await fetchData()
      setShowAssignModal(false)
      setNewUserId('')
      setExpirationDate('')
      setNotes('')
      
    } catch (err: any) {
      alert(err.message || 'Failed to assign user to tier')
    } finally {
      setAssigning(false)
    }
  }

  const handleRemoveUser = async (userId: string) => {
    if (!confirm(`Remove ${userId} from this tier?`)) return

    try {
      await delJson(`${SERVER_URL}/platform/tiers/assignments/${userId}`)
      await fetchData()
    } catch (err: any) {
      alert(err.message || 'Failed to remove user from tier')
    }
  }

  if (loading) {
    return (
      <ProtectedRoute requiredPermission="manage_tiers">
        <Layout>
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="spinner mx-auto mb-4"></div>
              <p className="text-gray-600 dark:text-gray-400">Loading tier users...</p>
            </div>
          </div>
        </Layout>
      </ProtectedRoute>
    )
  }

  return (
    <ProtectedRoute requiredPermission="manage_tiers">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">
                {tier?.display_name || tier?.name || 'Tier'} - Assigned Users
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                Manage users assigned to this tier
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowAssignModal(true)}
                className="btn btn-primary"
              >
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Assign User
              </button>
              <button
                onClick={() => router.push('/tiers')}
                className="btn btn-secondary"
              >
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back to Tiers
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
              <div className="flex">
                <svg className="h-5 w-5 text-error-400 dark:text-error-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="ml-3">
                  <p className="text-sm text-error-700 dark:text-error-300">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Tier Info Card */}
          {tier && (
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Tier Details
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Requests/Minute</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {tier.requests_per_minute?.toLocaleString() || 'Unlimited'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Requests/Hour</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {tier.requests_per_hour?.toLocaleString() || 'Unlimited'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Monthly Quota</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    {tier.monthly_request_quota?.toLocaleString() || 'Unlimited'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Assigned Users */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                Assigned Users ({assignments.length})
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>User ID</th>
                    <th>Effective From</th>
                    <th>Expiration Date</th>
                    <th>Notes</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {assignments.length > 0 ? (
                    assignments.map((assignment) => (
                      <tr key={assignment.user_id}>
                        <td className="font-medium">{assignment.user_id}</td>
                        <td>
                          {assignment.effective_from
                            ? new Date(assignment.effective_from).toLocaleDateString()
                            : '-'}
                        </td>
                        <td>
                          {assignment.expiration_date ? (
                            <span className="badge badge-warning">
                              {new Date(assignment.expiration_date).toLocaleDateString()}
                            </span>
                          ) : (
                            <span className="badge badge-success">Permanent</span>
                          )}
                        </td>
                        <td className="text-sm text-gray-600 dark:text-gray-400">
                          {assignment.notes || '-'}
                        </td>
                        <td>
                          <button
                            onClick={() => handleRemoveUser(assignment.user_id)}
                            className="btn btn-sm btn-error"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="text-center text-gray-500 dark:text-gray-400 py-8">
                        No users assigned to this tier
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Assign User Modal */}
        {showAssignModal && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen px-4">
              <div className="fixed inset-0 bg-black/50" onClick={() => setShowAssignModal(false)} />
              
              <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                  Assign User to Tier
                </h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Username *
                    </label>
                    <SearchableSelect
                      value={newUserId}
                      onChange={setNewUserId}
                      fetchOptions={fetchUserOptions}
                      placeholder="Select username"
                      restrictToOptions
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Expiration Date (Optional)
                    </label>
                    <input
                      type="date"
                      value={expirationDate}
                      onChange={(e) => setExpirationDate(e.target.value)}
                      className="input"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Leave empty for permanent assignment
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Notes (Optional)
                    </label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      className="input"
                      rows={3}
                      placeholder="Add notes about this assignment"
                    />
                  </div>
                </div>
                
                <div className="flex gap-2 mt-6">
                  <button
                    onClick={handleAssignUser}
                    disabled={assigning}
                    className="btn btn-primary flex-1"
                  >
                    {assigning ? (
                      <>
                        <div className="spinner mr-2"></div>
                        Assigning...
                      </>
                    ) : (
                      'Assign User'
                    )}
                  </button>
                  <button
                    onClick={() => setShowAssignModal(false)}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </Layout>
    </ProtectedRoute>
  )
}
