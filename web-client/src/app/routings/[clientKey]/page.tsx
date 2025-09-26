'use client'

import React, { useState, useEffect } from 'react'
import ConfirmModal from '@/components/ConfirmModal'
import Link from 'next/link'
import { useRouter, useParams } from 'next/navigation'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { fetchJson } from '@/utils/http'
import { SERVER_URL } from '@/utils/config'

interface Routing {
  routing_name: string
  routing_servers: string[]
  routing_description: string
  client_key: string
  server_index?: number
}

interface UpdateRoutingData {
  routing_name?: string
  routing_servers?: string[]
  routing_description?: string
  server_index?: number
}

const RoutingDetailPage = () => {
  const router = useRouter()
  const params = useParams()
  const clientKey = params.clientKey as string
  const [routing, setRouting] = useState<Routing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editData, setEditData] = useState<UpdateRoutingData>({})
  const [newServer, setNewServer] = useState('')
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const routingData = sessionStorage.getItem('selectedRouting')
    if (routingData) {
      try {
        const parsedRouting = JSON.parse(routingData)
        setRouting(parsedRouting)
        setEditData({
          routing_name: parsedRouting.routing_name,
          routing_servers: [...parsedRouting.routing_servers],
          routing_description: parsedRouting.routing_description,
          server_index: parsedRouting.server_index || 0
        })
        setLoading(false)
      } catch (err) {
        setError('Failed to load routing data')
        setLoading(false)
      }
    } else {
      setError('No routing data found')
      setLoading(false)
    }
  }, [clientKey])

  const handleBack = () => {
    router.push('/routings')
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancel = () => {
    setIsEditing(false)
    if (routing) {
      setEditData({
        routing_name: routing.routing_name,
        routing_servers: [...routing.routing_servers],
        routing_description: routing.routing_description,
        server_index: routing.server_index || 0
      })
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      
      const response = await fetch(`${SERVER_URL}/platform/routing/${clientKey}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editData)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update routing')
      }

      // Refresh from server to get the latest canonical data
      const refreshedRouting = await fetchJson(`${SERVER_URL}/platform/routing/${encodeURIComponent(clientKey)}`)
      setRouting(refreshedRouting)
      sessionStorage.setItem('selectedRouting', JSON.stringify(refreshedRouting))
      setIsEditing(false)
      setSuccess('Routing updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update routing. Please try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field: keyof UpdateRoutingData, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }))
  }

  const handleServerChange = (index: number, value: string) => {
    setEditData(prev => ({
      ...prev,
      routing_servers: prev.routing_servers?.map((server, i) => i === index ? value : server) || []
    }))
  }

  const addServer = () => {
    if (newServer.trim() && !editData.routing_servers?.includes(newServer.trim())) {
      setEditData(prev => ({
        ...prev,
        routing_servers: [...(prev.routing_servers || []), newServer.trim()]
      }))
      setNewServer('')
    }
  }

  const removeServer = (index: number) => {
    setEditData(prev => ({
      ...prev,
      routing_servers: prev.routing_servers?.filter((_, i) => i !== index) || []
    }))
  }

  const handleDeleteClick = () => {
    setShowDeleteModal(true)
  }

  const handleDeleteCancel = () => {
    setShowDeleteModal(false)
    setDeleteConfirmation('')
  }

  const handleDeleteConfirm = async () => {
    if (deleteConfirmation !== routing?.routing_name) {
      setError('Routing name does not match')
      return
    }

    try {
      setDeleting(true)
      setError(null)
      
      const { delJson } = await import('@/utils/api')
      await delJson(`${SERVER_URL}/platform/routing/${encodeURIComponent(clientKey)}`)

      router.push('/routings')
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to delete routing. Please try again.')
      }
    } finally {
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="spinner mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading routing details...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error && !routing) {
    return (
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Routing Details</h1>
            </div>
            <button onClick={handleBack} className="btn btn-secondary">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Routings
            </button>
          </div>
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
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">{routing?.routing_name || 'Routing Details'}</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage routing configuration and load balancing
            </p>
          </div>
          <div className="flex gap-2">
            {!isEditing ? (
              <>
                <button onClick={handleEdit} className="btn btn-primary">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit Routing
                </button>
                <button onClick={handleDeleteClick} className="btn btn-error">
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Delete Routing
                </button>
              </>
            ) : (
              <>
                <button onClick={handleSave} disabled={saving} className="btn btn-primary">
                  {saving ? (
                    <div className="flex items-center">
                      <div className="spinner mr-2"></div>
                      Saving...
                    </div>
                  ) : (
                    <>
                      <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Save Changes
                    </>
                  )}
                </button>
                <button onClick={handleCancel} className="btn btn-secondary">
                  Cancel
                </button>
              </>
            )}
            <button onClick={handleBack} className="btn btn-ghost">
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back
            </button>
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <div className="rounded-lg bg-success-50 border border-success-200 p-4 dark:bg-success-900/20 dark:border-success-800">
            <div className="flex">
              <svg className="h-5 w-5 text-success-400 dark:text-success-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="ml-3">
                <p className="text-sm text-success-700 dark:text-success-300">{success}</p>
              </div>
            </div>
          </div>
        )}

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

        {routing && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Information */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Basic Information</h3>
                <FormHelp docHref="/docs/using-fields.html#routing">Update name, description, and fixed server index.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Routing Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editData.routing_name || ''}
                      onChange={(e) => handleInputChange('routing_name', e.target.value)}
                      className="input"
                      placeholder="Enter routing name"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{routing.routing_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Client Key
                  </label>
                  <code className="text-sm bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded font-mono">
                    {routing.client_key}
                  </code>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  {isEditing ? (
                    <textarea
                      value={editData.routing_description || ''}
                      onChange={(e) => handleInputChange('routing_description', e.target.value)}
                      className="input resize-none"
                      rows={3}
                      placeholder="Enter routing description"
                    />
                  ) : (
                    <p className="text-gray-600 dark:text-gray-400">{routing.routing_description || 'No description'}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server Index
                    <InfoTooltip text="Optional fixed index into the server list; leave 0 for default selection." />
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      value={editData.server_index || 0}
                      onChange={(e) => handleInputChange('server_index', parseInt(e.target.value))}
                      className="input"
                      min="0"
                    />
                  ) : (
                    <p className="text-gray-900 dark:text-white">{routing.server_index || 0}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Servers Configuration */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="card-title">Servers Configuration</h3>
                <FormHelp docHref="/docs/using-fields.html#routing">Ordered upstreams used for this client key.</FormHelp>
              </div>
              <div className="p-6 space-y-4">
                {isEditing && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newServer}
                      onChange={(e) => setNewServer(e.target.value)}
                      className="input flex-1"
                      placeholder="Enter server URL"
                      onKeyPress={(e) => e.key === 'Enter' && addServer()}
                    />
                    <button onClick={addServer} className="btn btn-primary">
                      Add
                    </button>
                  </div>
                )}
                
                <div className="space-y-2">
                  {(isEditing ? editData.routing_servers : routing.routing_servers)?.map((server, index) => (
                    <div key={index} className="flex items-center gap-2">
                      {isEditing ? (
                        <input
                          type="text"
                          value={server}
                          onChange={(e) => handleServerChange(index, e.target.value)}
                          className="input flex-1"
                          placeholder="Enter server URL"
                        />
                      ) : (
                        <span className="text-sm font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded flex-1">
                          {server}
                        </span>
                      )}
                      {isEditing && (
                        <button
                          onClick={() => removeServer(index)}
                          className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                {(!isEditing ? routing.routing_servers : editData.routing_servers)?.length === 0 && (
                  <p className="text-gray-500 dark:text-gray-400 text-sm">No servers configured</p>
                )}
              </div>
            </div>
          </div>
        )}

        <ConfirmModal
          open={showDeleteModal}
          title="Delete Routing"
          message={<>
            This action cannot be undone. This will permanently delete the routing "{routing?.routing_name}".
          </>}
          confirmLabel={deleting ? 'Deleting...' : 'Delete Routing'}
          cancelLabel="Cancel"
          onCancel={handleDeleteCancel}
          onConfirm={handleDeleteConfirm}
        />
      </div>
    </Layout>
  )
}

export default RoutingDetailPage 
