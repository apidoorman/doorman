'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'
import ConfirmModal from '@/components/ConfirmModal'
import { getJson } from '@/utils/api'

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
    api_allowed_groups: ['ALL'] as string[],
    api_allowed_headers: [] as string[],
    api_authorization_field_swap: '',
    api_credits_enabled: false,
    api_credit_group: '',
    active: true,
    api_auth_required: true,
    api_ip_mode: 'allow_all' as 'allow_all' | 'whitelist',
    api_trust_x_forwarded_for: false,
    validation_enabled: false
  })
  const [publicConfirmOpen, setPublicConfirmOpen] = useState(false)
  const [pendingPublicValue, setPendingPublicValue] = useState<boolean | null>(null)
  const [pubCredsConfirmOpen, setPubCredsConfirmOpen] = useState(false)
  const [pendingPubCredsField, setPendingPubCredsField] = useState<null | { field: 'api_public' | 'api_credits_enabled'; value: boolean }>(null)
  const [newServer, setNewServer] = useState('')
  const [newRole, setNewRole] = useState('')
  const [newGroup, setNewGroup] = useState('')
  const [newHeader, setNewHeader] = useState('')
  const [ipWhitelistText, setIpWhitelistText] = useState('')
  const [ipBlacklistText, setIpBlacklistText] = useState('')
  const [clientIp, setClientIp] = useState('')
  const [clientIpXff, setClientIpXff] = useState('')
  const [protoFile, setProtoFile] = useState<File | null>(null)
  const [uploadProto, setUploadProto] = useState(false)

  React.useEffect(() => {
    (async () => {
      try {
        const data = await getJson<any>(`${SERVER_URL}/platform/security/settings`)
        setClientIp(String(data.client_ip || ''))
        setClientIpXff(String(data.client_ip_xff || ''))
      } catch {}
    })()
  }, [])

  const addMyIpToWhitelist = () => {
    const effectiveIp = (((formData as any).api_trust_x_forwarded_for && clientIpXff) ? clientIpXff : clientIp)
    if (!effectiveIp) return
    const list = ipWhitelistText.split(/\r?\n|,/).map(s => s.trim()).filter(Boolean)
    if (list.includes(effectiveIp)) return
    setIpWhitelistText(prev => (prev && prev.trim().length > 0) ? `${prev.trim()}\n${effectiveIp}` : effectiveIp)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const payload: any = { ...formData }
      payload.api_ip_whitelist = ipWhitelistText.split(/\r?\n|,/).map((s:string) => s.trim()).filter(Boolean)
      payload.api_ip_blacklist = ipBlacklistText.split(/\r?\n|,/).map((s:string) => s.trim()).filter(Boolean)
      if (!payload.api_authorization_field_swap) delete payload.api_authorization_field_swap
      if (!payload.api_credit_group) delete payload.api_credit_group
      if (!Array.isArray(payload.api_allowed_headers) || payload.api_allowed_headers.length === 0) delete payload.api_allowed_headers
      if (!Array.isArray(payload.api_allowed_roles) || payload.api_allowed_roles.length === 0) delete payload.api_allowed_roles
      if (!Array.isArray(payload.api_allowed_groups) || payload.api_allowed_groups.length === 0) {
        payload.api_allowed_groups = ['ALL']
      }
      await postJson(`${SERVER_URL}/platform/api`, payload)
      
      // Upload proto file if provided
      if (uploadProto && protoFile) {
        try {
          const formData = new FormData()
          formData.append('file', protoFile)
          const csrf = document.cookie.split('; ').find(row => row.startsWith('csrf_token='))?.split('=')[1]
          await fetch(`${SERVER_URL}/platform/proto/${encodeURIComponent(payload.api_name)}/${encodeURIComponent(payload.api_version)}`, {
            method: 'POST',
            credentials: 'include',
            headers: csrf ? { 'X-CSRF-Token': csrf } : {},
            body: formData
          })
        } catch (protoErr) {
          console.error('Proto upload failed:', protoErr)
          // Don't fail the whole operation if proto upload fails
        }
      }
      
      router.push('/apis')
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    if (name === 'api_public' && type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked
      if (checked) {
        setPendingPublicValue(true)
        setPublicConfirmOpen(true)
        return
      }
    }
    if (name === 'api_public' && (e.target as HTMLInputElement).checked && (formData as any).api_credits_enabled) {
      setPendingPubCredsField({ field: 'api_public', value: true })
      setPubCredsConfirmOpen(true)
      return
    }
    if (name === 'api_credits_enabled' && (e.target as HTMLInputElement).checked && ((formData as any).api_public || pendingPublicValue)) {
      setPendingPubCredsField({ field: 'api_credits_enabled', value: true })
      setPubCredsConfirmOpen(true)
      return
    }
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

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Basic Information</h3>
              <FormHelp docHref="/docs/using-fields.html#apis">Fill API name/version; these form the base path clients call.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              {((formData as any).api_public && (formData as any).api_credits_enabled) && (
                <div className="rounded-lg bg-warning-50 border border-warning-200 p-3 text-warning-800 dark:bg-warning-900/20 dark:border-warning-800 dark:text-warning-200">
                  Public + Credits: Anyone can call this API and the group API key will be injected. Per-user deductions/keys are skipped.
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Public API <InfoTooltip text="Anyone with the URL can call this API. Auth, subscription, and group checks are skipped." /></label>
                <div className="flex items-center">
                  <input
                    id="api_public"
                    name="api_public"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={(formData as any).api_public || false}
                    onChange={handleChange}
                    disabled={loading || ((formData as any).api_credits_enabled === true)}
                  />
                  <label htmlFor="api_public" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                    Anyone with the URL can call this API
                  </label>
                </div>
                {((formData as any).api_credits_enabled === true) && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Disable Credits to change Public status.</p>
                )}
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">Use with care. Authentication, subscriptions, and group checks are skipped.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Active</label>
                <div className="flex items-center">
                  <input
                    id="active"
                    name="active"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={formData.active as any}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <label htmlFor="active" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                    Enable this API
                  </label>
                </div>
              </div>
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
                  API version (e.g., v1, v2)
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
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">IP Access Control</h3>
              <FormHelp docHref="/docs/using-fields.html#api-ip-policy">Control IP access per API.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              {(() => {
                const effectiveIp = (((formData as any).api_trust_x_forwarded_for && clientIpXff) ? clientIpXff : clientIp)
                const listFromText = (t: string) => t.split(/\r?\n|,/).map(s=>s.trim()).filter(Boolean)
                const wl = listFromText(ipWhitelistText)
                const bl = listFromText(ipBlacklistText)
                const isIPv6 = (s: string) => s.includes(':')
                const toIPv4 = (s: string) => { const parts = s.split('.'); if (parts.length !== 4) return null as any; return parts.reduce((a,p)=> (a<<8n)+(BigInt(parseInt(p,10)&255)),0n) }
                const expandIPv6 = (ip: string) => { if (ip.indexOf('::') !== -1) { const [head, tail] = ip.split('::'); const headParts = head ? head.split(':') : []; const tailParts = tail ? tail.split(':') : []; const missing = 8 - (headParts.length + tailParts.length); const zeros = Array(Math.max(0, missing)).fill('0'); return [...headParts, ...zeros, ...tailParts].map(h=>h || '0') } return ip.split(':') }
                const toIPv6 = (s: string) => { const parts = expandIPv6(s); if (parts.length !== 8) return null as any; try { return parts.reduce((acc, h) => (acc<<16n) + BigInt(parseInt(h || '0', 16)), 0n) } catch { return null as any } }
                const matches = (ip: string, patterns: string[]) => {
                  if (!ip) return false
                  const v6 = isIPv6(ip)
                  const ipVal = v6 ? toIPv6(ip) : toIPv4(ip)
                  return patterns.some(raw => {
                    const p = raw.trim(); if (!p) return false
                    if (p.includes('/')) {
                      const [net, maskStr] = p.split('/'); const m = parseInt(maskStr,10)
                      const n6 = isIPv6(net); if (n6 !== v6) return false
                      const netVal = n6 ? toIPv6(net) : toIPv4(net); if (netVal === null || ipVal === null || isNaN(m as any)) return false
                      const bits = n6 ? 128 : 32
                      const shift = BigInt(bits - Math.min(Math.max(m,0), bits))
                      const mask = ((1n << BigInt(bits)) - 1n) ^ ((1n << shift) - 1n)
                      return ((ipVal & mask) === (netVal & mask))
                    }
                    return p.toLowerCase() === ip.toLowerCase()
                  })
                }
                const warnWL = ((formData as any).api_ip_mode === 'whitelist') && wl.length > 0 && !matches(effectiveIp, wl)
                const warnBL = matches(effectiveIp, bl)
                if (!(warnWL || warnBL)) return null
                return (
                  <div className="rounded-md bg-warning-50 border border-warning-200 p-3 text-warning-800 dark:bg-warning-900/20 dark:border-warning-800 dark:text-warning-200">
                    {warnBL ? 'Warning: Your current IP appears in the blacklist and you may lose access after saving.' : 'Warning: Your current IP is not in the whitelist and you may lose access after saving.'}
                    <div className="text-xs mt-1">Your IP: {effectiveIp || 'unknown'} {((formData as any).api_trust_x_forwarded_for ? '(using X-Forwarded-For)' : '')}</div>
                  </div>
                )
              })()}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Policy</label>
                  <select name="api_ip_mode" className="input" value={formData.api_ip_mode}
                    onChange={(e)=>setFormData(p=>({...p, api_ip_mode: e.target.value as any}))}>
                    <option value="allow_all">Allow All</option>
                    <option value="whitelist">Whitelist</option>
                  </select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">When Whitelist is selected, only listed IPs/CIDRs can call this API. Blacklist applies always.</p>
                </div>
                <div className="md:col-span-2 flex items-center gap-2">
                  <input id="api_trust_x_forwarded_for" type="checkbox" className="h-4 w-4" checked={!!(formData as any).api_trust_x_forwarded_for} onChange={(e)=>setFormData(p=>({...p, api_trust_x_forwarded_for: e.target.checked}))} />
                  <label htmlFor="api_trust_x_forwarded_for" className="text-sm text-gray-700 dark:text-gray-300">Trust X-Forwarded-For (behind proxy)</label>
                  <InfoTooltip text="If enabled, the effective IP for this API is taken from X-Forwarded-For (first hop) or X-Real-IP when present. Platform 'Trusted Proxies' must include the direct source; otherwise headers are ignored to prevent spoofing." />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Whitelist (one per line or comma-separated)</label>
                    <button type="button" className="btn btn-ghost btn-xs" onClick={addMyIpToWhitelist}>Add My IP</button>
                  </div>
                  <textarea className="input min-h-[120px]" value={ipWhitelistText} onChange={(e)=>setIpWhitelistText(e.target.value)} placeholder="192.168.1.10\n10.0.0.0/8" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Blacklist (one per line or comma-separated)</label>
                  <textarea className="input min-h-[120px]" value={ipBlacklistText} onChange={(e)=>setIpBlacklistText(e.target.value)} placeholder="203.0.113.0/24" />
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Configuration</h3>
              <FormHelp docHref="/docs/using-fields.html#api-config">Set credits, auth header mapping, and validations.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Auth Required <InfoTooltip text="When enabled (default), requests must be authenticated and pass subscription/group checks. Disable to allow unauthenticated access (not public)." /></label>
                <div className="flex items-center">
                  <input
                    id="api_auth_required"
                    name="api_auth_required"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={(formData as any).api_auth_required}
                    onChange={handleChange}
                    disabled={loading}
                  />
                  <label htmlFor="api_auth_required" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                    Require platform auth (JWT) for this API
                  </label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Disable to accept unauthenticated requests. Not public — but subscription/group checks are skipped without auth.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Credits Enabled
                  <InfoTooltip text="When enabled, each request to this API deducts credits before proxying. Note: Public APIs skip credit deductions and per-user keys." />
                </label>
                <div className="flex items-center">
                  <input
                    id="api_credits_enabled"
                    name="api_credits_enabled"
                    type="checkbox"
                    className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    checked={formData.api_credits_enabled}
                    onChange={handleChange}
                    disabled={loading || ((formData as any).api_public === true)}
                  />
                  <label htmlFor="api_credits_enabled" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                    Enable API credits
                  </label>
                </div>
                {((formData as any).api_public === true) && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Disable Public to enable Credits.</p>
                )}
              </div>
              {formData.api_credits_enabled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Credit Group
                    <InfoTooltip text="Configured credit group (e.g., ai-basic). Determines the API key header injected. Per-user keys apply only when Auth Required is enabled." />
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Authorization Field Swap
                  <InfoTooltip text="Map inbound Authorization header into a different header name expected by the upstream service. Example: X-Api-Key." />
                </label>
                <input type="text" name="api_authorization_field_swap" className="input" placeholder="backend-auth-header" value={formData.api_authorization_field_swap} onChange={handleChange} disabled={loading} />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Servers</h3>
              <FormHelp docHref="/docs/using-fields.html#servers">Add one or more upstream base URLs used for proxying.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Servers
                <InfoTooltip text="Base URLs for upstreams. Include scheme and port. Example: http://localhost:8080" />
              </label>
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
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Allowed Roles</h3>
              <FormHelp docHref="/docs/using-fields.html#access-control">Grant access by platform roles and groups.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Allowed Roles
                  <InfoTooltip text="Only enforced when Auth Required is enabled. Users must have any of these platform roles." />
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
            </div>
          </div>

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Allowed Groups</h3>
              <FormHelp docHref="/docs/using-fields.html#access-control">Restrict by user groups; use ALL to allow any group.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Allowed Groups
                  <InfoTooltip text="Only enforced when Auth Required is enabled. User must belong to any listed group (e.g., ALL)." />
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
            <div className="card-header flex items-center justify-between">
              <h3 className="card-title">Allowed Headers</h3>
              <FormHelp docHref="/docs/using-fields.html#header-forwarding">Choose which upstream response headers are forwarded.</FormHelp>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Allowed Headers
                  <InfoTooltip text="Response headers from upstream that Doorman may forward back to the client. Use lowercase names; examples: x-rate-limit, retry-after." />
                </label>
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

          <div className="card">
            <div className="card-header">
              <h3 className="card-title">gRPC Proto Configuration (Optional)</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Upload a Protocol Buffer definition for gRPC APIs</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <input
                  type="checkbox"
                  id="upload_proto"
                  checked={uploadProto}
                  onChange={(e) => {
                    setUploadProto(e.target.checked)
                    if (!e.target.checked) setProtoFile(null)
                  }}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <label htmlFor="upload_proto" className="flex-1 cursor-pointer">
                  <p className="font-medium text-gray-900 dark:text-white">Upload Proto File</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Enable gRPC support by uploading a .proto file after API creation
                  </p>
                </label>
              </div>

              {uploadProto && (
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Select Proto File
                  </label>
                  <div className="flex items-center gap-3">
                    <label className="btn btn-secondary cursor-pointer">
                      <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      Choose File
                      <input
                        type="file"
                        accept=".proto,text/plain"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (file) {
                            if (!file.name.endsWith('.proto')) {
                              alert('Please select a .proto file')
                              e.target.value = ''
                              return
                            }
                            setProtoFile(file)
                          }
                        }}
                      />
                    </label>
                    {protoFile && (
                      <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                        <svg className="h-5 w-5 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="font-medium">{protoFile.name}</span>
                        <button
                          type="button"
                          onClick={() => setProtoFile(null)}
                          className="text-error-600 hover:text-error-800 dark:text-error-400"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    The proto file will be uploaded and compiled automatically after the API is created successfully.
                  </p>
                </div>
              )}
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
      <ConfirmModal
        open={publicConfirmOpen}
        title="Make API Public?"
        message={<div>
          <p className="mb-2">This API will be public. Anyone with the URL can call it.</p>
          <p className="text-amber-600">Authentication, subscriptions, and group checks will be skipped.</p>
        </div>}
        confirmLabel="Make Public"
        onConfirm={() => {
          setPublicConfirmOpen(false)
          if (pendingPublicValue) {
            setFormData(prev => ({ ...prev, api_public: true as any }))
          }
          setPendingPublicValue(null)
        }}
        onCancel={() => {
          setPublicConfirmOpen(false)
          setPendingPublicValue(null)
        }}
      />

      <ConfirmModal
        open={pubCredsConfirmOpen}
        title="Public API with Credits?"
        message={<div>
          <p className="mb-2">Enabling Credits on a Public API injects the group API key for anyone calling this API.</p>
          <p className="text-amber-600">User-level deductions/keys are skipped for public/no-auth calls.</p>
        </div>}
        confirmLabel="Proceed"
        onConfirm={() => {
          setPubCredsConfirmOpen(false)
          if (pendingPubCredsField) {
            setFormData(prev => ({ ...prev, [pendingPubCredsField.field]: pendingPubCredsField.value as any }))
          }
          setPendingPubCredsField(null)
        }}
        onCancel={() => {
          setPubCredsConfirmOpen(false)
          setPendingPubCredsField(null)
        }}
      />
    </Layout>
  )
}

export default AddApiPage
