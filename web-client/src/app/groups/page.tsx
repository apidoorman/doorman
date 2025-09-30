'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson } from '@/utils/api'

interface Group {
  group_name: string
  group_description: string
  api_access?: string[]
}

const GroupsPage = () => {
  const router = useRouter()
  const [groups, setGroups] = useState<Group[]>([])
  const [allGroups, setAllGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('group_name')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)

  useEffect(() => {
    fetchGroups()
  }, [page, pageSize])

  const fetchGroups = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getJson<any>(`${SERVER_URL}/platform/group/all?page=${page}&page_size=${pageSize}`)
      const items: any[] = Array.isArray(data) ? data : (data.groups || data.response?.groups || [])
      const seen = new Set<string>()
      const unique = items.filter((g: any) => {
        const key = String(g.group_name)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      }).sort((a: any, b: any) => String(a.group_name).localeCompare(String(b.group_name)))
      setAllGroups(unique)
      setGroups(unique)
      setHasNext((items || []).length === pageSize)
    } catch (err) {
      setError('Failed to load groups. Please try again later.')
      setGroups([])
      setAllGroups([])
      setHasNext(false)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchTerm.trim()) {
      setGroups(allGroups)
      return
    }

    const filteredGroups = allGroups.filter(group =>
      group.group_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.group_description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.api_access?.some(api => api.toLowerCase().includes(searchTerm.toLowerCase()))
    )
    setGroups(filteredGroups)
  }

  const handleSort = (sortField: string) => {
    setSortBy(sortField)
    const sortedGroups = [...groups].sort((a, b) => {
      if (sortField === 'group_name') {
        return a.group_name.localeCompare(b.group_name)
      } else if (sortField === 'api_access') {
        return (a.api_access?.length || 0) - (b.api_access?.length || 0)
      }
      return 0
    })
    setGroups(sortedGroups)
  }

  const handleGroupClick = (group: Group) => {
    sessionStorage.setItem('selectedGroup', JSON.stringify(group))
    router.push(`/groups/${group.group_name}`)
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Groups</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage user groups and API access permissions
            </p>
          </div>
          <Link href="/groups/add" className="btn btn-primary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Group
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
                  placeholder="Search groups by name, description, or API access..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>

            <div className="flex gap-2">
              <button
                onClick={() => handleSort('group_name')}
                className={`btn ${sortBy === 'group_name' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Name
              </button>
              <button
                onClick={() => handleSort('api_access')}
                className={`btn ${sortBy === 'api_access' ? 'btn-primary' : 'btn-secondary'}`}
              >
                API Access
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
                <p className="text-gray-600 dark:text-gray-400">Loading groups...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Groups Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>API Access</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <tr
                      key={group.group_name}
                      onClick={() => handleGroupClick(group)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center mr-3">
                            <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900 dark:text-white">{group.group_name}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {group.group_description || 'No description'}
                        </p>
                      </td>
                      <td>
                        <span className="badge badge-success">
                          {group.api_access?.length || 0} API{(group.api_access?.length || 0) !== 1 ? 's' : ''}
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

            {groups.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No groups found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Get started by creating your first user group.'}
                </p>
                <Link href="/groups/add" className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Group
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default GroupsPage
