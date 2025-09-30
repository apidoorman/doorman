'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'

interface CreditDefItem {
  api_credit_group: string
  api_key_header: string
  api_key_present: boolean
  credit_tiers: Array<{ tier_name: string; credits: number; input_limit: number; output_limit: number; reset_frequency: string }>
}

export default function CreditDefsPage() {
  const router = useRouter()
  const [items, setItems] = useState<CreditDefItem[]>([])
  const [allItems, setAllItems] = useState<CreditDefItem[]>([])
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
      const res = await getJson<any>(`${SERVER_URL}/platform/credit/defs?page=${page}&page_size=${pageSize}`)
      const list = Array.isArray(res) ? res : (res.items || res.response?.items || [])
      setItems(list)
      setAllItems(list)
      setHasNext(list.length === pageSize)
    } catch (e: any) {
      setError(e?.message || 'Failed to load credit definitions')
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
      it.api_credit_group.toLowerCase().includes(s) ||
      (it.api_key_header || '').toLowerCase().includes(s) ||
      (it.credit_tiers || []).some(t => t.tier_name.toLowerCase().includes(s))
    )))
  }

  return (
    <ProtectedRoute requiredPermission="manage_credits">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Credit Definitions</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Define API credit groups and tiers</p>
            </div>
            <div className="flex gap-2">
              <Link href="/credits" className="btn btn-secondary">
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                Back to Credits
              </Link>
              <Link href="/credit-defs/add" className="btn btn-primary">
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Credit Definition
              </Link>
            </div>
          </div>

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

          {loading ? (
            <div className="card"><div className="flex items-center justify-center py-12"><div className="text-center"><div className="spinner mx-auto mb-4"></div><p className="text-gray-600 dark:text-gray-400">Loading credit definitions...</p></div></div></div>
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
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it) => (
                      <tr
                        key={it.api_credit_group}
                        onClick={() => router.push(`/credit-defs/${encodeURIComponent(it.api_credit_group)}`)}
                        className="cursor-pointer"
                      >
                        <td><span className="font-medium">{it.api_credit_group}</span></td>
                        <td><span className="badge badge-gray">{it.api_key_header || '-'}</span></td>
                        <td>
                          {(it.credit_tiers || []).length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {(it.credit_tiers || []).slice(0, 3).map((t, idx) => (
                                <span key={idx} className="badge badge-primary">{t.tier_name}</span>
                              ))}
                              {(it.credit_tiers || []).length > 3 && <span className="text-xs text-gray-500">+{(it.credit_tiers || []).length - 3}</span>}
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
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No credit definitions</h3>
                  <p className="text-gray-600 dark:text-gray-400 mb-4">Create a credit definition to get started.</p>
                  <Link href="/credit-defs/add" className="btn btn-primary">Add Credit Definition</Link>
                </div>
              )}
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
