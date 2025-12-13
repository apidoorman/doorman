'use client'

import React, { useEffect, useMemo, useState } from 'react'

type HttpMethod = 'get' | 'post' | 'put' | 'delete' | 'patch' | 'head' | 'options' | 'trace'

function methodColors(method: string) {
  switch (method.toUpperCase()) {
    case 'GET': return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
    case 'POST': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
    case 'PUT': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
    case 'PATCH': return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
    case 'DELETE': return 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
    default: return 'bg-gray-100 text-gray-800 dark:bg-white/5 dark:text-white/70'
  }
}

function toTitle(s: string) {
  return s.replace(/[-_]+/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
}

export default function OpenApiViewer({ openapiUrl }: { openapiUrl: string }) {
  const [spec, setSpec] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(openapiUrl, { cache: 'no-store' })
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const json = await res.json()
        if (!cancelled) setSpec(json)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [openapiUrl])

  const tagged = useMemo(() => {
    if (!spec?.paths) return { order: [] as string[], map: {} as Record<string, any[]> }
    const map: Record<string, any[]> = {}
    const tagsOrder = (spec.tags?.map((t: any) => t.name) ?? []) as string[]
    for (const [path, pathItem] of Object.entries<any>(spec.paths)) {
      for (const m of Object.keys(pathItem) as HttpMethod[]) {
        const op = (pathItem as any)[m]
        if (!op || typeof op !== 'object') continue
        const opTags: string[] = (op.tags && op.tags.length ? op.tags : ['General']) as string[]
        for (const t of opTags) {
          map[t] = map[t] || []
          map[t].push({ ...op, method: (m as string).toUpperCase(), path })
        }
      }
    }
    const remaining = Object.keys(map).filter(t => !tagsOrder.includes(t)).sort()
    const order = [...tagsOrder, ...remaining]
    return { order, map }
  }, [spec])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return tagged
    const map: Record<string, any[]> = {}
    const order: string[] = []
    for (const tag of tagged.order) {
      const items = (tagged.map[tag] || []).filter(op => {
        const hay = `${op.summary || ''} ${op.description || ''} ${op.operationId || ''} ${op.method} ${op.path}`.toLowerCase()
        return hay.includes(q)
      })
      if (items.length) { map[tag] = items; order.push(tag) }
    }
    return { order, map }
  }, [tagged, search])

  function computeBaseUrl(): string {
    try {
      const server = Array.isArray(spec?.servers) && spec.servers.length > 0 ? spec.servers[0].url : ''
      if (server) return (server as string).replace(/\/$/, '')
    } catch {}
    if (typeof window !== 'undefined') return window.location.origin
    return ''
  }

  function sampleValue(schema: any, forPath = false): any {
    if (!schema) return forPath ? 'id' : 'string'
    const t = schema.type || (schema.oneOf?.[0]?.type) || (schema.anyOf?.[0]?.type) || (schema.allOf?.[0]?.type)
    if (t === 'integer' || t === 'number') return forPath ? 1 : 1
    if (t === 'boolean') return forPath ? 'true' : true
    if (t === 'array') return [sampleValue(schema.items)]
    if (t === 'object' || schema.properties) {
      const obj: any = {}
      const props = schema.properties || {}
      const keys = Object.keys(props).slice(0, 3)
      for (const k of keys) obj[k] = sampleValue((props as any)[k])
      return obj
    }
    return forPath ? 'value' : 'string'
  }

  function buildCurl(op: any): string {
    const base = computeBaseUrl()
    let urlPath = op.path
    const params = Array.isArray(op.parameters) ? op.parameters : []
    const pathParams = params.filter((p: any) => p.in === 'path')
    for (const p of pathParams) {
      const val = sampleValue(p.schema, true)
      urlPath = urlPath.replace(`{${p.name}}`, String(val))
    }
    const qParams = params.filter((p: any) => p.in === 'query')
    const qs = qParams.map((p: any) => `${encodeURIComponent(p.name)}=${encodeURIComponent(String(sampleValue(p.schema, true)))}`).join('&')
    const fullUrl = `${base}${urlPath}${qs ? (urlPath.includes('?') ? '&' : '?') + qs : ''}`

    let body = ''
    const content = op.requestBody?.content || {}
    const jsonSchema = content['application/json']?.schema
    if (jsonSchema && (op.method === 'POST' || op.method === 'PUT' || op.method === 'PATCH')) {
      body = JSON.stringify(sampleValue(jsonSchema), null, 2)
    }

    const lines: string[] = ['# Example curl']
    if (body) {
      const escapedBody = body.replace(/'/g, "'\\''")
      lines.push(`curl -X ${op.method} \\`)
      lines.push(`  -H "Content-Type: application/json" \\`)
      lines.push(`  "${fullUrl}" \\`)
      lines.push(`  -d '${escapedBody}'`)
    } else {
      lines.push(`curl -X ${op.method} "${fullUrl}"`)
    }
    return lines.join('\n')
  }

  if (loading) return <div className="p-4 text-sm text-gray-500 dark:text-white/70">Loading OpenAPI...</div>
  if (error) return <div className="p-4 text-sm text-error-600 dark:text-error-400">Failed to load OpenAPI: {error}</div>
  if (!spec) return <div className="p-4 text-sm text-gray-500 dark:text-white/70">No spec</div>

  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_260px] gap-6">
      <div>
        <div className="mb-3">
          <input
            type="search"
            placeholder="Search endpoints..."
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600 dark:border-white/10 dark:bg-[#252525] dark:text-white/80 dark:placeholder-white/40"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {filtered.order.map((tag) => (
          <section key={tag} id={tag} className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{toTitle(tag)}</h2>
            <div className="space-y-2">
              {(filtered.map[tag] || []).map((op, i) => {
                const key = `${tag}-${op.method}-${op.path}-${i}`
                const isOpen = !!expanded[key]
                return (
                  <div key={key} className="rounded-md border border-gray-200 dark:border-white/10 bg-white dark:bg-dark-surface">
                    <button
                      onClick={() => setExpanded(prev => ({ ...prev, [key]: !isOpen }))}
                      className="w-full text-left px-3 py-2 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <span className={`text-[11px] px-2 py-0.5 rounded ${methodColors(op.method)}`}>{op.method}</span>
                      <span className="font-mono text-[12px] text-gray-900 dark:text-white">{op.path}</span>
                      {op.summary && <span className="text-sm text-gray-600 dark:text-white/70">— {op.summary}</span>}
                      <span className="ml-auto text-gray-400">{isOpen ? '▾' : '▸'}</span>
                    </button>
                    {isOpen && (
                      <div className="px-4 pb-3">
                        {op.description && (
                          <div className="markdown max-w-none my-2" dangerouslySetInnerHTML={{ __html: op.description }} />
                        )}
                        <div className="mt-2">
                          <div className="flex items-center justify-between">
                            <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-1">Example</div>
                            <button
                              className="text-xs px-2 py-0.5 rounded border border-gray-200 dark:border-white/10 hover:bg-gray-50 dark:hover:bg-white/5"
                              onClick={() => { try { navigator.clipboard.writeText(buildCurl(op)) } catch {} }}
                            >Copy</button>
                          </div>
                          <pre className="text-[12px] overflow-auto"><code>{buildCurl(op)}</code></pre>
                        </div>
                        {Array.isArray(op.parameters) && op.parameters.length > 0 && (
                          <div className="mt-2">
                            <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-1">Parameters</div>
                            <div className="overflow-auto">
                              <table className="table w-full">
                                <thead>
                                  <tr>
                                    <th>Name</th>
                                    <th>In</th>
                                    <th>Type</th>
                                    <th>Required</th>
                                    <th>Description</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {op.parameters.map((p: any, idx: number) => (
                                    <tr key={idx}>
                                      <td className="font-mono text-[12px]">{p.name}</td>
                                      <td className="text-[12px]">{p.in}</td>
                                      <td className="text-[12px]">{p.schema?.type || ''}</td>
                                      <td className="text-[12px]">{p.required ? 'Yes' : 'No'}</td>
                                      <td className="text-[12px]">{p.description || ''}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                        {op.responses && (
                          <div className="mt-3">
                            <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-1">Responses</div>
                            <div className="space-y-2">
                              {Object.entries<any>(op.responses).map(([code, resp]) => (
                                <div key={code} className="rounded border border-gray-200 dark:border-white/10">
                                  <div className="px-3 py-1.5 text-sm flex items-center gap-2 bg-gray-50 dark:bg-white/5">
                                    <span className="font-mono text-[12px]">{code}</span>
                                    <span className="text-gray-700 dark:text-white/70">{(resp as any).description || ''}</span>
                                  </div>
                                  {resp?.content && resp.content['application/json']?.schema && (
                                    <div className="px-3 py-2">
                                      <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-1">Schema</div>
                                      <pre className="text-[12px]"><code>{JSON.stringify(resp.content['application/json'].schema, null, 2)}</code></pre>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>

      <aside className="hidden md:block sticky top-16 h-max border-l border-gray-200 dark:border-white/10 pl-4">
        <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-white/50 mb-2">Tags</div>
        <nav className="space-y-1">
          {filtered.order.map((t) => (
            <a key={t} href={`#${t}`} className="block text-sm hover:underline">{toTitle(t)}</a>
          ))}
        </nav>
      </aside>
    </div>
  )
}

