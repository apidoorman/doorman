'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'

interface Role {
  role_name: string
  role_description: string
  manage_users?: boolean
  manage_apis?: boolean
  manage_endpoints?: boolean
  manage_groups?: boolean
  manage_roles?: boolean
  manage_routings?: boolean
  manage_gateway?: boolean
  manage_subscriptions?: boolean
  view_logs?: boolean
  export_logs?: boolean
}

const RoleDetailPage = () => {
  const router = useRouter()
  const params = useParams()
  const roleName = params.roleName as string
  
  const [role, setRole] = useState<Role | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState<Partial<Role>>({})
  const [saving, setSaving] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

  useEffect(() => {
    fetchRole()
  }, [roleName])

  const fetchRole = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Try to get from sessionStorage first
      const savedRole = sessionStorage.getItem('selectedRole')
      if (savedRole) {
        const parsedRole = JSON.parse(savedRole)
        if (parsedRole.role_name === roleName) {
          setRole(parsedRole)
          setEditData(parsedRole)
          setLoading(false)
          return
        }
      }

      // Fetch from API if not in sessionStorage
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to load role')
      }
      
      const data = await response.json()
      setRole(data)
      setEditData(data)
    } catch (err) {
      setError('Failed to load role. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    router.push('/roles')
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    setEditData(role || {})
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        },
        body: JSON.stringify(editData)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error_message || 'Failed to update role')
      }
      
      const updatedRole = await response.json()
      setRole(updatedRole)
      setIsEditing(false)
      setSuccess('Role updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update role. Please try again later.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (deleteConfirmation !== role?.role_name) {
      setError('Role name does not match')
      return
    }

    try {
      setDeleting(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to delete role')
      }
      
      router.push('/roles')
    } catch (err) {
      setError('Failed to delete role. Please try again later.')
      setShowDeleteModal(false)
    } finally {
      setDeleting(false)
    }
  }

  const handleInputChange = (field: keyof Role, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }))
  }

  const handlePermissionChange = (permission: keyof Role, value: boolean) => {
    setEditData(prev => ({ ...prev, [permission]: value }))
  }

  const getPermissionCount = (roleData: Role) => {
    return Object.values(roleData).filter(val => typeof val === 'boolean' && val).length
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="spinner mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading role details...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error && !role) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Role Details</h1>
            </div>
            <button onClick={handleBack} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Roles
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
            <h1 className="page-title">{role?.role_name || 'Role Details'}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage role permissions and settings
            </p>
          </div>
          <div className="flex gap-2">
            {!isEditing ? (
              <>
                <button onClick={handleEdit} className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit Role
                </button>
                <button onClick={() => setShowDeleteModal(true)} className="btn btn-error">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Delete Role
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

        {role && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Information */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Basic Information</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Role Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.role_name || ''}
                      onChange={(e) => handleInputChange('role_name', e.target.value)}
                      className="input"
                      placeholder="Enter role name"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{role.role_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  {isEditing ? (
                    <textarea
                      value={editData.role_description || ''}
                      onChange={(e) => handleInputChange('role_description', e.target.value)}
                      className="input resize-none"
                      rows={3}
                      placeholder="Enter role description"
                    />
                  ) : (
                    <p className="text-gray-600 dark:text-gray-400">{role.role_description || 'No description'}</p>
                  )}
                </div>

                {!isEditing && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Total Permissions
                    </label>
                    <span className="badge badge-primary">
                      {getPermissionCount(role)} permission{getPermissionCount(role) !== 1 ? 's' : ''} enabled
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Permissions */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Permissions</h3>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-1 gap-3">
                  {[
                    { key: 'manage_users', label: 'Manage Users', description: 'Create, edit, and delete user accounts' },
                    { key: 'manage_apis', label: 'Manage APIs', description: 'Create, edit, and delete API configurations' },
                    { key: 'manage_endpoints', label: 'Manage Endpoints', description: 'Configure API endpoints and validations' },
                    { key: 'manage_groups', label: 'Manage Groups', description: 'Create, edit, and delete user groups' },
                    { key: 'manage_roles', label: 'Manage Roles', description: 'Create, edit, and delete user roles' },
                    { key: 'manage_routings', label: 'Manage Routings', description: 'Configure API routing and load balancing' },
                    { key: 'manage_gateway', label: 'Manage Gateway', description: 'Configure gateway settings and policies' },
                    { key: 'manage_subscriptions', label: 'Manage Subscriptions', description: 'Manage API subscriptions and billing' },
                    { key: 'view_logs', label: 'View Logs', description: 'View system logs and API requests' },
                    { key: 'export_logs', label: 'Export Logs', description: 'Export logs in various formats' }
                  ].map(({ key, label, description }) => (
                    <div key={key} className="flex items-start space-x-3">
                      {isEditing ? (
                        <input
                          type="checkbox"
                          id={key}
                          checked={editData[key as keyof Role] as boolean || false}
                          onChange={(e) => handlePermissionChange(key as keyof Role, e.target.checked)}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded mt-1"
                          disabled={saving}
                        />
                      ) : (
                        <div className={`h-4 w-4 rounded mt-1 flex items-center justify-center ${
                          (role[key as keyof Role] as boolean) 
                            ? 'bg-success-500 text-white' 
                            : 'bg-gray-300 dark:bg-gray-600'
                        }`}>
                          {(role[key as keyof Role] as boolean) && (
                            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </div>
                      )}
                      <div className="flex-1">
                        <label htmlFor={key} className={`block text-sm font-medium ${isEditing ? 'text-gray-700 dark:text-gray-300 cursor-pointer' : 'text-gray-900 dark:text-white'}`}>
                          {label}
                        </label>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Delete Modal */}
        {showDeleteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={() => setShowDeleteModal(false)}></div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Delete Role</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                This action cannot be undone. This will permanently delete the role "{role?.role_name}".
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Please type <strong>{role?.role_name}</strong> to confirm.
              </p>
              <input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                className="input w-full mb-4"
                placeholder="Enter role name to confirm"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleDelete}
                  disabled={deleteConfirmation !== role?.role_name || deleting}
                  className="btn btn-error flex-1"
                >
                  {deleting ? (
                    <div className="flex items-center justify-center">
                      <div className="spinner mr-2"></div>
                      Deleting...
                    </div>
                  ) : (
                    'Delete Role'
                  )}
                </button>
                <button onClick={() => setShowDeleteModal(false)} className="btn btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}

export default RoleDetailPage 