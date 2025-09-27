'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'

export default function AddEndpointPage() {
  const params = useParams()
  const router = useRouter()
  const apiId = params.apiId as string
  const [apiName, setApiName] = useState('')
  const [apiVersion, setApiVersion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [method, setMethod] = useState('GET')
  const [uri, setUri] = useState('')
  const [description, setDescription] = useState('')
  const [useOverride, setUseOverride] = useState(false)
  const [servers, setServers] = useState<string[]>([])
  const [newServer, setNewServer] = useState('')

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

  const addServer = () => {
    const v = newServer.trim()
    if (!v) return
    if (servers.includes(v)) return
    setServers(prev => [...prev, v])
    setNewServer('')
  }

  const removeServer = (idx: number) => {
    setServers(prev => prev.filter((_, i) => i !== idx))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uri.trim()) return
    setLoading(true)
    setError(null)
    try {
      const body: any = {
        api_name: apiName,
        api_version: apiVersion,
        endpoint_method: method,
        endpoint_uri: uri.startsWith('/') ? uri : '/' + uri,
        endpoint_description: description || `${method} ${uri}`
      }
      if (useOverride && servers.length > 0) {
        body.endpoint_servers = servers
      }
      await postJson(`${SERVER_URL}/platform/endpoint`, body)
      setSuccess('Endpoint created')
      setTimeout(() => setSuccess(null), 1500)
      router.push(`/apis/${encodeURIComponent(apiId)}/endpoints`)
    } catch (e:any) {
      setError(e?.message || 'Failed to create endpoint')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Add Endpoint</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">For API {apiName}/{apiVersion}</p>
          </div>
          <div className="flex gap-2">
            <Link href={`/apis/${encodeURIComponent(apiId)}/endpoints`} className="btn btn-secondary">Back to Endpoints</Link>
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

        <div className="card max-w-3xl">
          <form onSubmit={handleSubmit} className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2 -mt-2 mb-2">
              <FormHelp docHref="/docs/using-fields.html#endpoints">Define method and URI; optional upstream override per endpoint.</FormHelp>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Method</label>
              <select className="input" value={method} onChange={e => setMethod(e.target.value)}>
                {['GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS'].map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                URI
                <InfoTooltip text="Path pattern relative to the API base. Use {param} for path variables. Example: /items/{id}" />
              </label>
              <input className="input" value={uri} onChange={e => setUri(e.target.value)} placeholder="/path/{id}" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">Description</label>
              <input className="input" value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe endpoint" />
            </div>

            <div className="md:col-span-2">
              <div className="flex items-center gap-2 mb-2">
                <input id="use-override" type="checkbox" className="h-4 w-4" checked={useOverride} onChange={(e)=>setUseOverride(e.target.checked)} />
                <label htmlFor="use-override" className="text-sm">
                  Use endpoint servers (override API servers)
                  <InfoTooltip text="Provide endpoint-specific upstreams. If disabled or empty, the API-level servers are used." />
                </label>
              </div>
              <div className={`flex gap-2 ${useOverride ? '' : 'opacity-60'}`}>
                <input
                  className="input flex-1"
                  value={newServer}
                  onChange={e => setNewServer(e.target.value)}
                  placeholder="e.g., http://localhost:8082"
                  onKeyPress={(e) => useOverride && e.key === 'Enter' && addServer()}
                  disabled={!useOverride}
                />
                <button type="button" onClick={addServer} className="btn btn-secondary" disabled={!useOverride}>Add</button>
              </div>
              <div className={`mt-2 space-y-2 ${useOverride ? '' : 'opacity-60'}`}>
                {servers.map((srv, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded">
                    <span className="text-sm font-mono">{srv}</span>
                    <button type="button" onClick={() => removeServer(idx)} className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200" disabled={!useOverride}>
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
                {!useOverride && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">Disabled — API servers will be used unless enabled.</p>
                )}
                {useOverride && servers.length === 0 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">No endpoint-specific servers. API servers will be used.</p>
                )}
              </div>
            </div>

            <div className="md:col-span-2">
              <button type="submit" className="btn btn-primary" disabled={loading || !uri.trim()}>
                {loading ? <div className="flex items-center"><div className="spinner mr-2"></div>Creating...</div> : 'Create Endpoint'}
              </button>
              <Link href={`/apis/${encodeURIComponent(apiId)}/endpoints`} className="btn btn-ghost ml-2">Cancel</Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}
