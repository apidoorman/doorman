'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'

interface Routing {
  routing_name: string
  routing_servers: string[]
  routing_description: string
  client_key: string
}

const RoutingsPage = () => {
  const router = useRouter()
  const [routings, setRoutings] = useState<Routing[]>([])
  const [allRoutings, setAllRoutings] = useState<Routing[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('routing_name')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)

  useEffect(() => {
    fetchRoutings()
  }, [page, pageSize])

  const fetchRoutings = async () => {
    try {
      setLoading(true)
      setError(null)
      const { fetchJson } = await import('@/utils/http')
      const data: any = await fetchJson(`${SERVER_URL}/platform/routing/all?page=${page}&page_size=${pageSize}`)
      const routingList = Array.isArray(data) ? data : (data.routings || data.response?.routings || [])
      setAllRoutings(routingList)
      setRoutings(routingList)
      setHasNext((routingList || []).length === pageSize)
    } catch (err) {
      setError('Failed to load routings. Please try again later.')
      setRoutings([])
      setAllRoutings([])
      setHasNext(false)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchTerm.trim()) {
      setRoutings(allRoutings)
      return
    }
    
    const filteredRoutings = allRoutings.filter(routing => 
      routing.routing_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      routing.routing_description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      routing.client_key.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (routing.routing_servers || []).some(server => server.toLowerCase().includes(searchTerm.toLowerCase()))
    )
    setRoutings(filteredRoutings)
  }

  const handleSort = (sortField: string) => {
    setSortBy(sortField)
    const sortedRoutings = [...routings].sort((a, b) => {
      if (sortField === 'routing_name') {
        return a.routing_name.localeCompare(b.routing_name)
      } else if (sortField === 'client_key') {
        return a.client_key.localeCompare(b.client_key)
      } else if (sortField === 'servers') {
        return a.routing_servers.length - b.routing_servers.length
      }
      return 0
    })
    setRoutings(sortedRoutings)
  }

  const handleRoutingClick = (routing: Routing) => {
    sessionStorage.setItem('selectedRouting', JSON.stringify(routing))
    router.push(`/routings/${routing.client_key}`)
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Routings</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage API routing configurations and load balancing
            </p>
          </div>
          <Link href="/routings/add" className="btn btn-primary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Routing
          </Link>
        </div>

        {/* Search and Filters */}
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
                  placeholder="Search routings by name, description, or servers..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>
            
            <div className="flex gap-2">
              <button
                onClick={() => handleSort('routing_name')}
                className={`btn ${sortBy === 'routing_name' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Name
              </button>
              <button
                onClick={() => handleSort('client_key')}
                className={`btn ${sortBy === 'client_key' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Key
              </button>
              <button
                onClick={() => handleSort('servers')}
                className={`btn ${sortBy === 'servers' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Servers
              </button>
            </div>
          </div>
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

        {/* Loading State */}
        {loading ? (
          <div className="card">
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="spinner mx-auto mb-4"></div>
                <p className="text-gray-600 dark:text-gray-400">Loading routings...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Routings Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Client Key</th>
                    <th>Description</th>
                    <th>Servers</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {routings.map((routing) => (
                    <tr 
                      key={routing.client_key}
                      onClick={() => handleRoutingClick(routing)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center mr-3">
                            <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900 dark:text-white">{routing.routing_name}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <code className="text-sm bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded font-mono">
                          {routing.client_key}
                        </code>
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {routing.routing_description || 'No description'}
                        </p>
                      </td>
                      <td>
                        <span className="badge badge-primary">
                          {routing.routing_servers.length} server{routing.routing_servers.length !== 1 ? 's' : ''}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-ghost btn-sm">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
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
              onPageSizeChange={(s) => { setPageSize(s); setPage(1) }}
              hasNext={hasNext}
            />

            {/* Empty State */}
            {routings.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No routings found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Get started by creating your first routing configuration.'}
                </p>
                <Link href="/routings/add" className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Routing
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default RoutingsPage
