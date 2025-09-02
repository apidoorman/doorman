'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

interface CreateRoutingData {
  routing_name: string
  routing_servers: string[]
  routing_description: string
  client_key?: string
  server_index?: number
}

const AddRoutingPage = () => {
  const router = useRouter()
  const [formData, setFormData] = useState<CreateRoutingData>({
    routing_name: '',
    routing_servers: [],
    routing_description: '',
    server_index: 0
  })
  const [newServer, setNewServer] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInputChange = (field: keyof CreateRoutingData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const addServer = () => {
    if (newServer.trim() && !formData.routing_servers.includes(newServer.trim())) {
      setFormData(prev => ({ ...prev, routing_servers: [...prev.routing_servers, newServer.trim()] }))
      setNewServer('')
    }
  }

  const removeServer = (index: number) => {
    setFormData(prev => ({ ...prev, routing_servers: prev.routing_servers.filter((_, i) => i !== index) }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields
    if (!formData.routing_name || formData.routing_servers.length === 0) {
      setError('Please fill in routing name and add at least one server')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const response = await fetch('http://localhost:3002/platform/routing/', {
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
        throw new Error(errorData.detail || 'Failed to create routing')
      }

      router.push('/routings')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to create routing. Please try again.')
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
            <h1 className="page-title">Add Routing</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Create a new routing configuration for load balancing
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
              <label htmlFor="routing_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Routing Name *
              </label>
              <input
                type="text"
                id="routing_name"
                name="routing_name"
                className="input"
                placeholder="Enter routing name"
                value={formData.routing_name}
                onChange={(e) => handleInputChange('routing_name', e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div>
              <label htmlFor="routing_description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                id="routing_description"
                name="routing_description"
                rows={4}
                className="input resize-none"
                placeholder="Describe the purpose of this routing..."
                value={formData.routing_description}
                onChange={(e) => handleInputChange('routing_description', e.target.value)}
                disabled={loading}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Optional description of the routing configuration
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Servers *
              </label>
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="Enter server URL (e.g., http://localhost:8080)"
                    value={newServer}
                    onChange={(e) => setNewServer(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addServer())}
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={addServer}
                    disabled={loading || !newServer.trim()}
                    className="btn btn-primary"
                  >
                    Add
                  </button>
                </div>
                
                <div className="space-y-2">
                  {formData.routing_servers.map((server, index) => (
                    <div key={index} className="flex items-center justify-between bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded">
                      <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{server}</span>
                      <button
                        type="button"
                        onClick={() => removeServer(index)}
                        className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
                        disabled={loading}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
                
                {formData.routing_servers.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No servers added yet</p>
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
                    Creating Routing...
                  </div>
                ) : (
                  'Create Routing'
                )}
              </button>
              <Link href="/routings" className="btn btn-secondary flex-1">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
}

export default AddRoutingPage 