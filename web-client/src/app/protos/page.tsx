'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import { useToast } from '@/contexts/ToastContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'

type ApiItem = {
  api_id: string
  api_name: string
  api_version: string
  api_description?: string
}

type ProtoState = {
  loading: boolean
  exists: boolean | null
  content?: string
  error?: string | null
  working?: boolean
  deleted?: boolean
}

async function fetchWithCsrf(input: RequestInfo, init: RequestInit = {}) {
  try {
    const mod = await import('@/utils/http')
    const csrf = mod.getCookie ? mod.getCookie('csrf_token') : null
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
  } catch (e) {
    throw e
  }
}

export default function ProtosPage() {
  const [apis, setApis] = useState<ApiItem[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [protoByKey, setProtoByKey] = useState<Record<string, ProtoState>>({})
  const [search, setSearch] = useState('')
  const toast = useToast()

  const keyFor = (a: ApiItem) => `${a.api_name}/${a.api_version}`

  useEffect(() => {
    const loadApis = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await getJson<any>(`${SERVER_URL}/platform/api/all?page=${page}&page_size=${pageSize}`)
        const list: ApiItem[] = Array.isArray(data) ? data : (data.apis || data.response?.apis || [])
        setApis(list)
        await Promise.all(list.map(a => checkProto(a)))
      } catch (e: any) {
        setError(e?.message || 'Failed to load APIs')
        setApis([])
      } finally {
        setLoading(false)
      }
    }
    loadApis()
  }, [page, pageSize])

  const checkProto = async (api: ApiItem) => {
    const k = keyFor(api)
    setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), loading: true, error: null as any } }))
    try {
      const payload = await fetchWithCsrf(`${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`)
      const content = payload?.content || ''
      setProtoByKey(prev => ({ ...prev, [k]: { loading: false, exists: true, content, error: null } }))
    } catch (e: any) {
      if (String(e?.message || '').toLowerCase().includes('not found')) {
        setProtoByKey(prev => ({ ...prev, [k]: { loading: false, exists: false, content: undefined, error: null } }))
      } else {
        setProtoByKey(prev => ({ ...prev, [k]: { loading: false, exists: null, content: undefined, error: e?.message || 'Failed to check proto' } }))
      }
    }
  }

  const uploadOrUpdate = async (api: ApiItem, file: File, mode: 'create'|'update') => {
    const k = keyFor(api)
    setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), working: true, error: null as any } }))
    try {
      const form = new FormData()
      if (mode === 'create') form.append('file', file)
      else form.append('proto_file', file)
      const url = `${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`
      const method = mode === 'create' ? 'POST' : 'PUT'
      await fetchWithCsrf(url, { method, body: form })
      setSuccess(mode === 'create' ? 'Proto uploaded' : 'Proto updated')
      toast.success(mode === 'create' ? 'Proto uploaded' : 'Proto updated')
      setTimeout(() => setSuccess(null), 2000)
      await checkProto(api)
    } catch (e: any) {
      setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), error: e?.message || 'Operation failed' } }))
    } finally {
      setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), working: false } }))
    }
  }

  const deleteProto = async (api: ApiItem) => {
    const k = keyFor(api)
    setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), working: true, error: null as any } }))
    try {
      await fetchWithCsrf(`${SERVER_URL}/platform/proto/${encodeURIComponent(api.api_name)}/${encodeURIComponent(api.api_version)}`, { method: 'DELETE' })
      setSuccess('Proto deleted')
      toast.success('Proto deleted')
      setTimeout(() => setSuccess(null), 2000)
      setProtoByKey(prev => ({ ...prev, [k]: { loading: false, exists: false, deleted: true, content: undefined, error: null } }))
    } catch (e: any) {
      setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), working: false, error: e?.message || 'Delete failed' } }))
    } finally {
      setProtoByKey(prev => ({ ...prev, [k]: { ...(prev[k] || {}), working: false } }))
    }
  }

  const FileInput: React.FC<{ api: ApiItem; mode: 'create'|'update' }> = ({ api, mode }) => {
    const [busy, setBusy] = useState(false)
    const k = keyFor(api)
    const working = protoByKey[k]?.working || false
    return (
      <label className={`btn btn-secondary ${busy ? 'opacity-60' : ''}`}>
        {mode === 'create' ? 'Upload' : 'Replace'}
        <input
          type="file"
          accept=".proto,text/plain"
          style={{ display: 'none' }}
          onChange={async (e) => {
            const f = e.target.files?.[0]
            if (!f) return
            setBusy(true)
            await uploadOrUpdate(api, f, mode)
            setBusy(false)
            e.currentTarget.value = ''
          }}
          disabled={busy || working}
        />
      </label>
    )
  }

  const filteredApis = useMemo(() => {
    const s = search.trim().toLowerCase()
    if (!s) return apis
    return apis.filter(a =>
      a.api_name.toLowerCase().includes(s) ||
      a.api_version.toLowerCase().includes(s) ||
      (a.api_description || '').toLowerCase().includes(s)
    )
  }, [apis, search])

  return (
    <ProtectedRoute requiredPermission="manage_apis">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">gRPC Protos</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Upload, view, update, and delete proto files per API</p>
            </div>
            <div className="flex gap-2 items-center">
              <button className="btn btn-secondary" onClick={() => { setPage(1); setPageSize(pageSize) }}>Refresh</button>
            </div>
          </div>
          <div className="card">
            <form onSubmit={(e) => { e.preventDefault() }} className="flex-1">
              <div className="relative">
                <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search by name, version, or description..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
            </form>
          </div>

          {success && (
            <div className="rounded-lg bg-success-50 border border-success-200 p-4 dark:bg-success-900/20 dark:border-success-800">
              <p className="text-sm text-success-700 dark:text-success-300">{success}</p>
            </div>
          )}
          {error && (
            <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
              <p className="text-sm text-error-700 dark:text-error-300">{error}</p>
            </div>
          )}

          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>API</th>
                    <th>Description</th>
                    <th>Proto</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={4}><div className="p-6 text-gray-500">Loading...</div></td></tr>
                  ) : filteredApis.length === 0 ? (
                    <tr><td colSpan={4}><div className="p-6 text-gray-500">No APIs found</div></td></tr>
                  ) : (
                    filteredApis.map(api => {
                      const k = keyFor(api)
                      const st = protoByKey[k] || { loading: false, exists: null }
                      return (
                        <tr key={k}>
                          <td className="whitespace-nowrap font-mono">{api.api_name}/{api.api_version}</td>
                          <td className="max-w-xl truncate">{api.api_description || ''}</td>
                          <td className="w-48">
                            {st.loading ? (
                              <span className="text-gray-500">Checking...</span>
                            ) : st.exists === true ? (
                              <span className="text-success-700 dark:text-success-400">Present</span>
                            ) : st.exists === false ? (
                              <span className="text-error-700 dark:text-error-400">{st.deleted ? 'Deleted' : 'Missing'}</span>
                            ) : (
                              <button className="btn btn-ghost btn-sm" onClick={() => checkProto(api)}>Check</button>
                            )}
                            {st.error && <div className="text-xs text-error-600 mt-1">{st.error}</div>}
                          </td>
                          <td className="flex gap-2 items-center">
                            <button className="btn btn-secondary btn-sm" onClick={() => checkProto(api)} disabled={st.loading}>View</button>
                            <FileInput api={api} mode="create" />
                            <FileInput api={api} mode="update" />
                            <button className="btn btn-error btn-sm" onClick={() => deleteProto(api)} disabled={st.working}>Delete</button>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {Object.entries(protoByKey).some(([_, v]) => v?.content) && (
            <div className="card">
              <div className="card-header"><h3 className="card-title">Proto Content</h3></div>
              <div className="p-4 overflow-auto">
                {Object.entries(protoByKey).map(([k, v]) => v?.content ? (
                  <div key={k} className="mb-6">
                    <div className="text-sm font-mono text-gray-500 mb-2">{k}</div>
                    <pre className="text-xs whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded">{v.content}</pre>
                  </div>
                ) : null)}
              </div>
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
