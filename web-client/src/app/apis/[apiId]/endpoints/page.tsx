'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import ConfirmModal from '@/components/ConfirmModal'

interface EndpointItem {
  api_name: string
  api_version: string
  endpoint_method: string
  endpoint_uri: string
  endpoint_description?: string
  endpoint_id?: string
  endpoint_servers?: string[]
}

export default function ApiEndpointsPage() {
  const params = useParams()
  const router = useRouter()
  const apiId = params.apiId as string
  const [apiName, setApiName] = useState('')
  const [apiVersion, setApiVersion] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [endpoints, setEndpoints] = useState<EndpointItem[]>([])
  const [allEndpoints, setAllEndpoints] = useState<EndpointItem[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<'method' | 'uri' | 'servers'>('method')
  const [working, setWorking] = useState<Record<string, boolean>>({})
  const [epNewServer, setEpNewServer] = useState<Record<string, string>>({})

  type EpValidation = {
    loading: boolean
    exists: boolean
    enabled: boolean
    schemaText: string
    saving: boolean
    error: string | null
  }
  const [validationByEndpoint, setValidationByEndpoint] = useState<Record<string, EpValidation>>({})

  const ensureValidationLoaded = async (ep: EndpointItem) => {
    const eid = ep.endpoint_id
    if (!eid) return
    if (validationByEndpoint[eid]?.loading === false && validationByEndpoint[eid] !== undefined) return
    setValidationByEndpoint(prev => ({
      ...prev,
      [eid]: { loading: true, exists: false, enabled: false, schemaText: '{\n}\n', saving: false, error: null }
    }))
    try {
      const { fetchWithCsrf } = await import('@/utils/http')
      const resp = await fetchWithCsrf(`${SERVER_URL}/platform/endpoint/validation/${encodeURIComponent(eid)}`, {
        headers: { 'Accept': 'application/json' }
      })
      if (resp.ok) {
        const data = await resp.json().catch(() => ({}))
        const payload = data.response || data
        const enabled = !!payload.validation_enabled
        const schema = payload.validation_schema || {}
        setValidationByEndpoint(prev => ({
          ...prev,
          [eid]: {
            loading: false,
            exists: true,
            enabled,
            schemaText: JSON.stringify(schema, null, 2),
            saving: false,
            error: null
          }
        }))
      } else if (resp.status === 404) {
        setValidationByEndpoint(prev => ({
          ...prev,
          [eid]: { loading: false, exists: false, enabled: false, schemaText: '{\n}\n', saving: false, error: null }
        }))
      } else {
        setValidationByEndpoint(prev => ({
          ...prev,
          [eid]: { loading: false, exists: false, enabled: false, schemaText: '{\n}\n', saving: false, error: 'Failed to load validation' }
        }))
      }
    } catch (e) {
      setValidationByEndpoint(prev => ({
        ...prev,
        [eid]: { loading: false, exists: false, enabled: false, schemaText: '{\n}\n', saving: false, error: 'Failed to load validation' }
      }))
    }
  }

  const saveValidation = async (ep: EndpointItem) => {
    const eid = ep.endpoint_id
    if (!eid) return
    const cur = validationByEndpoint[eid]
    if (!cur) return
    setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...cur, saving: true, error: null } }))
    try {
      let schema: any = {}
      try { schema = JSON.parse(cur.schemaText || '{}') } catch { throw new Error('Schema must be valid JSON') }
      const body = JSON.stringify({ validation_enabled: !!cur.enabled, validation_schema: schema })
      const url = `${SERVER_URL}/platform/endpoint/validation/${encodeURIComponent(eid)}`
      const resp = await fetch(url, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.error_message || 'Failed to save validation')
      }
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...prev[eid], saving: false, exists: true } }))
      setSuccess('Validation saved')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...prev[eid], saving: false, error: e?.message || 'Failed to save validation' } }))
    }
  }

  const createValidation = async (ep: EndpointItem) => {
    const eid = ep.endpoint_id
    if (!eid) return
    const cur = validationByEndpoint[eid]
    if (!cur) return
    setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...cur, saving: true, error: null } }))
    try {
      let schema: any = {}
      try { schema = JSON.parse(cur.schemaText || '{}') } catch { throw new Error('Schema must be valid JSON') }
      const body = JSON.stringify({ endpoint_id: eid, validation_enabled: !!cur.enabled, validation_schema: schema })
      const { fetchWithCsrf } = await import('@/utils/http')
      const resp = await fetchWithCsrf(`${SERVER_URL}/platform/endpoint/validation`, {
        method: 'POST',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.error_message || 'Failed to create validation')
      }
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...prev[eid], saving: false, exists: true } }))
      setSuccess('Validation created')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...prev[eid], saving: false, error: e?.message || 'Failed to create validation' } }))
    }
  }

  const deleteValidation = async (ep: EndpointItem) => {
    const eid = ep.endpoint_id
    if (!eid) return
    const cur = validationByEndpoint[eid]
    if (!cur) return
    setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...cur, saving: true, error: null } }))
    try {
      const { fetchWithCsrf } = await import('@/utils/http')
      const resp = await fetchWithCsrf(`${SERVER_URL}/platform/endpoint/validation/${encodeURIComponent(eid)}`, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' }
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.error_message || 'Failed to delete validation')
      }
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { loading: false, exists: false, enabled: false, schemaText: '{\n}\n', saving: false, error: null } }))
      setSuccess('Validation deleted')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setValidationByEndpoint(prev => ({ ...prev, [eid]: { ...prev[eid], saving: false, error: e?.message || 'Failed to delete validation' } }))
    }
  }

  useEffect(() => {
    try {
      const apiData = sessionStorage.getItem('selectedApi')
      if (apiData) {
        const parsed = JSON.parse(apiData)
        setApiName(parsed.api_name || '')
        setApiVersion(parsed.api_version || '')
      }
    } catch {}
  }, [])

  const loadEndpoints = async () => {
    setLoading(true)
    setError(null)
    const attempt = async () => {
      if (!apiName || !apiVersion) {
        const data = await getJson<any>(`${SERVER_URL}/platform/api/all`)
        const list = Array.isArray(data) ? data : (data.apis || data.response?.apis || [])
        const found = (list || []).find((a:any) => String(a.api_id) === String(apiId))
        if (found) {
          setApiName(found.api_name || '')
          setApiVersion(found.api_version || '')
        }
      }
      const { fetchJson } = await import('@/utils/http')
      const data = await fetchJson(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(apiName)}/${encodeURIComponent(apiVersion)}`)
      let list: any[] = []
      if (data) {
        list = data.endpoints || data.response?.endpoints || []
      }
      setEndpoints(list)
      setAllEndpoints(list)
    }
    try {
      await attempt()
    } catch (e:any) {
      try {
        await new Promise(r => setTimeout(r, 200))
        await attempt()
      } catch (err:any) {
        setError(err?.message || 'Failed to load endpoints')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (apiName && apiVersion) {
      loadEndpoints()
    } else {
      setLoading(false)
    }
  }, [apiName, apiVersion])

  const keyFor = (ep: EndpointItem) => `${ep.endpoint_method}:${ep.endpoint_uri}`
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [endpointToDelete, setEndpointToDelete] = useState<EndpointItem | null>(null)

  const filtered = useMemo(() => {
    const t = searchTerm.trim().toLowerCase()
    let list = allEndpoints
    if (t) {
      list = list.filter(ep =>
        ep.endpoint_method.toLowerCase().includes(t) ||
        ep.endpoint_uri.toLowerCase().includes(t) ||
        (ep.endpoint_description || '').toLowerCase().includes(t)
      )
    }
    const sorted = [...list].sort((a, b) => {
      if (sortBy === 'method') return a.endpoint_method.localeCompare(b.endpoint_method)
      if (sortBy === 'uri') return a.endpoint_uri.localeCompare(b.endpoint_uri)
      const ac = (a.endpoint_servers || []).length
      const bc = (b.endpoint_servers || []).length
      return ac - bc
    })
    return sorted
  }, [allEndpoints, searchTerm, sortBy])

  const deleteEndpoint = async (ep: EndpointItem) => {
    const k = keyFor(ep)
    setWorking(prev => ({ ...prev, [k]: true }))
    setError(null)
    try {
      const { delJson } = await import('@/utils/api')
      await delJson(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(ep.endpoint_method)}/${encodeURIComponent(ep.api_name)}/${encodeURIComponent(ep.api_version)}/${encodeURIComponent(ep.endpoint_uri.replace(/^\//, ''))}`)
      await loadEndpoints()
      setSuccess('Endpoint deleted')
      setTimeout(() => setSuccess(null), 2000)
      setShowDeleteModal(false)
      setDeleteConfirmation('')
      setEndpointToDelete(null)
    } catch (e:any) {
      setError(e?.message || 'Failed to delete endpoint')
    } finally {
      setWorking(prev => ({ ...prev, [k]: false }))
    }
  }

  const handleDeleteClick = (ep: EndpointItem, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    setEndpointToDelete(ep)
    setDeleteConfirmation('')
    setShowDeleteModal(true)
  }

  const saveEndpointServers = async (ep: EndpointItem, servers: string[]) => {
    const k = keyFor(ep)
    setWorking(prev => ({ ...prev, [k]: true }))
    setError(null)
    try {
      const { putJson } = await import('@/utils/api')
      await putJson(`${SERVER_URL}/platform/endpoint/${encodeURIComponent(ep.endpoint_method)}/${encodeURIComponent(ep.api_name)}/${encodeURIComponent(ep.api_version)}/${encodeURIComponent(ep.endpoint_uri.replace(/^\//, ''))}`, { endpoint_servers: servers })
      await loadEndpoints()
      setSuccess('Endpoint servers updated')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setError(e?.message || 'Failed to update endpoint')
    } finally {
      setWorking(prev => ({ ...prev, [k]: false }))
    }
  }

  const addEndpointServer = async (ep: EndpointItem) => {
    const k = keyFor(ep)
    const value = (epNewServer[k] || '').trim()
    if (!value) return
    const next = [...(ep.endpoint_servers || [])]
    if (!next.includes(value)) next.push(value)
    await saveEndpointServers(ep, next)
    setEpNewServer(prev => ({ ...prev, [k]: '' }))
  }

  const removeEndpointServer = async (ep: EndpointItem, index: number) => {
    const next = (ep.endpoint_servers || []).filter((_, i) => i !== index)
    await saveEndpointServers(ep, next)
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Endpoints for {apiName}/{apiVersion}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">Create, edit, and delete endpoints. Precedence: Routing (client-key) → Endpoint servers → API servers.</p>
          </div>
          <div className="flex gap-2">
            <Link href={`/apis/${encodeURIComponent(apiId)}/endpoints/add`} className="btn btn-primary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Endpoint
            </Link>
            <Link href={`/apis/${encodeURIComponent(apiId)}`} className="btn btn-ghost">Back</Link>
          </div>
        </div>

        {success && (
          <div className="rounded-lg bg-success-50 border border-success-200 p-4 dark:bg-success-900/20 dark:border-success-800">
            <div className="flex"><p className="text-sm text-success-700 dark:text-success-300">{success}</p></div>
          </div>
        )}
        {error && (
          <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
            <div className="flex"><p className="text-sm text-error-700 dark:text-error-300">{error}</p></div>
          </div>
        )}

        <div className="card">
          <div className="flex flex-col sm:flex-row gap-4">
            <form onSubmit={(e) => { e.preventDefault(); }} className="flex-1">
              <div className="relative">
                <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search endpoints by method, URI, or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>

            <div className="flex gap-2">
              <button onClick={() => setSortBy('method')} className={`btn ${sortBy === 'method' ? 'btn-primary' : 'btn-secondary'}`}>Method</button>
              <button onClick={() => setSortBy('uri')} className={`btn ${sortBy === 'uri' ? 'btn-primary' : 'btn-secondary'}`}>URI</button>
              <button onClick={() => setSortBy('servers')} className={`btn ${sortBy === 'servers' ? 'btn-primary' : 'btn-secondary'}`}>Servers</button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th></th>
                  <th>Method</th>
                  <th>URI</th>
                  <th>Description</th>
                  <th>Routing</th>
                  <th>Servers</th>

                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} className="text-center py-8 text-gray-500">Loading endpoints...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-8 text-gray-500">No endpoints found.</td></tr>
                ) : (
                  filtered.map((ep) => {
                    const k = keyFor(ep)
                    const saving = !!working[k]
                    const hasOverride = (ep.endpoint_servers || []).length > 0
                    const [expanded, setExpanded] = [undefined as any, undefined as any]
                    return (
                      <React.Fragment key={k}>
                        <tr className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover" onClick={() => setExpandedKeys(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n })}>
                          <td>
                            <button className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" onClick={(e) => { e.stopPropagation(); setExpandedKeys(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n }) }}>
                              <svg className={`h-4 w-4 transform transition-transform ${expandedKeys.has(k) ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                            </button>
                          </td>
                          <td>
                            <span className={`badge ${ep.endpoint_method === 'GET' ? 'badge-success' : ep.endpoint_method === 'POST' ? 'badge-primary' : 'badge-warning'}`}>{ep.endpoint_method}</span>
                          </td>
                          <td className="font-mono text-sm">{ep.endpoint_uri}</td>
                          <td className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">{ep.endpoint_description || '-'}</td>
                          <td>
                            <span className={`badge ${hasOverride ? 'badge-primary' : 'badge-gray'}`} title="Routing precedence: client-key → endpoint → API">
                              {hasOverride ? 'Endpoint override' : 'API default'}
                            </span>
                          </td>
                          <td>
                            <span className="badge badge-secondary">{(ep.endpoint_servers || []).length}</span>
                          </td>

                        </tr>
                        {expandedKeys.has(k) && (
                          <tr>
                            <td colSpan={6} className="p-0">
                              <div className="bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
                                <div className="p-4 space-y-3">
                                  <div className="flex items-center gap-3">
                                    <div className="flex items-center gap-2">
                                      <input
                                        type="checkbox"
                                        checked={hasOverride}
                                        onChange={async (e) => {
                                          const on = e.target.checked
                                          if (!on) {
                                            await saveEndpointServers(ep, [])
                                          }
                                        }}
                                      />
                                      <span className="text-sm text-gray-700 dark:text-gray-300">Use endpoint servers</span>
                                    </div>
                                    <div className="flex-1" />
                                    <button onClick={(e) => handleDeleteClick(ep, e)} className="btn btn-error btn-sm">Delete Endpoint</button>
                                  </div>
                                  <div className={`${hasOverride ? '' : 'opacity-60'}`}>
                                    <div className="text-sm font-medium mb-1">Endpoint Servers (override API servers)</div>
                                    <div className="space-y-2">
                                      {(ep.endpoint_servers || []).map((srv, idx) => (
                                        <div key={idx} className="flex items-center justify-between bg-white dark:bg-gray-900 px-3 py-2 rounded border">
                                          <span className="text-sm font-mono">{srv}</span>
                                          <button disabled={saving || !hasOverride} onClick={() => removeEndpointServer(ep, idx)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
                                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                          </button>
                                        </div>
                                      ))}
                                      {(ep.endpoint_servers || []).length === 0 && (
                                        <p className="text-xs text-gray-500">No endpoint-specific servers. Using API servers.</p>
                                      )}
                                    </div>
                                    <div className="mt-2 flex gap-2">
                                      <input className="input flex-1" value={epNewServer[k] || ''} onChange={e => setEpNewServer(prev => ({ ...prev, [k]: e.target.value }))} placeholder="Add server URL" onKeyPress={(e) => e.key === 'Enter' && hasOverride && addEndpointServer(ep)} disabled={!hasOverride} />
                                      <button disabled={saving || !hasOverride} onClick={() => addEndpointServer(ep)} className="btn btn-secondary">{saving ? <div className="flex items-center"><div className="spinner mr-2"></div>Saving...</div> : 'Add'}</button>
                                    </div>
                                  </div>
                                  {ep.endpoint_id && (
                                    <div className="mt-4 p-3 rounded border bg-white dark:bg-gray-900">
                                      <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                          <input
                                            type="checkbox"
                                            checked={!!validationByEndpoint[ep.endpoint_id]?.enabled}
                                            onChange={(e) => {
                                              const v = validationByEndpoint[ep.endpoint_id!] || { loading:false, exists:false, enabled:false, schemaText:'{\n}\n', saving:false, error:null }
                                              setValidationByEndpoint(prev => ({ ...prev, [ep.endpoint_id!]: { ...v, enabled: e.target.checked } }))
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                            onFocus={() => ensureValidationLoaded(ep)}
                                          />
                                          <span className="text-sm font-medium">Validation Enabled</span>
                                        </div>
                                        <div className="text-xs text-gray-500">
                                          {validationByEndpoint[ep.endpoint_id]?.exists ? 'Configured' : 'Not configured'}
                                        </div>
                                      </div>
                                      <div>
                                        <label className="block text-xs text-gray-500 mb-1">Validation Schema (JSON)</label>
                                        <textarea
                                          className="input font-mono text-xs h-32"
                                          value={validationByEndpoint[ep.endpoint_id!]?.schemaText || '{\n}\n'}
                                          onChange={(e) => {
                                            const v = validationByEndpoint[ep.endpoint_id!] || { loading:false, exists:false, enabled:false, schemaText:'{\n}\n', saving:false, error:null }
                                            setValidationByEndpoint(prev => ({ ...prev, [ep.endpoint_id!]: { ...v, schemaText: e.target.value } }))
                                          }}
                                          onFocus={() => ensureValidationLoaded(ep)}
                                        />
                                      </div>
                                      {validationByEndpoint[ep.endpoint_id!]?.error && (
                                        <div className="mt-2 text-xs text-error-600">{validationByEndpoint[ep.endpoint_id!]?.error}</div>
                                      )}
                                      <div className="mt-2 flex gap-2">
                                        {validationByEndpoint[ep.endpoint_id!]?.exists ? (
                                          <button
                                            className="btn btn-secondary btn-sm"
                                            disabled={validationByEndpoint[ep.endpoint_id!]?.saving}
                                            onClick={(e) => { e.stopPropagation(); saveValidation(ep) }}
                                          >
                                            {validationByEndpoint[ep.endpoint_id!]?.saving ? 'Saving...' : 'Save'}
                                          </button>
                                        ) : (
                                          <button
                                            className="btn btn-secondary btn-sm"
                                            disabled={validationByEndpoint[ep.endpoint_id!]?.saving}
                                            onClick={(e) => { e.stopPropagation(); createValidation(ep) }}
                                          >
                                            {validationByEndpoint[ep.endpoint_id!]?.saving ? 'Saving...' : 'Create'}
                                          </button>
                                        )}
                                        {validationByEndpoint[ep.endpoint_id!]?.exists && (
                                          <button
                                            className="btn btn-error btn-sm"
                                            disabled={validationByEndpoint[ep.endpoint_id!]?.saving}
                                            onClick={(e) => { e.stopPropagation(); deleteValidation(ep) }}
                                          >
                                            Delete
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <ConfirmModal
        open={!!showDeleteModal && !!endpointToDelete}
        title="Delete Endpoint"
        message={<>
          This action cannot be undone. This will permanently delete endpoint
          <span className="font-mono"> {endpointToDelete?.endpoint_method} {endpointToDelete?.endpoint_uri}</span>.
        </>}
        confirmLabel="Delete Endpoint"
        cancelLabel="Cancel"
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={() => endpointToDelete && deleteEndpoint(endpointToDelete)}
      />
    </Layout>
  )
}
