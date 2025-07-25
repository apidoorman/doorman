'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

interface API {
  api_version: React.ReactNode
  api_type: React.ReactNode
  api_description: React.ReactNode
  api_path: React.ReactNode
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

  useEffect(() => {
    fetchApis()
  }, [])

  const fetchApis = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`http://localhost:3002/platform/api/all`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      if (!response.ok) {
        throw new Error('Failed to load APIs')
      }
      const data = await response.json()
      const apiList = Array.isArray(data) ? data : (data.apis || data.response?.apis || [])
      setAllApis(apiList)
      setApis(apiList)
    } catch (err) {
      setError('Failed to load APIs. Please try again later.')
      setApis([])
      setAllApis([])
    } finally {
      setLoading(false)
    }
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
      (api.api_path as string)?.toLowerCase().includes(searchTerm.toLowerCase()) ||
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

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
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
                    <th>Path</th>
                    <th>Description</th>
                    <th>Type</th>
                    <th></th>
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
                          <div>
                            <p className="font-medium text-gray-900 dark:text-white">{api.api_name}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-primary">{api.api_version}</span>
                      </td>
                      <td>
                        <code className="text-sm bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
                          {api.api_path}
                        </code>
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

            {/* Empty State */}
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
