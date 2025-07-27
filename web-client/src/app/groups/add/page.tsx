'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

interface CreateGroupData {
  group_name: string
  group_description: string
  api_access: string[]
}

const AddGroupPage = () => {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<CreateGroupData>({
    group_name: '',
    group_description: '',
    api_access: []
  })
  const [newApi, setNewApi] = useState('')

  const handleInputChange = (field: keyof CreateGroupData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const addApi = () => {
    if (newApi.trim() && !formData.api_access.includes(newApi.trim())) {
      setFormData(prev => ({
        ...prev,
        api_access: [...prev.api_access, newApi.trim()]
      }))
      setNewApi('')
    }
  }

  const removeApi = (index: number) => {
    setFormData(prev => ({
      ...prev,
      api_access: prev.api_access.filter((_, i) => i !== index)
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.group_name.trim()) {
      setError('Group name is required')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const response = await fetch('http://localhost:3002/platform/group', {
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
        throw new Error(errorData.detail || 'Failed to create group')
      }

      router.push('/groups')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to create group. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Add Group</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Create a new user group with API access permissions
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
              <label htmlFor="group_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Group Name *
              </label>
              <input
                type="text"
                id="group_name"
                name="group_name"
                className="input"
                placeholder="Enter group name"
                value={formData.group_name}
                onChange={(e) => handleInputChange('group_name', e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div>
              <label htmlFor="group_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="group_description"
                name="group_description"
                rows={4}
                className="input resize-none"
                placeholder="Describe the purpose of this group..."
                value={formData.group_description}
                onChange={(e) => handleInputChange('group_description', e.target.value)}
                disabled={loading}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Optional description of the group's purpose
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Access
              </label>
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="Enter API name to grant access"
                    value={newApi}
                    onChange={(e) => setNewApi(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addApi())}
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={addApi}
                    disabled={loading || !newApi.trim()}
                    className="btn btn-primary"
                  >
                    Add
                  </button>
                </div>
                
                <div className="flex flex-wrap gap-2">
                  {formData.api_access.map((api, index) => (
                    <div key={index} className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{api}</span>
                      <button
                        type="button"
                        onClick={() => removeApi(index)}
                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
                        disabled={loading}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
                
                {formData.api_access.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No APIs assigned yet</p>
                )}
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
                    Creating Group...
                  </div>
                ) : (
                  'Create Group'
                )}
              </button>
              <Link href="/groups" className="btn btn-secondary flex-1">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}

export default AddGroupPage 