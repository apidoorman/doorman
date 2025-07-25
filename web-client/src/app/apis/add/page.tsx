'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Layout from '@/components/Layout'

const AddApiPage = () => {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    api_name: '',
    api_version: '',
    api_type: 'REST',
    api_path: '',
    api_description: '',
    validation_enabled: false
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('http://localhost:3002/platform/api', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        },
        body: JSON.stringify(formData)
      })

      if (response.ok) {
        router.push('/apis')
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to create API')
      }
    } catch (err) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }))
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Add New API</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Create a new API endpoint for your gateway
            </p>
          </div>
          <Link href="/apis" className="btn btn-secondary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to APIs
          </Link>
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="api_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API Name *
                </label>
                <input
                  id="api_name"
                  name="api_name"
                  type="text"
                  required
                  className="input"
                  placeholder="e.g., user-service"
                  value={formData.api_name}
                  onChange={handleChange}
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  A unique identifier for your API
                </p>
              </div>

              <div>
                <label htmlFor="api_version" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Version *
                </label>
                <input
                  id="api_version"
                  name="api_version"
                  type="text"
                  required
                  className="input"
                  placeholder="e.g., v1"
                  value={formData.api_version}
                  onChange={handleChange}
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  API version (e.g., v1, v2, beta)
                </p>
              </div>
            </div>

            <div>
              <label htmlFor="api_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Type *
              </label>
              <select
                id="api_type"
                name="api_type"
                required
                className="input"
                value={formData.api_type}
                onChange={handleChange}
                disabled={loading}
              >
                <option value="REST">REST</option>
                <option value="GraphQL">GraphQL</option>
                <option value="gRPC">gRPC</option>
                <option value="SOAP">SOAP</option>
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                The protocol type for this API
              </p>
            </div>

            <div>
              <label htmlFor="api_path" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Path *
              </label>
              <input
                id="api_path"
                name="api_path"
                type="text"
                required
                className="input"
                placeholder="e.g., https://api.example.com"
                value={formData.api_path}
                onChange={handleChange}
                disabled={loading}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                The base URL or path for your API
              </p>
            </div>

            <div>
              <label htmlFor="api_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="api_description"
                name="api_description"
                rows={4}
                className="input resize-none"
                placeholder="Describe what this API does..."
                value={formData.api_description}
                onChange={handleChange}
                disabled={loading}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Optional description of the API's purpose
              </p>
            </div>

            <div className="flex items-center">
              <input
                id="validation_enabled"
                name="validation_enabled"
                type="checkbox"
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                checked={formData.validation_enabled}
                onChange={handleChange}
                disabled={loading}
              />
              <label htmlFor="validation_enabled" className="ml-2 block text-sm text-gray-700 dark:text-gray-300">
                Enable request validation
              </label>
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
                    Creating API...
                  </div>
                ) : (
                  'Create API'
                )}
              </button>
              <Link href="/apis" className="btn btn-secondary flex-1">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}

export default AddApiPage 