'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'

interface User {
  username: string
  email: string
  active: boolean
  created_at: string
  last_login?: string
  roles?: string[]
}

const UsersPage = () => {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('username')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)

  useEffect(() => {
    fetchUsers()
  }, [page, pageSize])

  const fetchUsers = async () => {
    try {
      setLoading(true)
      setError(null)
      const { fetchJson } = await import('@/utils/http')
      const data: any = await fetchJson(`${SERVER_URL}/platform/user/all?page=${page}&page_size=${pageSize}`)
      const userList = Array.isArray(data) ? data : (data.users || data.response?.users || [])
      setAllUsers(userList)
      setUsers(userList)
      setHasNext((userList || []).length === pageSize)
    } catch (err) {
      setError('Failed to load users. Please try again later.')
      setUsers([])
      setAllUsers([])
      setHasNext(false)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchTerm.trim()) {
      setUsers(allUsers)
      return
    }

    const filteredUsers = allUsers.filter(user =>
      user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (user.roles || []).some(role => role.toLowerCase().includes(searchTerm.toLowerCase()))
    )
    setUsers(filteredUsers)
  }

  const handleSort = (sortField: string) => {
    setSortBy(sortField)
    const sortedUsers = [...users].sort((a, b) => {
      if (sortField === 'username') {
        return a.username.localeCompare(b.username)
      } else if (sortField === 'email') {
        return a.email.localeCompare(b.email)
      } else if (sortField === 'status') {
        return a.active === b.active ? 0 : a.active ? -1 : 1
      }
      return 0
    })
    setUsers(sortedUsers)
  }

  const handleUserClick = (user: User) => {
    sessionStorage.setItem('selectedUser', JSON.stringify(user))
    router.push(`/users/${user.username}`)
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Users</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage user accounts and permissions
            </p>
          </div>
          <Link href="/users/add" className="btn btn-primary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add User
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
                  placeholder="Search users by username, email, or role..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>

            <div className="flex gap-2">
              <button
                onClick={() => handleSort('username')}
                className={`btn ${sortBy === 'username' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Username
              </button>
              <button
                onClick={() => handleSort('email')}
                className={`btn ${sortBy === 'email' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Email
              </button>
              <button
                onClick={() => handleSort('status')}
                className={`btn ${sortBy === 'status' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Status
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
                <p className="text-gray-600 dark:text-gray-400">Loading users...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Users Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th>Status</th>
                    <th>Last Login</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr
                      key={user.username}
                      onClick={() => handleUserClick(user)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-medium">
                            {user.username.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-3">
                            <p className="font-medium text-gray-900 dark:text-white">
                              {user.username}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <p className="text-sm text-gray-900 dark:text-white">{user.email}</p>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {(user.roles || []).slice(0, 2).map((role, index) => (
                            <span key={index} className="badge badge-primary text-xs">
                              {role}
                            </span>
                          ))}
                          {(user.roles || []).length > 2 && (
                            <span className="badge badge-gray text-xs">
                              +{(user.roles || []).length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${user.active ? 'badge-success' : 'badge-error'}`}>
                          {user.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {formatDate(user.last_login || '')}
                        </p>
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

            {users.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No users found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Get started by creating your first user account.'}
                </p>
                <Link href="/users/add" className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add User
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default UsersPage
