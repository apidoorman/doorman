'use client'

import React, { useState, useEffect } from 'react'
import InfoTooltip from '@/components/InfoTooltip'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'

interface API {
  api_version: React.ReactNode
  api_type: React.ReactNode
  api_description: React.ReactNode
  api_servers?: string[]
  api_id: React.ReactNode
  api_name: React.ReactNode
  id: string
  name: string
  version: string
  description: string
  status: string
  endpoints: number
  lastUpdated: string
}

const APIsPage = () => {
  const router = useRouter()
  const [apis, setApis] = useState<API[]>([])
  const [allApis, setAllApis] = useState<API[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('name')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)
  const [ignorePagingAllCache, setIgnorePagingAllCache] = useState<API[] | null>(null)
  const [backendIgnoresPaging, setBackendIgnoresPaging] = useState(false)

  useEffect(() => {
    fetchApis()
  }, [page, pageSize])

  const fetchApis = async () => {
    try {
      setLoading(true)
      setError(null)
      let fetched: any[] = []
      let raw: any = null
      try {
        const data = await getJson<any>(`${SERVER_URL}/platform/api/all?page=${page}&page_size=${pageSize}`)
        raw = data
        fetched = Array.isArray(data) ? data : (data.apis || data.response?.apis || [])
      } catch {
        fetched = []
      }

      let display: any[] = fetched
      let next = false
      let ignores = false
      if (Array.isArray(fetched) && fetched.length > pageSize) {
        ignores = true
        const total = fetched.length
        const start = (page - 1) * pageSize
        const end = start + pageSize
        display = fetched.slice(start, end)
        next = end < total
        setIgnorePagingAllCache(fetched as any)
      } else if (Array.isArray(fetched)) {
        const hn = (raw?.meta?.has_next ?? raw?.has_next ?? raw?.response?.has_next)
        next = typeof hn === 'boolean' ? hn : fetched.length === pageSize
        setIgnorePagingAllCache(null)
      }
      const seen = new Set<string>()
      const unique = display.filter((a: any) => {
        const id = String(a.api_id || `${a.api_name}/${a.api_version}`)
        if (seen.has(id)) return false
        seen.add(id)
        return true
      })
      unique.sort((a: any, b: any) => String(a.api_name).localeCompare(String(b.api_name)) || String(a.api_version).localeCompare(String(b.api_version)))
      setAllApis(unique)
      setApis(unique)
      setHasNext(next)
      setBackendIgnoresPaging(ignores)
    } catch (err) {
      setError('Failed to load APIs. Please try again later.')
      setApis([])
      setAllApis([])
      setHasNext(false)
    } finally {
      setLoading(false)
    }
  }

  const changePage = (p: number) => {
    if (backendIgnoresPaging && ignorePagingAllCache) {
      const start = (p - 1) * pageSize
      const end = start + pageSize
      const slice = ignorePagingAllCache.slice(start, end)
      setApis(slice as any)
      setPage(p)
      setHasNext(end < ignorePagingAllCache.length)
    } else {
      setPage(p)
    }
  }

  const changePageSize = (s: number) => {
    setPageSize(s)
    setPage(1)
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchTerm.trim()) {
      setApis(allApis)
      return
    }

    const filteredApis = allApis.filter(api =>
      (api.api_name as string)?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (api.api_version as string)?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (api.api_type as string)?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ((api.api_servers || []).join(',').toLowerCase().includes(searchTerm.toLowerCase())) ||
      (api.api_description as string)?.toLowerCase().includes(searchTerm.toLowerCase())
    )
    setApis(filteredApis)
  }

  const handleSort = (sortField: string) => {
    setSortBy(sortField)
    const sortedApis = [...apis].sort((a, b) => {
      if (sortField === 'api_name') {
        return (a.api_name as string).localeCompare(b.api_name as string)
      } else if (sortField === 'api_version') {
        return (a.api_version as string).localeCompare(b.api_version as string)
      } else if (sortField === 'api_type') {
        return (a.api_type as string).localeCompare(b.api_type as string)
      }
      return 0
    })
    setApis(sortedApis)
  }

  const handleApiClick = (api: API) => {
    sessionStorage.setItem('selectedApi', JSON.stringify(api))
    router.push(`/apis/${api.api_id}`)
  }

  const handleViewEndpoints = (e: React.MouseEvent, api: API) => {
    e.stopPropagation()
    sessionStorage.setItem('selectedApi', JSON.stringify(api))
    router.push(`/apis/${api.api_id}/endpoints`)
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">APIs</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage and monitor your API endpoints
            </p>
          </div>
          <Link href="/apis/add" className="btn btn-primary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add API
          </Link>
        </div>

        <div className="card">
          <div className="flex flex-col sm:flex-row gap-4">
            <form onSubmit={handleSearch} className="flex-1">
              <div className="relative">
                <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Search APIs by name, version, type, or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>

            <div className="flex gap-2">
              <button
                onClick={() => handleSort('api_name')}
                className={`btn ${sortBy === 'api_name' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Name
              </button>
              <button
                onClick={() => handleSort('api_version')}
                className={`btn ${sortBy === 'api_version' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Version
              </button>
              <button
                onClick={() => handleSort('api_type')}
                className={`btn ${sortBy === 'api_type' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Type
              </button>
            </div>
          </div>
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
          <div className="card">
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="spinner mx-auto mb-4"></div>
                <p className="text-gray-600 dark:text-gray-400">Loading APIs...</p>
              </div>
            </div>
          </div>
        ) : (
          /* APIs Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Servers</th>
                    <th>Description</th>
                    <th>Type</th>
                    <th className="w-56">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {apis.map((api, index) => (
                    <tr
                      key={String(api.api_id) || `${api.api_name}-${api.api_version}-${index}`}
                      onClick={() => handleApiClick(api)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-8 w-8 rounded-lg bg-primary-100 dark:bg-primary-900/20 flex items-center justify-center mr-3">
                            <svg className="h-4 w-4 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                          </div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-900 dark:text-white">{api.api_name}</p>
                            {(((api as any).api_ip_mode || 'allow_all') === 'whitelist') && (
                              <span className="badge badge-secondary">IP Whitelist</span>
                            )}
                            {Array.isArray((api as any).api_ip_blacklist) && (api as any).api_ip_blacklist.length > 0 && (
                              <span className="badge badge-error">Blacklist</span>
                            )}
                            {((api as any).api_public ?? false) && (
                              <span className="badge badge-warning flex items-center gap-1" title="This API is public">
                                Public
                                <InfoTooltip text="Anyone can call this API; auth, subscription, and group checks are skipped." />
                              </span>
                            )}
                            {!((api as any).api_public ?? false) && ((api as any).api_auth_required === false) && (
                              <span className="badge badge-secondary flex items-center gap-1" title="No authentication required">
                                No Auth
                                <InfoTooltip text="Unauthenticated access is allowed. Subscription and group checks do not apply without auth." />
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-primary">{api.api_version}</span>
                      </td>
                      <td>
                        {Array.isArray((api as any).api_servers) && (api as any).api_servers.length > 0 ? (
                          <div className="text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate">
                            {(api as any).api_servers.slice(0, 3).join(', ')}
                            {(api as any).api_servers.length > 3 && ' …'}
                          </div>
                        ) : (
                          <span className="text-gray-500 dark:text-gray-400 text-sm">None</span>
                        )}
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {api.api_description}
                        </p>
                      </td>
                      <td>
                        <span className={`badge ${
                          (api.api_type as string)?.toLowerCase() === 'rest' ? 'badge-success' :
                          (api.api_type as string)?.toLowerCase() === 'graphql' ? 'badge-warning' :
                          (api.api_type as string)?.toLowerCase() === 'grpc' ? 'badge-error' :
                          'badge-gray'
                        }`}>
                          {api.api_type}
                        </span>
                      </td>
                      <td className="whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={(e) => handleViewEndpoints(e, api)}
                            title="View endpoints for this API"
                          >
                            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                            </svg>
                            View Endpoints
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={(e) => { e.stopPropagation(); handleApiClick(api); }}
                            title="Open API details"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
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
              onPageChange={changePage}
              onPageSizeChange={changePageSize}
              hasNext={hasNext}
            />

            {apis.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No APIs found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Get started by creating your first API.'}
                </p>
                <Link href="/apis/add" className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add API
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default APIsPage
