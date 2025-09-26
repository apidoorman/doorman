'use client'

import React, { useState, useEffect } from 'react'
import ConfirmModal from '@/components/ConfirmModal'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'
import { fetchJson, getCookie } from '@/utils/http'
import { useToast } from '@/contexts/ToastContext'
import { SERVER_URL } from '@/utils/config'

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
  api_credits_enabled: boolean
  api_credit_group?: string
  api_path?: string
}

interface EndpointItem {
  api_name: string
  api_version: string
  endpoint_method: string
  endpoint_uri: string
  endpoint_description?: string
  endpoint_id?: string
  endpoint_servers?: string[]
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
  api_credits_enabled?: boolean
  api_credit_group?: string
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
  const [endpoints, setEndpoints] = useState<EndpointItem[]>([])
  const [epNewServer, setEpNewServer] = useState<Record<string, string>>({})
  const [epSaving, setEpSaving] = useState<Record<string, boolean>>({})
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleting, setDeleting] = useState(false)
  const toast = useToast()
  const [useProtobuf, setUseProtobufState] = useState<boolean>(false)

  // Proto management state and helpers
  type ProtoState = { loading: boolean; exists: boolean | null; content?: string; error?: string | null; working?: boolean; show?: boolean }
  const [proto, setProto] = useState<ProtoState>({ loading: false, exists: null, content: undefined, error: null, working: false, show: false })

  const fetchWithCsrf = async (input: RequestInfo, init: RequestInit = {}) => {
    const csrf = getCookie('csrf_token')
    const headers: any = { ...(init.headers || {}), Accept: 'application/json' }
    if (csrf) headers['X-CSRF-Token'] = csrf
    const resp = await fetch(input, { credentials: 'include', ...init, headers })
    const data = await resp.json().catch(() => ({} as any))
    const payload = data && typeof data === 'object' && 'response' in data ? data.response : data
    if (!resp.ok) {
      const msg = (payload && (payload.error_message || payload.message)) || resp.statusText
      throw new Error(msg)
    }
    return payload
  }

  const checkProto = async () => {
    if (!api) return
    setProto(prev => ({ ...prev, loading: true, error: null }))
    try {
      const payload = await fetchWithCsrf(`${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`)
      setProto({ loading: false, exists: true, content: payload?.content || '', error: null, working: false, show: false })
    } catch (e: any) {
      const msg = String(e?.message || '')
      if (msg.toLowerCase().includes('not found')) setProto({ loading: false, exists: false, content: undefined, error: null, working: false, show: false })
      else setProto({ loading: false, exists: null, content: undefined, error: msg || 'Failed to check proto', working: false, show: false })
    }
  }

  const uploadOrUpdateProto = async (file: File, mode: 'create' | 'update') => {
    if (!api) return
    setProto(prev => ({ ...prev, working: true, error: null }))
    try {
      const form = new FormData()
      if (mode === 'create') form.append('file', file)
      else form.append('proto_file', file)
      const method = mode === 'create' ? 'POST' : 'PUT'
      await fetchWithCsrf(`${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`, { method, body: form })
      await checkProto()
      setSuccess(mode === 'create' ? 'Proto uploaded' : 'Proto updated')
      toast.success(mode === 'create' ? 'Proto uploaded' : 'Proto updated')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e: any) {
      setProto(prev => ({ ...prev, error: e?.message || 'Operation failed' }))
    } finally {
      setProto(prev => ({ ...prev, working: false }))
    }
  }

  const deleteProto = async () => {
    if (!api) return
    setProto(prev => ({ ...prev, working: true, error: null }))
    try {
      await fetchWithCsrf(`${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`, { method: 'DELETE' })
      setProto({ loading: false, exists: false, content: undefined, error: null, working: false, show: false })
      setSuccess('Proto deleted')
      toast.success('Proto deleted')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e: any) {
      setProto(prev => ({ ...prev, error: e?.message || 'Delete failed' }))
    } finally {
      setProto(prev => ({ ...prev, working: false }))
    }
  }

  useEffect(() => {
    const apiData = sessionStorage.getItem('selectedApi')
    if (apiData) {
      try {
        const parsedApi = JSON.parse(apiData)
        setApi(parsedApi)
        try {
          const { getUseProtobuf } = require('@/utils/proto')
          setUseProtobufState(getUseProtobuf(parsedApi.api_name, parsedApi.api_version))
        } catch {}
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
          api_credits_enabled: parsedApi.api_credits_enabled,
          api_credit_group: parsedApi.api_credit_group
        })
        setLoading(false)
      } catch (err) {
        setError('Failed to load API data')
        setLoading(false)
      }
    } else {
      // Fallback: resolve API by id from server list
      (async () => {
        try {
          const data = await fetchJson(`${SERVER_URL}/platform/api/all?page=1&page_size=1000`)
          const list = Array.isArray(data) ? data : (data as any).apis || (data as any).response?.apis || []
          const found = (list as any[]).find((a: any) => String(a.api_id) === String(apiId))
          if (found) {
            setApi(found)
            try {
              const { getUseProtobuf } = require('@/utils/proto')
              setUseProtobufState(getUseProtobuf(found.api_name, found.api_version))
            } catch {}
            setEditData({
              api_name: found.api_name,
              api_version: found.api_version,
              api_description: found.api_description,
              api_allowed_roles: [...(found.api_allowed_roles || [])],
              api_allowed_groups: [...(found.api_allowed_groups || [])],
              api_servers: [...(found.api_servers || [])],
              api_type: found.api_type,
              api_allowed_retry_count: found.api_allowed_retry_count,
              api_authorization_field_swap: found.api_authorization_field_swap,
              api_allowed_headers: [...(found.api_allowed_headers || [])],
              api_credits_enabled: found.api_credits_enabled,
              api_credit_group: found.api_credit_group
            })
            setError(null)
          } else {
            setError('No API data found')
          }
        } catch (e) {
          setError('Failed to load API data')
        } finally {
          setLoading(false)
        }
      })()
    }
  }, [apiId])

  useEffect(() => {
    const loadEndpoints = async () => {
      if (!api) return
      try {
        const response = await fetch(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}` ,{
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.error_message || 'Failed to load endpoints')
        setEndpoints(data.endpoints || [])
      } catch (e) {
        // endpoints optional; do not hard fail page
        console.warn('Failed to load endpoints for API', e)
      }
    }
    loadEndpoints()
  }, [api])

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
        api_credits_enabled: api.api_credits_enabled,
        api_credit_group: api.api_credit_group
      })
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const targetName = (api?.['api_name'] as string) || ''
      const targetVersion = (api?.['api_version'] as string) || ''
      const response = await fetch(`${SERVER_URL}/platform/api/${encodeURIComponent(targetName)}/${encodeURIComponent(targetVersion)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editData)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update API')
      }

      // Refresh from server to get the latest canonical data
      if (!api) throw new Error('API context missing for refresh')
      const name = (api as any).api_name as string
      const version = (api as any).api_version as string
      const refreshedApi = await fetchJson(`${SERVER_URL}/platform/api/${encodeURIComponent(name)}/${encodeURIComponent(version)}`)
      setApi(refreshedApi)
      sessionStorage.setItem('selectedApi', JSON.stringify(refreshedApi))
      // Persist current protobuf preference
      try {
        const { setUseProtobuf } = await import('@/utils/proto')
        setUseProtobuf(refreshedApi.api_name, refreshedApi.api_version, useProtobuf)
      } catch {}
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

  const addEndpointServer = async (ep: EndpointItem) => {
    const key = `${ep.endpoint_method}:${ep.endpoint_uri}`
    const value = (epNewServer[key] || '').trim()
    if (!value) return
    const next = [...(ep.endpoint_servers || [])]
    if (next.includes(value)) return
    next.push(value)
    await saveEndpointServers(ep, next)
    setEpNewServer(prev => ({ ...prev, [key]: '' }))
  }

  const removeEndpointServer = async (ep: EndpointItem, index: number) => {
    const next = (ep.endpoint_servers || []).filter((_, i) => i !== index)
    await saveEndpointServers(ep, next)
  }

  const saveEndpointServers = async (ep: EndpointItem, servers: string[]) => {
    if (!api) return
    const key = `${ep.endpoint_method}:${ep.endpoint_uri}`
    setEpSaving(prev => ({ ...prev, [key]: true }))
    try {
      const response = await fetch(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(ep.endpoint_method)}/${encodeURIComponent(ep.api_name)}/${encodeURIComponent(ep.api_version)}/${encodeURIComponent(ep.endpoint_uri.replace(/^\//, ''))}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ endpoint_servers: servers })
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error_message || 'Failed to save endpoint servers')
      // refresh endpoints
      const refreshed = await fetch(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}` ,{
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      })
      const refreshedData = await refreshed.json()
      setEndpoints(refreshedData.endpoints || [])
      setSuccess('Endpoint servers updated')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setError(e?.message || 'Failed to update endpoint')
      setTimeout(() => setError(null), 3000)
    } finally {
      setEpSaving(prev => ({ ...prev, [key]: false }))
    }
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
    try {
      setDeleting(true)
      setError(null)
      const { delJson } = await import('@/utils/api')
      let name = (api as any)?.api_name as string | undefined
      let version = (api as any)?.api_version as string | undefined
      if (!name || !version) {
        // Fallback: resolve by id
        try {
          const data = await fetchJson(`${SERVER_URL}/platform/api/all?page=1&page_size=1000`)
          const list = Array.isArray(data) ? data : (data as any).apis || (data as any).response?.apis || []
          const found = (list as any[]).find((a: any) => String(a.api_id) === String(apiId))
          if (found) {
            name = found.api_name
            version = found.api_version
          }
        } catch {}
      }
      if (!name || !version) throw new Error('API context missing for delete')
      await delJson(`${SERVER_URL}/platform/api/${encodeURIComponent(name)}/${encodeURIComponent(version)}`)

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
                <Link href={`/apis/${encodeURIComponent(apiId)}/endpoints`} className="btn btn-secondary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  Manage Endpoints
                </Link>
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
                    Credits Enabled
                  </label>
                  {isEditing ? (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={editData.api_credits_enabled || false}
                        onChange={(e) => handleInputChange('api_credits_enabled', e.target.checked)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Enable API credits
                      </label>
                    </div>
                  ) : (
                    <span className={`badge ${api.api_credits_enabled ? 'badge-success' : 'badge-gray'}`}>
                      {api.api_credits_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  )}
                </div>

                {api.api_credits_enabled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Credit Group
                    <InfoTooltip text="Configured credit group name used to deduct and inject keys." />
                  </label>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editData.api_credit_group || ''}
                        onChange={(e) => handleInputChange('api_credit_group', e.target.value)}
                        className="input"
                        placeholder="Enter credit group"
                      />
                    ) : (
                      <p className="text-gray-900 dark:text-white">{api.api_credit_group || 'Default'}</p>
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Authorization Field Swap
                    <InfoTooltip text="Map Authorization to a different header (e.g., X-Api-Key)." />
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Use Protobuf
                    <InfoTooltip text="Frontend preference; enables proto-aware UI only." />
                  </label>
                  {isEditing ? (
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={useProtobuf}
                        onChange={async (e) => {
                          const next = e.target.checked
                          setUseProtobufState(next)
                          try {
                            const { setUseProtobuf } = await import('@/utils/proto')
                            setUseProtobuf(api?.api_name, api?.api_version, next)
                          } catch {}
                        }}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                        Enable proto-based features for this API
                      </label>
                    </div>
                  ) : (
                    <span className={`badge ${useProtobuf ? 'badge-success' : 'badge-gray'}`}>
                      {useProtobuf ? 'Enabled' : 'Disabled'}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Proto Management */}
            {useProtobuf ? (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Proto</h3>
                </div>
                <div className="p-6 space-y-4">
                  {proto.error && (
                    <div className="rounded bg-error-50 border border-error-200 p-2 text-error-700 text-sm">{proto.error}</div>
                  )}
                  <div className="flex items-center gap-3">
                    <button className="btn btn-secondary" onClick={checkProto} disabled={proto.loading}> {proto.loading ? 'Checking...' : 'Check Status'} </button>
                    {proto.exists === true && <span className="text-success-700 dark:text-success-400">Present</span>}
                    {proto.exists === false && <span className="text-error-700 dark:text-error-400">Missing</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="btn btn-secondary">
                      Upload
                      <input type="file" accept=".proto,text/plain" style={{ display: 'none' }} disabled={proto.working}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await uploadOrUpdateProto(f, 'create'); e.currentTarget.value = '' } }} />
                    </label>
                    <label className="btn btn-secondary">
                      Replace
                      <input type="file" accept=".proto,text/plain" style={{ display: 'none' }} disabled={proto.working}
                        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await uploadOrUpdateProto(f, 'update'); e.currentTarget.value = '' } }} />
                    </label>
                    <button className="btn btn-error" onClick={deleteProto} disabled={proto.working || proto.exists !== true}>Delete</button>
                    <button className="btn btn-ghost" onClick={() => setProto(prev => ({ ...prev, show: !prev.show }))} disabled={!proto.content}>{proto.show ? 'Hide' : 'View'}</button>
                  </div>
                  {proto.show && proto.content && (
                    <pre className="text-xs whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded max-h-64 overflow-auto">{proto.content}</pre>
                  )}
                </div>
              </div>
            ) : (
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">Proto</h3>
                </div>
                <div className="p-6 space-y-4">
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Protobuf features are disabled for this API. Enable "Use Protobuf" in the Configuration section to upload or manage proto files.
                  </div>
                </div>
              </div>
            )}

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
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Allowed Groups</h3>
                <FormHelp docHref="/docs/using-fields.html#access-control">User must belong to any listed group.</FormHelp>
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
                <p className="text-xs text-gray-500 dark:text-gray-400">Used when no client routing or endpoint override is configured</p>
                <FormHelp docHref="/docs/using-fields.html#servers">Add base upstreams; include scheme and port.</FormHelp>
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

            {/* Endpoint Overrides */}
            <div className="card lg:col-span-2">
              <div className="card-header">
                <h3 className="card-title">Endpoint Overrides</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Precedence: Routing (client-key) → Endpoint servers → API servers</p>
              </div>
              <div className="p-6 space-y-4">
                {endpoints.length === 0 ? (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No endpoints found for this API.</p>
                ) : (
                  endpoints.map((ep) => {
                    const key = `${ep.endpoint_method}:${ep.endpoint_uri}`
                    const saving = !!epSaving[key]
                    const enabled = (ep.endpoint_servers || []).length > 0
                    return (
                      <div key={key} className="border rounded-lg p-4 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">{ep.endpoint_method}</div>
                            <div className="font-mono text-gray-900 dark:text-gray-100">{ep.endpoint_uri}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={enabled}
                              onChange={async (e) => {
                                const on = e.target.checked
                                if (!on) {
                                  await removeEndpointServer(ep, -1) // noop fallback
                                  await saveEndpointServers(ep, [])
                                }
                              }}
                            />
                            <span className="text-sm text-gray-600 dark:text-gray-300">Use endpoint servers</span>
                          </div>
                        </div>
                        <div className={`mt-3 space-y-2 ${enabled ? '' : 'opacity-60'}`}>
                          {(ep.endpoint_servers || []).map((srv, idx) => (
                            <div key={idx} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded">
                              <span className="text-sm font-mono">{srv}</span>
                              <button disabled={saving || !enabled} onClick={() => removeEndpointServer(ep, idx)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          ))}
                          {(ep.endpoint_servers || []).length === 0 && (
                            <p className="text-gray-500 dark:text-gray-400 text-sm">No endpoint-specific servers. Using API servers.</p>
                          )}
                        </div>
                        <div className="mt-3 flex gap-2">
                          <input
                            type="text"
                            value={epNewServer[key] || ''}
                            onChange={(e) => setEpNewServer(prev => ({ ...prev, [key]: e.target.value }))}
                            className={`input flex-1 ${enabled ? '' : 'opacity-60'}`}
                            placeholder="Add endpoint server URL"
                            onKeyPress={(e) => e.key === 'Enter' && enabled && addEndpointServer(ep)}
                            disabled={!enabled}
                          />
                          <button disabled={saving || !enabled} onClick={() => addEndpointServer(ep)} className="btn btn-primary">
                            {saving ? <div className="flex items-center"><div className="spinner mr-2"></div>Saving...</div> : 'Add'}
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>

            {/* Allowed Headers */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Allowed Headers</h3>
                <FormHelp docHref="/docs/using-fields.html#header-forwarding">Forward only selected upstream response headers.</FormHelp>
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

        <ConfirmModal
          open={showDeleteModal}
          title="Delete API"
          message={<>
            This action cannot be undone. This will permanently delete the API "{api?.api_name}".
          </>}
          confirmLabel={deleting ? 'Deleting...' : 'Delete API'}
          cancelLabel="Cancel"
          onCancel={handleDeleteCancel}
          onConfirm={handleDeleteConfirm}
          requireTextMatch={api?.api_name || ''}
          inputPlaceholder="Enter API name to confirm"
        />
      </div>
    </Layout>
  )
}

export default ApiDetailPage 
