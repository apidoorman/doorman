'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'

interface TokenDefItem {
  api_token_group: string
  api_key_header: string
  api_key_present: boolean
  token_tiers: Array<{ tier_name: string; tokens: number; input_limit: number; output_limit: number; reset_frequency: string }>
}

export default function TokenDefsPage() {
  const [items, setItems] = useState<TokenDefItem[]>([])
  const [allItems, setAllItems] = useState<TokenDefItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)

  useEffect(() => { fetchDefs() }, [page, pageSize])

  const fetchDefs = async () => {
    try {
      setLoading(true); setError(null)
      const res = await getJson<any>(`${SERVER_URL}/platform/token/defs?page=${page}&page_size=${pageSize}`)
      const list = Array.isArray(res) ? res : (res.items || res.response?.items || [])
      setItems(list)
      setAllItems(list)
      setHasNext(list.length === pageSize)
    } catch (e: any) {
      setError(e?.message || 'Failed to load token definitions')
      setItems([])
      setAllItems([])
      setHasNext(false)
    } finally {
      setLoading(false)
    }
  }

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!search.trim()) { setItems(allItems); return }
    const s = search.toLowerCase()
    setItems(allItems.filter(it => (
      it.api_token_group.toLowerCase().includes(s) ||
      (it.api_key_header || '').toLowerCase().includes(s) ||
      (it.token_tiers || []).some(t => t.tier_name.toLowerCase().includes(s))
    )))
  }

  return (
    <ProtectedRoute requiredPermission="manage_tokens">
      <Layout>
        <div className="space-y-6">
          {/* Header */}
          <div className="page-header">
            <div>
              <h1 className="page-title">Token Definitions</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Define API token groups and tiers</p>
            </div>
            <Link href="/token-defs/add" className="btn btn-primary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Token Definition
            </Link>
          </div>

          {/* Search */}
          <div className="card">
            <form onSubmit={onSearch} className="flex-1">
              <div className="relative">
                <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input type="text" className="search-input" placeholder="Search by group, header, or tier..." value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
            </form>
          </div>

          {/* Error */}
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

          {/* Loading */}
          {loading ? (
            <div className="card"><div className="flex items-center justify-center py-12"><div className="text-center"><div className="spinner mx-auto mb-4"></div><p className="text-gray-600 dark:text-gray-400">Loading token definitions...</p></div></div></div>
          ) : (
            <div className="card">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Group</th>
                      <th>Header</th>
                      <th>Tiers</th>
                      <th>API Key</th>
                      <th className="w-40">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it) => (
                      <tr key={it.api_token_group}>
                        <td><span className="font-medium">{it.api_token_group}</span></td>
                        <td><span className="badge badge-gray">{it.api_key_header || '-'}</span></td>
                        <td>
                          {(it.token_tiers || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {(it.token_tiers || []).slice(0, 3).map((t, idx) => (
                                <span key={idx} className="badge badge-primary">{t.tier_name}</span>
                              ))}
                              {(it.token_tiers || []).length > 3 && <span className="text-xs text-gray-500">+{(it.token_tiers || []).length - 3}</span>}
                            </div>
                          ) : <span className="text-gray-500 text-sm">None</span>}
                        </td>
                        <td>
                          {it.api_key_present ? (
                            <span className="badge badge-success">Configured</span>
                          ) : (
                            <span className="badge badge-warning">Missing</span>
                          )}
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <Link href={`/token-defs/${encodeURIComponent(it.api_token_group)}`} className="btn btn-secondary btn-sm">
                              Edit
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
                hasNext={hasNext}
              />
              {items.length === 0 && !loading && (
                <div className="text-center py-12">
                  <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                    <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 1.343-3 3 0 2.239 3 5 3 5s3-2.761 3-5c0-1.657-1.343-3-3-3z M12 13a2 2 0 110-4 2 2 0 010 4z" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No token definitions</h3>
                  <p className="text-gray-600 dark:text-gray-400 mb-4">Create a token definition to get started.</p>
                  <Link href="/token-defs/add" className="btn btn-primary">Add Token Definition</Link>
                </div>
              )}
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

