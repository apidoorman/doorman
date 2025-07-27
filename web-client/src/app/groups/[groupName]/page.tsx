'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'

interface Group {
  group_name: string
  group_description: string
  api_access?: string[]
}

const GroupDetailPage = () => {
  const router = useRouter()
  const params = useParams()
  const groupName = params.groupName as string
  
  const [group, setGroup] = useState<Group | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState<Partial<Group>>({})
  const [saving, setSaving] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [newApi, setNewApi] = useState('')

  useEffect(() => {
    fetchGroup()
  }, [groupName])

  const fetchGroup = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Try to get from sessionStorage first
      const savedGroup = sessionStorage.getItem('selectedGroup')
      if (savedGroup) {
        const parsedGroup = JSON.parse(savedGroup)
        if (parsedGroup.group_name === groupName) {
          setGroup(parsedGroup)
          setEditData(parsedGroup)
          setLoading(false)
          return
        }
      }

      // Fetch from API if not in sessionStorage
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to load group')
      }
      
      const data = await response.json()
      setGroup(data)
      setEditData(data)
    } catch (err) {
      setError('Failed to load group. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    router.push('/groups')
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    if (group) {
      setEditData(group)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
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
        throw new Error(errorData.detail || 'Failed to update group')
      }
      
      const updatedGroup = await response.json()
      setGroup(updatedGroup)
      setIsEditing(false)
      setSuccess('Group updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update group. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (deleteConfirmation !== group?.group_name) {
      setError('Group name does not match')
      return
    }

    try {
      setDeleting(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to delete group')
      }
      
      router.push('/groups')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to delete group. Please try again.')
      }
    } finally {
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  const handleInputChange = (field: keyof Group, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }))
  }

  const handleApiAccessChange = (index: number, value: string) => {
    setEditData(prev => ({
      ...prev,
      api_access: prev.api_access?.map((api, i) => i === index ? value : api) || []
    }))
  }

  const addApiAccess = () => {
    if (newApi.trim() && !editData.api_access?.includes(newApi.trim())) {
      setEditData(prev => ({
        ...prev,
        api_access: [...(prev.api_access || []), newApi.trim()]
      }))
      setNewApi('')
    }
  }

  const removeApiAccess = (index: number) => {
    setEditData(prev => ({
      ...prev,
      api_access: prev.api_access?.filter((_, i) => i !== index) || []
    }))
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="spinner mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading group details...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error && !group) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Group Details</h1>
            </div>
            <button onClick={handleBack} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Groups
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
            <h1 className="page-title">{group?.group_name || 'Group Details'}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage group configuration and API access
            </p>
          </div>
          <div className="flex gap-2">
            {!isEditing ? (
              <>
                <button onClick={handleEdit} className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit Group
                </button>
                <button onClick={() => setShowDeleteModal(true)} className="btn btn-error">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Delete Group
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

        {group && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Information */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Basic Information</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Group Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.group_name || ''}
                      onChange={(e) => handleInputChange('group_name', e.target.value)}
                      className="input"
                      placeholder="Enter group name"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{group.group_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  {isEditing ? (
                    <textarea
                      value={editData.group_description || ''}
                      onChange={(e) => handleInputChange('group_description', e.target.value)}
                      className="input resize-none"
                      rows={3}
                      placeholder="Enter group description"
                    />
                  ) : (
                    <p className="text-gray-600 dark:text-gray-400">{group.group_description || 'No description'}</p>
                  )}
                </div>
              </div>
            </div>

            {/* API Access */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">API Access</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newApi}
                      onChange={(e) => setNewApi(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter API name to grant access"
                      onKeyPress={(e) => e.key === 'Enter' && addApiAccess()}
                    />
                    <button onClick={addApiAccess} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="space-y-2">
                  {(isEditing ? editData.api_access : group.api_access)?.map((api, index) => (
                    <div key={index} className="flex items-center gap-2">
                      {isEditing ? (
                        <input
                          type="text"
                          value={api}
                          onChange={(e) => handleApiAccessChange(index, e.target.value)}
                          className="input flex-1"
                          placeholder="Enter API name"
                        />
                      ) : (
                        <span className="text-sm bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full flex-1">
                          {api}
                        </span>
                      )}
                      {isEditing && (
                        <button
                          onClick={() => removeApiAccess(index)}
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
                
                {(!isEditing ? group.api_access : editData.api_access)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No APIs assigned</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Delete Modal */}
        {showDeleteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={() => setShowDeleteModal(false)}></div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Delete Group</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                This action cannot be undone. This will permanently delete the group "{group?.group_name}".
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Please type <strong>{group?.group_name}</strong> to confirm.
              </p>
              <input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                className="input w-full mb-4"
                placeholder="Enter group name to confirm"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleDelete}
                  disabled={deleteConfirmation !== group?.group_name || deleting}
                  className="btn btn-error flex-1"
                >
                  {deleting ? (
                    <div className="flex items-center justify-center">
                      <div className="spinner mr-2"></div>
                      Deleting...
                    </div>
                  ) : (
                    'Delete Group'
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

export default GroupDetailPage 