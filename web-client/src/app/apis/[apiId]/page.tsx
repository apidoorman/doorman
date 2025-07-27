'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'

interface API {
  api_id: string
  api_name: string
  api_version: string
  api_description: string
  api_allowed_roles: string[]
  api_allowed_groups: string[]
  api_servers: string[]
  api_type: string
  api_allowed_retry_count: number
  api_authorization_field_swap?: string
  api_allowed_headers?: string[]
  api_tokens_enabled: boolean
  api_token_group?: string
  api_path?: string
}

interface UpdateApiData {
  api_name?: string
  api_version?: string
  api_description?: string
  api_allowed_roles?: string[]
  api_allowed_groups?: string[]
  api_servers?: string[]
  api_type?: string
  api_allowed_retry_count?: number
  api_authorization_field_swap?: string
  api_allowed_headers?: string[]
  api_tokens_enabled?: boolean
  api_token_group?: string
}

const ApiDetailPage = () => {
  const router = useRouter()
  const params = useParams()
  const apiId = params.apiId as string
  const [api, setApi] = useState<API | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editData, setEditData] = useState<UpdateApiData>({})
  const [newRole, setNewRole] = useState('')
  const [newGroup, setNewGroup] = useState('')
  const [newServer, setNewServer] = useState('')
  const [newHeader, setNewHeader] = useState('')
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const apiData = sessionStorage.getItem('selectedApi')
    if (apiData) {
      try {
        const parsedApi = JSON.parse(apiData)
        setApi(parsedApi)
        setEditData({
          api_name: parsedApi.api_name,
          api_version: parsedApi.api_version,
          api_description: parsedApi.api_description,
          api_allowed_roles: [...(parsedApi.api_allowed_roles || [])],
          api_allowed_groups: [...(parsedApi.api_allowed_groups || [])],
          api_servers: [...(parsedApi.api_servers || [])],
          api_type: parsedApi.api_type,
          api_allowed_retry_count: parsedApi.api_allowed_retry_count,
          api_authorization_field_swap: parsedApi.api_authorization_field_swap,
          api_allowed_headers: [...(parsedApi.api_allowed_headers || [])],
          api_tokens_enabled: parsedApi.api_tokens_enabled,
          api_token_group: parsedApi.api_token_group
        })
        setLoading(false)
      } catch (err) {
        setError('Failed to load API data')
        setLoading(false)
      }
    } else {
      setError('No API data found')
      setLoading(false)
    }
  }, [apiId])

  const handleBack = () => {
    router.push('/apis')
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    if (api) {
      setEditData({
        api_name: api.api_name,
        api_version: api.api_version,
        api_description: api.api_description,
        api_allowed_roles: [...(api.api_allowed_roles || [])],
        api_allowed_groups: [...(api.api_allowed_groups || [])],
        api_servers: [...(api.api_servers || [])],
        api_type: api.api_type,
        api_allowed_retry_count: api.api_allowed_retry_count,
        api_authorization_field_swap: api.api_authorization_field_swap,
        api_allowed_headers: [...(api.api_allowed_headers || [])],
        api_tokens_enabled: api.api_tokens_enabled,
        api_token_group: api.api_token_group
      })
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/api/${apiId}`, {
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
        throw new Error(errorData.detail || 'Failed to update API')
      }

      const updatedApi = await response.json()
      setApi(updatedApi)
      setIsEditing(false)
      setSuccess('API updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update API. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field: keyof UpdateApiData, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }))
  }

  const addRole = () => {
    if (newRole.trim() && !editData.api_allowed_roles?.includes(newRole.trim())) {
      setEditData(prev => ({
        ...prev,
        api_allowed_roles: [...(prev.api_allowed_roles || []), newRole.trim()]
      }))
      setNewRole('')
    }
  }

  const removeRole = (index: number) => {
    setEditData(prev => ({
      ...prev,
      api_allowed_roles: prev.api_allowed_roles?.filter((_, i) => i !== index) || []
    }))
  }

  const addGroup = () => {
    if (newGroup.trim() && !editData.api_allowed_groups?.includes(newGroup.trim())) {
      setEditData(prev => ({
        ...prev,
        api_allowed_groups: [...(prev.api_allowed_groups || []), newGroup.trim()]
      }))
      setNewGroup('')
    }
  }

  const removeGroup = (index: number) => {
    setEditData(prev => ({
      ...prev,
      api_allowed_groups: prev.api_allowed_groups?.filter((_, i) => i !== index) || []
    }))
  }

  const addServer = () => {
    if (newServer.trim() && !editData.api_servers?.includes(newServer.trim())) {
      setEditData(prev => ({
        ...prev,
        api_servers: [...(prev.api_servers || []), newServer.trim()]
      }))
      setNewServer('')
    }
  }

  const removeServer = (index: number) => {
    setEditData(prev => ({
      ...prev,
      api_servers: prev.api_servers?.filter((_, i) => i !== index) || []
    }))
  }

  const addHeader = () => {
    if (newHeader.trim() && !editData.api_allowed_headers?.includes(newHeader.trim())) {
      setEditData(prev => ({
        ...prev,
        api_allowed_headers: [...(prev.api_allowed_headers || []), newHeader.trim()]
      }))
      setNewHeader('')
    }
  }

  const removeHeader = (index: number) => {
    setEditData(prev => ({
      ...prev,
      api_allowed_headers: prev.api_allowed_headers?.filter((_, i) => i !== index) || []
    }))
  }

  const handleDeleteClick = () => {
    setShowDeleteModal(true)
  }

  const handleDeleteCancel = () => {
    setShowDeleteModal(false)
    setDeleteConfirmation('')
  }

  const handleDeleteConfirm = async () => {
    if (deleteConfirmation !== api?.api_name) {
      setError('API name does not match')
      return
    }

    try {
      setDeleting(true)
      setError(null)
      
      const response = await fetch(`http://localhost:3002/platform/api/${apiId}`, {
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
        throw new Error(errorData.detail || 'Failed to delete API')
      }

      router.push('/apis')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to delete API. Please try again.')
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
            <p className="text-gray-600 dark:text-gray-400">Loading API details...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error && !api) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">API Details</h1>
            </div>
            <button onClick={handleBack} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to APIs
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
            <h1 className="page-title">{api?.api_name || 'API Details'}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage API configuration and settings
            </p>
          </div>
          <div className="flex gap-2">
            {!isEditing ? (
              <>
                <button onClick={handleEdit} className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit API
                </button>
                <button onClick={handleDeleteClick} className="btn btn-error">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Delete API
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

        {api && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Information */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Basic Information</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.api_name || ''}
                      onChange={(e) => handleInputChange('api_name', e.target.value)}
                      className="input"
                      placeholder="Enter API name"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{api.api_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Version
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.api_version || ''}
                      onChange={(e) => handleInputChange('api_version', e.target.value)}
                      className="input"
                      placeholder="Enter API version"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{api.api_version}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Type
                  </label>
                  {isEditing ? (
                    <select
                      value={editData.api_type || ''}
                      onChange={(e) => handleInputChange('api_type', e.target.value)}
                      className="input"
                    >
                      <option value="REST">REST</option>
                      <option value="GraphQL">GraphQL</option>
                      <option value="SOAP">SOAP</option>
                      <option value="gRPC">gRPC</option>
                    </select>
                  ) : (
                    <span className="badge badge-primary">{api.api_type}</span>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  {isEditing ? (
                    <textarea
                      value={editData.api_description || ''}
                      onChange={(e) => handleInputChange('api_description', e.target.value)}
                      className="input resize-none"
                      rows={3}
                      placeholder="Enter API description"
                    />
                  ) : (
                    <p className="text-gray-600 dark:text-gray-400">{api.api_description || 'No description'}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Retry Count
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      value={editData.api_allowed_retry_count || 0}
                      onChange={(e) => handleInputChange('api_allowed_retry_count', parseInt(e.target.value))}
                      className="input"
                      min="0"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{api.api_allowed_retry_count}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Configuration */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Configuration</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Tokens Enabled
                  </label>
                  {isEditing ? (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={editData.api_tokens_enabled || false}
                        onChange={(e) => handleInputChange('api_tokens_enabled', e.target.checked)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Enable API tokens
                      </label>
                    </div>
                  ) : (
                    <span className={`badge ${api.api_tokens_enabled ? 'badge-success' : 'badge-gray'}`}>
                      {api.api_tokens_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  )}
                </div>

                {api.api_tokens_enabled && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Token Group
                    </label>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editData.api_token_group || ''}
                        onChange={(e) => handleInputChange('api_token_group', e.target.value)}
                        className="input"
                        placeholder="Enter token group"
                      />
                    ) : (
                      <p className="text-gray-900 dark:text-white">{api.api_token_group || 'Default'}</p>
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Authorization Field Swap
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.api_authorization_field_swap || ''}
                      onChange={(e) => handleInputChange('api_authorization_field_swap', e.target.value)}
                      className="input"
                      placeholder="Enter authorization field swap"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{api.api_authorization_field_swap || 'None'}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Allowed Roles */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Allowed Roles</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter role name"
                      onKeyPress={(e) => e.key === 'Enter' && addRole()}
                    />
                    <button onClick={addRole} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="flex flex-wrap gap-2">
                  {(isEditing ? editData.api_allowed_roles : api.api_allowed_roles)?.map((role, index) => (
                    <div key={index} className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{role}</span>
                      {isEditing && (
                        <button
                          onClick={() => removeRole(index)}
                          className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? api.api_allowed_roles : editData.api_allowed_roles)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No roles assigned</p>
                )}
              </div>
            </div>

            {/* Allowed Groups */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Allowed Groups</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newGroup}
                      onChange={(e) => setNewGroup(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter group name"
                      onKeyPress={(e) => e.key === 'Enter' && addGroup()}
                    />
                    <button onClick={addGroup} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="flex flex-wrap gap-2">
                  {(isEditing ? editData.api_allowed_groups : api.api_allowed_groups)?.map((group, index) => (
                    <div key={index} className="flex items-center gap-2 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{group}</span>
                      {isEditing && (
                        <button
                          onClick={() => removeGroup(index)}
                          className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? api.api_allowed_groups : editData.api_allowed_groups)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No groups assigned</p>
                )}
              </div>
            </div>

            {/* Servers */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Servers</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newServer}
                      onChange={(e) => setNewServer(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter server URL"
                      onKeyPress={(e) => e.key === 'Enter' && addServer()}
                    />
                    <button onClick={addServer} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="space-y-2">
                  {(isEditing ? editData.api_servers : api.api_servers)?.map((server, index) => (
                    <div key={index} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded">
                      <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{server}</span>
                      {isEditing && (
                        <button
                          onClick={() => removeServer(index)}
                          className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? api.api_servers : editData.api_servers)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No servers configured</p>
                )}
              </div>
            </div>

            {/* Allowed Headers */}
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Allowed Headers</h3>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newHeader}
                      onChange={(e) => setNewHeader(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter header name"
                      onKeyPress={(e) => e.key === 'Enter' && addHeader()}
                    />
                    <button onClick={addHeader} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="flex flex-wrap gap-2">
                  {(isEditing ? editData.api_allowed_headers : api.api_allowed_headers)?.map((header, index) => (
                    <div key={index} className="flex items-center gap-2 bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{header}</span>
                      {isEditing && (
                        <button
                          onClick={() => removeHeader(index)}
                          className="text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? api.api_allowed_headers : editData.api_allowed_headers)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No headers configured</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Delete Modal */}
        {showDeleteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={handleDeleteCancel}></div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Delete API</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                This action cannot be undone. This will permanently delete the API "{api?.api_name}".
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Please type <strong>{api?.api_name}</strong> to confirm.
              </p>
              <input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                className="input w-full mb-4"
                placeholder="Enter API name to confirm"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleDeleteConfirm}
                  disabled={deleteConfirmation !== api?.api_name || deleting}
                  className="btn btn-error flex-1"
                >
                  {deleting ? (
                    <div className="flex items-center justify-center">
                      <div className="spinner mr-2"></div>
                      Deleting...
                    </div>
                  ) : (
                    'Delete API'
                  )}
                </button>
                <button onClick={handleDeleteCancel} className="btn btn-secondary flex-1">
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

export default ApiDetailPage 