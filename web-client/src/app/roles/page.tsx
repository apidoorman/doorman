'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

interface Role {
  role_name: string
  role_description: string
  manage_users?: boolean
  manage_apis?: boolean
  manage_endpoints?: boolean
  manage_groups?: boolean
  manage_roles?: boolean
  manage_routings?: boolean
  manage_gateway?: boolean
  manage_subscriptions?: boolean
}

const RolesPage = () => {
  const router = useRouter()
  const [roles, setRoles] = useState<Role[]>([])
  const [allRoles, setAllRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('role_name')

  useEffect(() => {
    fetchRoles()
  }, [])

  const fetchRoles = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`http://localhost:3002/platform/role/all?page=1&page_size=10`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      })
      if (!response.ok) {
        throw new Error('Failed to load roles')
      }
      const data = await response.json()
      
      setAllRoles(data.roles)
      setRoles(data.roles)
    } catch (err) {
      setError('Failed to load roles. Please try again later.')
      setRoles([])
      setAllRoles([])
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchTerm.trim()) {
      setRoles(allRoles)
      return
    }
    
    const filteredRoles = allRoles.filter(role => 
      role.role_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      role.role_description?.toLowerCase().includes(searchTerm.toLowerCase())
    )
    setRoles(filteredRoles)
  }

  const handleSort = (sortField: string) => {
    setSortBy(sortField)
    const sortedRoles = [...roles].sort((a, b) => {
      if (sortField === 'role_name') {
        return a.role_name.localeCompare(b.role_name)
      } else if (sortField === 'permissions') {
        const aPerms = Object.values(a).filter(val => typeof val === 'boolean' && val).length
        const bPerms = Object.values(b).filter(val => typeof val === 'boolean' && val).length
        return bPerms - aPerms
      }
      return 0
    })
    setRoles(sortedRoles)
  }

  const handleRoleClick = (role: Role) => {
    sessionStorage.setItem('selectedRole', JSON.stringify(role))
    router.push(`/roles/${role.role_name}`)
  }

  const getPermissionCount = (role: Role) => {
    return Object.values(role).filter(val => typeof val === 'boolean' && val).length
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Roles</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage user roles and permissions
            </p>
          </div>
          <Link href="/roles/add" className="btn btn-primary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Role
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
                  placeholder="Search roles by name or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </form>
            
            <div className="flex gap-2">
              <button
                onClick={() => handleSort('role_name')}
                className={`btn ${sortBy === 'role_name' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Name
              </button>
              <button
                onClick={() => handleSort('permissions')}
                className={`btn ${sortBy === 'permissions' ? 'btn-primary' : 'btn-secondary'}`}
              >
                Permissions
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
                <p className="text-gray-600 dark:text-gray-400">Loading roles...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Roles Table */
          <div className="card">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Permissions</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map((role) => (
                    <tr 
                      key={role.role_name}
                      onClick={() => handleRoleClick(role)}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors"
                    >
                      <td>
                        <div className="flex items-center">
                          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center mr-3">
                            <svg className="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900 dark:text-white">{role.role_name}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <p className="text-sm text-gray-600 dark:text-gray-400 max-w-xs truncate">
                          {role.role_description || 'No description'}
                        </p>
                      </td>
                      <td>
                        <span className="badge badge-warning">
                          {getPermissionCount(role)} permission{getPermissionCount(role) !== 1 ? 's' : ''}
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
            {roles.length === 0 && !loading && (
              <div className="text-center py-12">
                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No roles found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {searchTerm ? 'Try adjusting your search terms.' : 'Get started by creating your first user role.'}
                </p>
                <Link href="/roles/add" className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Role
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}

export default RolesPage