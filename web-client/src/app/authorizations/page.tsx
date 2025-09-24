'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { useAuth } from '@/contexts/AuthContext'

interface User {
  username: string
  email: string
  active: boolean
  created_at: string
  last_login?: string
  roles?: string[]
}

const AuthorizationsPage = () => {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [allUsers, setAllUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [hasNext, setHasNext] = useState(false)
  const { user: currentUser } = useAuth()

  useEffect(() => {
    fetchUsers()
  }, [page, pageSize])

  const fetchUsers = async () => {
    try {
      setLoading(true)
      setError(null)
      const { fetchJson } = await import('@/utils/http')
      const data: any = await fetchJson(`${SERVER_URL}/platform/user/all?page=${page}&page_size=${pageSize}`)
      let userList = Array.isArray(data) ? data : (data.users || data.response?.users || [])
      // Ensure the active user is first in the list
      if (currentUser?.username) {
        userList = [...userList]
        const idx = userList.findIndex(u => u.username === currentUser.username)
        if (idx > 0) {
          const [me] = userList.splice(idx, 1)
          userList.unshift(me)
        }
      }
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

  const handleManageSubscriptions = (user: User) => {
    router.push(`/authorizations/${user.username}`)
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Subscriptions</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Grant and revoke API access by managing user subscriptions.
            </p>
          </div>
        </div>

        <div className="card">
          <form onSubmit={handleSearch} className="flex-1">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                className="search-input"
                placeholder="Search for a user by username, email, or role..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </form>
        </div>

        {error && (
          <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
            <p className="text-sm text-error-700 dark:text-error-300">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="card">
            <div className="flex items-center justify-center py-12">
              <div className="spinner mx-auto mb-4"></div>
              <p className="text-gray-600 dark:text-gray-400">Loading users...</p>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => {
                    const isMe = currentUser?.username === user.username
                    return (
                    <tr 
                      key={user.username}
                      onClick={() => handleManageSubscriptions(user)}
                      className={`cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors ${isMe ? 'bg-primary-50/60 dark:bg-primary-900/20' : ''}`}
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-medium">
                            {user.username.charAt(0).toUpperCase()}
                          </div>
                          <div className="ml-3">
                            <p className="font-medium text-gray-900 dark:text-white">
                              {user.username}
                              {isMe && (
                                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-700 dark:bg-primary-800 dark:text-primary-200">
                                  You
                                </span>
                              )}
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
                        <button className="btn btn-ghost btn-sm">
                          Manage Subscriptions
                          <svg className="h-4 w-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  )})}
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
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No users found</h3>
                <p className="text-gray-600 dark:text-gray-400">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Create a user first to manage their authorizations.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default AuthorizationsPage
