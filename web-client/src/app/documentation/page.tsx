'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import MarkdownViewer from '@/components/MarkdownViewer'
import HtmlViewer from '@/components/HtmlViewer'
import { SERVER_URL } from '@/utils/config'

export default function DocumentationPage() {
  // Serve the gateway documentation (static HTML) from the app public folder
  // Keep a link to the API reference (Swagger) for developers who need it
  // User-facing documentation tabs (exclude setup/ops)
  const tabs = [
    { key: 'guides', label: 'Guides', type: 'md', src: '/docs/guides.md' },
    { key: 'users', label: 'Users & Roles', type: 'md', src: '/docs/howto-users-roles.md' },
    { key: 'apis', label: 'Publish REST API', type: 'md', src: '/docs/howto-create-api-rest.md' },
    { key: 'rate', label: 'Rate & Throttle', type: 'md', src: '/docs/howto-rate-throttle.md' },
    { key: 'credits', label: 'Credits & Quotas', type: 'md', src: '/docs/howto-credits-quotas.md' },
    { key: 'workflows', label: 'API Workflows', type: 'md', src: '/docs/api-workflows.md' },
    { key: 'fields', label: 'Using Fields', type: 'html', src: '/docs/using-fields.html' },
    { key: 'security', label: 'Security', type: 'md', src: '/docs/security.md' },
    { key: 'troubleshooting', label: 'Troubleshooting', type: 'md', src: '/docs/troubleshooting.md' },
    { key: 'openapi', label: 'Open API Docs', type: 'frame', src: `${SERVER_URL}/platform/docs` },
  ]
  const [active, setActive] = useState<typeof tabs[number]['key']>('guides')
  const [search, setSearch] = useState('')
  const [index, setIndex] = useState<Array<{ key: string; label: string; src: string; headings: Array<{ text: string; id: string }>; text: string }>>([])

  // Build a simple search index for markdown tabs
  useEffect(() => {
    let cancelled = false
    async function build() {
      try {
        const mdTabs = tabs.filter(t => t.type === 'md')
        const out: Array<{ key: string; label: string; src: string; headings: Array<{ text: string; id: string }>; text: string }> = []
        for (const t of mdTabs) {
          const res = await fetch(t.src, { cache: 'no-store' })
          const raw = await res.text()
          const lines = raw.replaceAll('\r\n', '\n').split('\n')
          const headings: Array<{ text: string; id: string }> = []
          let text = ''
          let inCode = false
          for (const r of lines) {
            const line = r.trimEnd()
            if (line.startsWith('```')) { inCode = !inCode; continue }
            if (!inCode) {
              const m = line.match(/^(#{1,6})\s+(.*)$/)
              if (m) {
                const ht = m[2].trim()
                const id = ht.toLowerCase().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').slice(0, 64)
                headings.push({ text: ht, id })
              }
            }
            text += r + '\n'
          }
          out.push({ key: t.key, label: t.label, src: t.src, headings, text })
        }
        if (!cancelled) setIndex(out)
      } catch {}
    }
    build()
    return () => { cancelled = true }
  }, [])

  const results = useMemo(() => {
    const q = search.trim()
    if (q.length < 2) return [] as Array<{ key: string; label: string; anchor?: string; snippet: string }>
    const lower = q.toLowerCase()
    const hits: Array<{ key: string; label: string; anchor?: string; snippet: string }> = []
    for (const doc of index) {
      const pos = doc.text.toLowerCase().indexOf(lower)
      if (pos >= 0) {
        // Find closest heading
        let anchor: string | undefined
        try {
          const before = doc.text.slice(0, pos)
          const lines = before.split('\n')
          for (let i = lines.length - 1; i >= 0; i--) {
            const m = lines[i].match(/^#{1,6}\s+(.*)$/)
            if (m) { anchor = m[1].toLowerCase().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').slice(0, 64); break }
          }
        } catch {}
        const start = Math.max(0, pos - 40)
        const end = Math.min(doc.text.length, pos + q.length + 40)
        const snippet = doc.text.slice(start, end).replace(/\n/g, ' ')
        hits.push({ key: doc.key, label: doc.label, anchor, snippet })
      }
    }
    return hits.slice(0, 8)
  }, [search, index])

  // Removed "Open API Reference" button per request

  // Intercept clicks on /docs/... links to switch tabs instead of navigating
  function handleDocsLinkClick(e: React.MouseEvent<HTMLDivElement>) {
    try {
      const target = e.target as HTMLElement
      const a = target?.closest('a') as HTMLAnchorElement | null
      if (!a) return
      const href = a.getAttribute('href') || ''
      const url = new URL(href, window.location.origin)
      if (url.origin === window.location.origin && url.pathname.startsWith('/docs/')) {
        const tab = tabs.find(t => t.src === url.pathname)
        if (tab) {
          e.preventDefault()
          setActive(tab.key)
          const anchor = (url.hash || '').replace(/^#/, '')
          if (anchor) {
            setTimeout(() => {
              try {
                const el = document.getElementById(anchor)
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
              } catch {}
            }, 50)
          }
        }
      }
    } catch {}
  }

  return (
    <ProtectedRoute>
      <Layout>
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Gateway Documentation</h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Guides and field references for configuring and operating the Doorman gateway
              </p>
            </div>
          </div>

          {/* Search bar under title, above tabs */}
          <div className="relative">
            <div className="flex items-center rounded-md border border-gray-200 dark:border-white/10 bg-white dark:bg-dark-surface px-3 py-2 w-full max-w-2xl">
              <svg className="h-4 w-4 text-gray-400 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-4.35-4.35"/><circle cx="11" cy="11" r="7"/></svg>
              <input
                type="search"
                placeholder="Search docs..."
                className="bg-transparent flex-1 text-sm outline-none placeholder:text-gray-400 dark:placeholder:text-white/50"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {search.trim().length >= 2 && results.length > 0 && (
              <div className="absolute z-20 mt-2 w-full max-w-2xl rounded-md border border-gray-200 dark:border-white/10 bg-white dark:bg-dark-surface shadow-lg">
                <div className="max-h-[300px] overflow-auto divide-y divide-gray-100 dark:divide-white/10">
                  {results.map((r, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setActive(r.key as any)
                        setTimeout(() => { if (r.anchor) { try { window.location.hash = r.anchor } catch {} } }, 50)
                        setSearch('')
                      }}
                      className="w-full text-left px-3 py-2 hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <div className="text-sm font-medium text-gray-900 dark:text-white">{r.label}</div>
                      <div className="text-xs text-gray-500 dark:text-white/70 truncate">{r.snippet}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div>
            <div role="tablist" aria-label="Documentation sections" className="-mb-px flex gap-2 overflow-x-auto no-scrollbar border-b border-gray-200 dark:border-white/10">
              {tabs.map(t => {
                const isActive = active === t.key
                return (
                  <button
                    role="tab"
                    aria-selected={isActive}
                    key={t.key}
                    onClick={() => setActive(t.key)}
                    className={
                      'relative px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:rounded-md ' +
                      (isActive
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-gray-600 dark:text-white/70 hover:text-gray-900 dark:hover:text-white')
                    }
                  >
                    <span>{t.label}</span>
                    <span className={
                      'absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-all ' +
                      (isActive ? 'bg-blue-600 dark:bg-blue-400' : 'bg-transparent')
                    } />
                  </button>
                )
              })}
            </div>

            <div className="bg-white dark:bg-dark-surface rounded-lg shadow-sm border border-gray-200 dark:border-white/[0.08] overflow-hidden" onClick={handleDocsLinkClick}>
              {tabs.map(t => (
                <div key={t.key} style={{ display: active === t.key ? 'block' : 'none' }}>
                  {t.type === 'md' ? (
                    <div className="p-5" style={{ minHeight: '600px' }}>
                      <MarkdownViewer src={t.src} searchTerm={search} />
                    </div>
                  ) : t.type === 'html' ? (
                    <div className="p-5" style={{ minHeight: '600px' }}>
                      <HtmlViewer src={t.src} />
                    </div>
                  ) : (
                    <div className="p-0" style={{ minHeight: '600px' }}>
                      <iframe title="OpenAPI Docs" src={t.src as any} className="w-full" style={{ minHeight: 'calc(100vh - 260px)', border: 0 }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Info panel removed per request */}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
