'use client'

import React, { useState, useEffect } from 'react'
import ConfirmModal from '@/components/ConfirmModal'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { fetchJson } from '@/utils/http'
import { PROTECTED_USERS, SERVER_URL } from '@/utils/config'

interface User {
  username: string
  email: string
  role: string
  groups: string[]
  rate_limit_duration: number
  rate_limit_duration_type: string
  throttle_duration: number
  throttle_duration_type: string
  throttle_wait_duration: number
  throttle_wait_duration_type: string
  throttle_queue_limit: number | null
  custom_attributes: Record<string, string>
  active: boolean
  ui_access?: boolean
}

interface UpdateUserData {
  username?: string
  email?: string
  password?: string
  role?: string
  groups?: string[]
  rate_limit_duration?: number
  rate_limit_duration_type?: string
  throttle_duration?: number
  throttle_duration_type?: string
  throttle_wait_duration?: number
  throttle_wait_duration_type?: string
  throttle_queue_limit?: number | null
  custom_attributes?: Record<string, string>
  active?: boolean
  ui_access?: boolean
}

const UserDetailPage = () => {
  const router = useRouter()
  const params = useParams()
  const username = params.username as string
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editData, setEditData] = useState<UpdateUserData>({})
  const [newCustomAttribute, setNewCustomAttribute] = useState({ key: '', value: '' })
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleting, setDeleting] = useState(false)
  const isProtected = PROTECTED_USERS.includes((username || '').toLowerCase())

  useEffect(() => {
    const userData = sessionStorage.getItem('selectedUser')
    if (userData) {
      try {
        const parsedUser = JSON.parse(userData)
        setUser(parsedUser)
        setEditData({
          username: parsedUser.username,
          email: parsedUser.email,
          role: parsedUser.role,
          groups: [...parsedUser.groups],
          rate_limit_duration: parsedUser.rate_limit_duration,
          rate_limit_duration_type: parsedUser.rate_limit_duration_type,
          throttle_duration: parsedUser.throttle_duration,
          throttle_duration_type: parsedUser.throttle_duration_type,
          throttle_wait_duration: parsedUser.throttle_wait_duration,
          throttle_wait_duration_type: parsedUser.throttle_wait_duration_type,
          throttle_queue_limit: parsedUser.throttle_queue_limit,
          custom_attributes: { ...parsedUser.custom_attributes },
          active: parsedUser.active,
          ui_access: parsedUser.ui_access
        })
        setLoading(false)
      } catch (err) {
        setError('Failed to load user data')
        setLoading(false)
      }
    } else {
      setError('No user data found')
      setLoading(false)
    }
  }, [username])

  const handleBack = () => {
    router.push('/users')
  }

  const formatDuration = (duration: number, durationType: string) => {
    return `${duration} ${durationType}${duration !== 1 ? 's' : ''}`
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    if (user) {
      setEditData({
        username: user.username,
        email: user.email,
        role: user.role,
        groups: [...user.groups],
        rate_limit_duration: user.rate_limit_duration,
        rate_limit_duration_type: user.rate_limit_duration_type,
        throttle_duration: user.throttle_duration,
        throttle_duration_type: user.throttle_duration_type,
        throttle_wait_duration: user.throttle_wait_duration,
        throttle_wait_duration_type: user.throttle_wait_duration_type,
        throttle_queue_limit: user.throttle_queue_limit,
        custom_attributes: { ...user.custom_attributes },
        active: user.active,
        ui_access: user.ui_access
      })
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      if (isProtected) {
        setError('Editing this user is disabled by policy')
        return
      }
      await (await import('@/utils/api')).putJson(`${SERVER_URL}/platform/user/${encodeURIComponent(username)}`, editData)

      // Refresh from server to get the latest canonical data
      const refreshedUser = await fetchJson(`${SERVER_URL}/platform/user/${encodeURIComponent(username)}`)
      setUser(refreshedUser)
      // Keep sessionStorage in sync for back-navigation
      sessionStorage.setItem('selectedUser', JSON.stringify(refreshedUser))
      setIsEditing(false)
      setSuccess('User updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update user. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field: keyof UpdateUserData, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }))
  }

  const handleGroupChange = (index: number, value: string) => {
    setEditData(prev => ({
      ...prev,
      groups: prev.groups?.map((group, i) => i === index ? value : group) || []
    }))
  }

  const addGroup = () => {
    const newGroup = prompt('Enter group name:')
    if (newGroup && newGroup.trim() && !editData.groups?.includes(newGroup.trim())) {
      setEditData(prev => ({
        ...prev,
        groups: [...(prev.groups || []), newGroup.trim()]
      }))
    }
  }

  const removeGroup = (index: number) => {
    setEditData(prev => ({
      ...prev,
      groups: prev.groups?.filter((_, i) => i !== index) || []
    }))
  }

  const addCustomAttribute = () => {
    if (newCustomAttribute.key.trim() && newCustomAttribute.value.trim()) {
      setEditData(prev => ({
        ...prev,
        custom_attributes: {
          ...prev.custom_attributes,
          [newCustomAttribute.key.trim()]: newCustomAttribute.value.trim()
        }
      }))
      setNewCustomAttribute({ key: '', value: '' })
    }
  }

  const removeCustomAttribute = (key: string) => {
    setEditData(prev => {
      const newAttributes = { ...prev.custom_attributes }
      delete newAttributes[key]
      return { ...prev, custom_attributes: newAttributes }
    })
  }

  const handleDeleteClick = () => {
    setShowDeleteModal(true)
  }

  const handleDeleteCancel = () => {
    setShowDeleteModal(false)
    setDeleteConfirmation('')
  }

  const handleDeleteConfirm = async () => {
    try {
      setDeleting(true)
      setError(null)
      
      if (isProtected) {
        setError('Deleting this user is disabled by policy')
        return
      }
      const { delJson } = await import('@/utils/api')
      await delJson(`${SERVER_URL}/platform/user/${encodeURIComponent(username)}`)

      router.push('/users')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to delete user. Please try again.')
      }
    } finally {
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="spinner mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading user details...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error && !user) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">User Details</h1>
            </div>
            <button onClick={handleBack} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Users
            </button>
          </div>
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
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">{user?.username || 'User Details'}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage user account and permissions
            </p>
          </div>
          <div className="flex gap-2">
            {!isEditing ? (
              <>
                <button onClick={handleEdit} disabled={isProtected} className="btn btn-primary disabled:opacity-50">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit User
                </button>
                <button onClick={handleDeleteClick} disabled={isProtected} className="btn btn-error disabled:opacity-50">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Delete User
                </button>
              </>
            ) : (
              <>
                <button onClick={handleSave} disabled={saving} className="btn btn-primary">
                  {saving ? (
                    <div className="flex items-center">
                      <div className="spinner mr-2"></div>
                      Saving...
                    </div>
                  ) : (
                    <>
                      <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Save Changes
                    </>
                  )}
                </button>
                <button onClick={handleCancel} className="btn btn-secondary">
                  Cancel
                </button>
              </>
            )}
            <button onClick={handleBack} className="btn btn-ghost">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back
            </button>
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <div className="rounded-lg bg-success-50 border border-success-200 p-4 dark:bg-success-900/20 dark:border-success-800">
            <div className="flex">
              <svg className="h-5 w-5 text-success-400 dark:text-success-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="ml-3">
                <p className="text-sm text-success-700 dark:text-success-300">{success}</p>
              </div>
            </div>
          </div>
        )}

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

        {user && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {isProtected && (
              <div className="rounded-lg bg-warning-50 border border-warning-200 p-4 dark:bg-warning-900/20 dark:border-warning-800">
                <div className="flex">
                  <svg className="h-5 w-5 text-warning-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M5.22 19h13.56A2 2 0 0020.6 16.2L13.9 4.8a2 2 0 00-3.48 0L3.4 16.2A2 2 0 005.22 19z" />
                  </svg>
                  <div className="ml-3">
                    <p className="text-sm text-warning-800 dark:text-warning-200">This account is protected by policy and cannot be edited or deleted.</p>
                  </div>
                </div>
              </div>
            )}
            {/* Basic Information */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Basic Information</h3>
                <FormHelp docHref="/docs/using-fields.html#users">Update identity, role, status, and UI access.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Username
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.username || ''}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      className="input"
                      placeholder="Enter username"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{user.username}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Email
                  </label>
                  {isEditing ? (
                    <input
                      type="email"
                      value={editData.email || ''}
                      onChange={(e) => handleInputChange('email', e.target.value)}
                      className="input"
                      placeholder="Enter email"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{user.email}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Role
                    <InfoTooltip text="Platform role controls permissions (e.g., manage_apis, view_logs)." />
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.role || ''}
                      onChange={(e) => handleInputChange('role', e.target.value)}
                      className="input"
                      placeholder="Enter role"
                    />
                  ) : (
                    <span className="badge badge-primary">{user.role}</span>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Status
                    <InfoTooltip text="Inactive users cannot authenticate until re-enabled. Does not affect public or no-auth APIs." />
                  </label>
                  {isEditing ? (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={editData.active || false}
                        onChange={(e) => handleInputChange('active', e.target.checked)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Active
                      </label>
                    </div>
                  ) : (
                    <span className={`badge ${user.active ? 'badge-success' : 'badge-error'}`}>
                      {user.active ? 'Active' : 'Inactive'}
                    </span>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    UI Access
                    <InfoTooltip text="Controls access to the admin UI. API access is controlled per API (Public/Auth Required settings)." />
                  </label>
                  {isEditing ? (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={editData.ui_access || false}
                        onChange={(e) => handleInputChange('ui_access', e.target.checked)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Allow UI access
                      </label>
                    </div>
                  ) : (
                    <span className={`badge ${user.ui_access ? 'badge-success' : 'badge-gray'}`}>
                      {user.ui_access ? 'Enabled' : 'Disabled'}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Groups */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Groups</h3>
                <FormHelp docHref="/docs/using-fields.html#access-control">Groups are used in API access checks alongside roles.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <button onClick={addGroup} className="btn btn-primary">
                    <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add Group
                  </button>
                )}
                
                <div className="space-y-2">
                  {(isEditing ? editData.groups : user.groups)?.map((group, index) => (
                    <div key={index} className="flex items-center gap-2">
                      {isEditing ? (
                        <input
                          type="text"
                          value={group}
                          onChange={(e) => handleGroupChange(index, e.target.value)}
                          className="input flex-1"
                          placeholder="Enter group name"
                        />
                      ) : (
                        <span className="text-sm bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-200 px-3 py-1 rounded-full flex-1">
                          {group}
                        </span>
                      )}
                      {isEditing && (
                        <button
                          onClick={() => removeGroup(index)}
                          className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? user.groups : editData.groups)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No groups assigned</p>
                )}
              </div>
            </div>

            {/* Rate Limiting */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Rate Limiting</h3>
                <FormHelp docHref="/docs/using-fields.html#rate-limit">Limits requests per user over a time window.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Rate Limit Duration
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {isEditing ? (
                      <>
                        <input
                          type="number"
                          value={editData.rate_limit_duration || 0}
                          onChange={(e) => handleInputChange('rate_limit_duration', parseInt(e.target.value))}
                          className="input"
                          min="0"
                        />
                        <select
                          value={editData.rate_limit_duration_type || ''}
                          onChange={(e) => handleInputChange('rate_limit_duration_type', e.target.value)}
                          className="input"
                        >
                          <option value="seconds">Seconds</option>
                          <option value="minutes">Minutes</option>
                          <option value="hours">Hours</option>
                        </select>
                      </>
                    ) : (
                      <p className="text-gray-900 dark:text-white">
                        {formatDuration(user.rate_limit_duration, user.rate_limit_duration_type)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Throttling */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Throttling</h3>
                <FormHelp docHref="/docs/using-fields.html#throttle">Control bursts with duration, wait, and queue size.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Throttle Duration
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {isEditing ? (
                      <>
                        <input
                          type="number"
                          value={editData.throttle_duration || 0}
                          onChange={(e) => handleInputChange('throttle_duration', parseInt(e.target.value))}
                          className="input"
                          min="0"
                        />
                        <select
                          value={editData.throttle_duration_type || ''}
                          onChange={(e) => handleInputChange('throttle_duration_type', e.target.value)}
                          className="input"
                        >
                          <option value="seconds">Seconds</option>
                          <option value="minutes">Minutes</option>
                          <option value="hours">Hours</option>
                        </select>
                      </>
                    ) : (
                      <p className="text-gray-900 dark:text-white">
                        {formatDuration(user.throttle_duration, user.throttle_duration_type)}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Wait Duration
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {isEditing ? (
                      <>
                        <input
                          type="number"
                          value={editData.throttle_wait_duration || 0}
                          onChange={(e) => handleInputChange('throttle_wait_duration', parseInt(e.target.value))}
                          className="input"
                          min="0"
                        />
                        <select
                          value={editData.throttle_wait_duration_type || ''}
                          onChange={(e) => handleInputChange('throttle_wait_duration_type', e.target.value)}
                          className="input"
                        >
                          <option value="seconds">Seconds</option>
                          <option value="minutes">Minutes</option>
                          <option value="hours">Hours</option>
                        </select>
                      </>
                    ) : (
                      <p className="text-gray-900 dark:text-white">
                        {formatDuration(user.throttle_wait_duration, user.throttle_wait_duration_type)}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Queue Limit
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      value={editData.throttle_queue_limit || 0}
                      onChange={(e) => handleInputChange('throttle_queue_limit', parseInt(e.target.value))}
                      className="input"
                      min="0"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{user.throttle_queue_limit || 'No limit'}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Custom Attributes */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Custom Attributes</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={newCustomAttribute.key}
                      onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, key: e.target.value }))}
                      className="input"
                      placeholder="Attribute key"
                    />
                    <input
                      type="text"
                      value={newCustomAttribute.value}
                      onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, value: e.target.value }))}
                      className="input"
                      placeholder="Attribute value"
                    />
                    <button onClick={addCustomAttribute} className="btn btn-primary col-span-2">
                      Add Attribute
                    </button>
                  </div>
                )}
                
                <div className="space-y-2">
                  {Object.entries(isEditing ? editData.custom_attributes || {} : user.custom_attributes).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-sm bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-200 px-3 py-1 rounded flex-1">
                        <strong>{key}:</strong> {value}
                      </span>
                      {isEditing && (
                        <button
                          onClick={() => removeCustomAttribute(key)}
                          className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {Object.keys(isEditing ? editData.custom_attributes || {} : user.custom_attributes).length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No custom attributes</p>
                )}
              </div>
            </div>
          </div>
        )}

        <ConfirmModal
          open={showDeleteModal}
          title="Delete User"
          message={<>
            This action cannot be undone. This will permanently delete the user "{user?.username}".
          </>}
          confirmLabel={deleting ? 'Deleting...' : 'Delete User'}
          cancelLabel="Cancel"
          onCancel={handleDeleteCancel}
          onConfirm={handleDeleteConfirm}
          
        />
      </div>
    </Layout>
  )
}

export default UserDetailPage 
