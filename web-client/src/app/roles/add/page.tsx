'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

interface CreateRoleData {
  role_name: string
  role_description: string
  manage_users: boolean
  manage_apis: boolean
  manage_endpoints: boolean
  manage_groups: boolean
  manage_roles: boolean
  manage_routings: boolean
  manage_gateway: boolean
  manage_subscriptions: boolean
  manage_security: boolean
}

const AddRolePage = () => {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<CreateRoleData>({
    role_name: '',
    role_description: '',
    manage_users: false,
    manage_apis: false,
    manage_endpoints: false,
    manage_groups: false,
    manage_roles: false,
    manage_routings: false,
    manage_gateway: false,
    manage_subscriptions: false,
    manage_security: false
  })

  const handleInputChange = (field: keyof CreateRoleData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.role_name.trim()) {
      setError('Role name is required')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const response = await fetch('http://localhost:3002/platform/role', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        },
        body: JSON.stringify(formData)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create role')
      }

      router.push('/roles')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to create role. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const permissions = [
    { key: 'manage_users', label: 'Manage Users', description: 'Create, edit, and delete user accounts' },
    { key: 'manage_apis', label: 'Manage APIs', description: 'Create, edit, and delete API configurations' },
    { key: 'manage_endpoints', label: 'Manage Endpoints', description: 'Configure API endpoints and validations' },
    { key: 'manage_groups', label: 'Manage Groups', description: 'Create, edit, and delete user groups' },
    { key: 'manage_roles', label: 'Manage Roles', description: 'Create, edit, and delete user roles' },
    { key: 'manage_routings', label: 'Manage Routings', description: 'Configure API routing and load balancing' },
    { key: 'manage_gateway', label: 'Manage Gateway', description: 'Configure gateway settings and policies' },
    { key: 'manage_subscriptions', label: 'Manage Subscriptions', description: 'Manage API subscriptions and billing' },
    { key: 'manage_security', label: 'Manage Security', description: 'Manage security settings and memory dump policy' }
  ]

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Add Role</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Create a new user role with specific permissions
            </p>
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

        {/* Form */}
        <div className="card max-w-2xl">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="role_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Role Name *
              </label>
              <input
                type="text"
                id="role_name"
                name="role_name"
                className="input"
                placeholder="Enter role name"
                value={formData.role_name}
                onChange={(e) => handleInputChange('role_name', e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div>
              <label htmlFor="role_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="role_description"
                name="role_description"
                rows={4}
                className="input resize-none"
                placeholder="Describe the purpose of this role..."
                value={formData.role_description}
                onChange={(e) => handleInputChange('role_description', e.target.value)}
                disabled={loading}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Optional description of the role's purpose
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
                Permissions
              </label>
              <div className="space-y-3">
                {permissions.map((permission) => (
                  <div key={permission.key} className="flex items-start space-x-3">
                    <input
                      type="checkbox"
                      id={permission.key}
                      name={permission.key}
                      checked={formData[permission.key as keyof CreateRoleData] as boolean}
                      onChange={(e) => handleInputChange(permission.key as keyof CreateRoleData, e.target.checked)}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded mt-1"
                      disabled={loading}
                    />
                    <div className="flex-1">
                      <label htmlFor={permission.key} className="block text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer">
                        {permission.label}
                      </label>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {permission.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-4 pt-6 border-t border-gray-200 dark:border-gray-700">
              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary flex-1"
              >
                {loading ? (
                  <div className="flex items-center justify-center">
                    <div className="spinner mr-2"></div>
                    Creating Role...
                  </div>
                ) : (
                  'Create Role'
                )}
              </button>
              <Link href="/roles" className="btn btn-secondary flex-1">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}

export default AddRolePage 
