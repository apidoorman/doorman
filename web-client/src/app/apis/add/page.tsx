'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'

const AddApiPage = () => {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    api_name: '',
    api_version: '',
    api_type: 'REST',
    api_description: '',
    api_allowed_retry_count: 0,
    api_servers: [] as string[],
    api_allowed_roles: [] as string[],
    api_allowed_groups: [] as string[],
    api_allowed_headers: [] as string[],
    api_authorization_field_swap: '',
    api_credits_enabled: false,
    api_credit_group: '',
    // Frontend-only preference; stored in localStorage per API
    use_protobuf: false,
    // kept for future use; backend ignores unknown fields
    validation_enabled: false
  })
  const [newServer, setNewServer] = useState('')
  const [newRole, setNewRole] = useState('')
  const [newGroup, setNewGroup] = useState('')
  const [newHeader, setNewHeader] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      // Trim empty optional fields to keep payload clean
      const payload: any = { ...formData }
      if (!payload.api_authorization_field_swap) delete payload.api_authorization_field_swap
      if (!payload.api_credit_group) delete payload.api_credit_group
      if (!Array.isArray(payload.api_allowed_headers) || payload.api_allowed_headers.length === 0) delete payload.api_allowed_headers
      if (!Array.isArray(payload.api_allowed_roles) || payload.api_allowed_roles.length === 0) delete payload.api_allowed_roles
      if (!Array.isArray(payload.api_allowed_groups) || payload.api_allowed_groups.length === 0) delete payload.api_allowed_groups
      await postJson(`${SERVER_URL}/platform/api`, payload)
      // Persist frontend-only preference for this API
      try {
        const { setUseProtobuf } = await import('@/utils/proto')
        setUseProtobuf(formData.api_name, formData.api_version, !!formData.use_protobuf)
      } catch {}
      router.push('/apis')
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : (name === 'api_allowed_retry_count' ? Number(value || 0) : value)
    }))
  }

  const addServer = () => {
    const value = newServer.trim()
    if (!value) return
    if (formData.api_servers.includes(value)) return
    setFormData(prev => ({ ...prev, api_servers: [...prev.api_servers, value] }))
    setNewServer('')
  }

  const removeServer = (index: number) => {
    setFormData(prev => ({ ...prev, api_servers: prev.api_servers.filter((_, i) => i !== index) }))
  }

  const addRole = () => {
    const v = newRole.trim()
    if (!v) return
    if (formData.api_allowed_roles.includes(v)) return
    setFormData(prev => ({ ...prev, api_allowed_roles: [...prev.api_allowed_roles, v] }))
    setNewRole('')
  }

  const removeRole = (index: number) => {
    setFormData(prev => ({ ...prev, api_allowed_roles: prev.api_allowed_roles.filter((_, i) => i !== index) }))
  }

  const addGroup = () => {
    const v = newGroup.trim()
    if (!v) return
    if (formData.api_allowed_groups.includes(v)) return
    setFormData(prev => ({ ...prev, api_allowed_groups: [...prev.api_allowed_groups, v] }))
    setNewGroup('')
  }

  const removeGroup = (index: number) => {
    setFormData(prev => ({ ...prev, api_allowed_groups: prev.api_allowed_groups.filter((_, i) => i !== index) }))
  }

  const addHeader = () => {
    const v = newHeader.trim()
    if (!v) return
    if (formData.api_allowed_headers.includes(v)) return
    setFormData(prev => ({ ...prev, api_allowed_headers: [...prev.api_allowed_headers, v] }))
    setNewHeader('')
  }

  const removeHeader = (index: number) => {
    setFormData(prev => ({ ...prev, api_allowed_headers: prev.api_allowed_headers.filter((_, i) => i !== index) }))
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Add API</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Define a new API and its default upstream servers
            </p>
          </div>
          <Link href="/apis" className="btn btn-secondary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to APIs
          </Link>
        </div>

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

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Basic Information</h3>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                <label htmlFor="api_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API Name *
                </label>
                <input
                  id="api_name"
                  name="api_name"
                  type="text"
                  required
                  className="input"
                  placeholder="e.g., user-service"
                  value={formData.api_name}
                  onChange={handleChange}
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  A unique identifier for your API
                </p>
              </div>

              <div>
                <label htmlFor="api_version" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Version *
                </label>
                <input
                  id="api_version"
                  name="api_version"
                  type="text"
                  required
                  className="input"
                  placeholder="e.g., v1"
                  value={formData.api_version}
                  onChange={handleChange}
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  API version (e.g., v1, v2, beta)
                </p>
              </div>
              </div>
              <div>
                <label htmlFor="api_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API Type*
                </label>
                <select
                  id="api_type"
                  name="api_type"
                  required
                  className="input"
                  value={formData.api_type}
                  onChange={handleChange}
                  disabled={loading}
                >
                  <option value="REST">REST</option>
                  <option value="GraphQL">GraphQL</option>
                  <option value="gRPC">gRPC</option>
                  <option value="SOAP">SOAP</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">The protocol type for this API</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Retry Count
                </label>
                <input
                  type="number"
                  name="api_allowed_retry_count"
                  className="input"
                  min={0}
                  value={formData.api_allowed_retry_count}
                  onChange={handleChange}
                  disabled={loading}
                />
              </div>
              <div>
                <label htmlFor="api_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</label>
                <textarea id="api_description" name="api_description" rows={4} className="input resize-none" placeholder="Describe what this API does..." value={formData.api_description} onChange={handleChange} disabled={loading} />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Optional description of the API's purpose</p>
              </div>
            </div>
          </div>
          </div>

          <div className="card">
            <div className="card-header"><h3 className="card-title">Configuration</h3></div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Credits Enabled
                </label>
                <div className="flex items-center">
                  <input
                    id="api_credits_enabled"
                    name="api_credits_enabled"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={formData.api_credits_enabled}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <label htmlFor="api_credits_enabled" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                    Enable API credits
                  </label>
                </div>
              </div>
              {formData.api_credits_enabled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Credit Group
                  </label>
                  <input
                    type="text"
                    name="api_credit_group"
                    className="input"
                    placeholder="ai-group-1"
                    value={formData.api_credit_group}
                    onChange={handleChange}
                    disabled={loading}
                  />
                </div>
              )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Authorization Field Swap</label>
                <input type="text" name="api_authorization_field_swap" className="input" placeholder="backend-auth-header" value={formData.api_authorization_field_swap} onChange={handleChange} disabled={loading} />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3 className="card-title">Servers</h3></div>
            <div className="p-6 space-y-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">API Servers</label>
              <div className="flex gap-2">
                <input type="text" className="input flex-1" placeholder="e.g., http://localhost:8080" value={newServer} onChange={(e) => setNewServer(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && addServer()} disabled={loading} />
                <button type="button" onClick={addServer} className="btn btn-secondary" disabled={loading}>Add</button>
              </div>
              <div className="mt-2 space-y-2">
                {formData.api_servers.map((srv, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded">
                    <span className="text-sm font-mono text-gray-800 dark:text-gray-200">{srv}</span>
                    <button type="button" onClick={() => removeServer(idx)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
                {formData.api_servers.length === 0 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">No servers added yet</p>
                )}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">These are the default upstreams for this API. You can override per-endpoint later.</p>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3 className="card-title">Allowed Roles</h3></div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Allowed Roles
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="admin"
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addRole()}
                    disabled={loading}
                  />
                  <button type="button" onClick={addRole} className="btn btn-secondary" disabled={loading}>Add</button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {formData.api_allowed_roles.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{r}</span>
                      <button type="button" onClick={() => removeRole(i)} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="1 1 22 22">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Use Protobuf
                </label>
                <div className="flex items-center">
                  <input
                    id="use_protobuf"
                    name="use_protobuf"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={formData.use_protobuf}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <label htmlFor="use_protobuf" className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                    Enable proto-based features for this API
                  </label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Frontend setting; controls proto UI and client behavior.</p>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3 className="card-title">Allowed Groups</h3></div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Allowed Groups
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="ALL"
                    value={newGroup}
                    onChange={(e) => setNewGroup(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addGroup()}
                    disabled={loading}
                  />
                  <button type="button" onClick={addGroup} className="btn btn-secondary" disabled={loading}>Add</button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {formData.api_allowed_groups.map((g, i) => (
                    <div key={i} className="flex items-center gap-2 bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{g}</span>
                      <button type="button" onClick={() => removeGroup(i)} className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-200">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="1 1 22 22">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3 className="card-title">Allowed Headers</h3></div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Allowed Headers</label>
                <div className="flex gap-2">
                  <input type="text" className="input flex-1" placeholder="e.g., Authorization" value={newHeader} onChange={(e) => setNewHeader(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && addHeader()} disabled={loading} />
                  <button type="button" onClick={addHeader} className="btn btn-secondary" disabled={loading}>Add</button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {formData.api_allowed_headers.map((h, i) => (
                    <div key={i} className="flex items-center gap-2 bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{h}</span>
                      <button type="button" onClick={() => removeHeader(i)} className="text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-200">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="1 1 22 22">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-4">
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary flex-1"
              >
                {loading ? (
                  <div className="flex items-center justify-center">
                    <div className="spinner mr-2"></div>
                    Creating API...
                  </div>
                ) : (
                  'Create API'
                )}
              </button>
              <Link href="/apis" className="btn btn-secondary flex-1">
                Cancel
              </Link>
          </div>
        </form>
      </div>
    </Layout>
  )
}

export default AddApiPage 
