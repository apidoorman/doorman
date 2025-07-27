'use client'

import React, { useState, useEffect } from 'react'
import Layout from '@/components/Layout'

interface ApiKey {
  id: string
  name: string
  key: string
  created: string
  lastUsed: string
  status: 'active' | 'revoked'
}

interface RateLimit {
  id: string
  path: string
  limit: number
  window: string
  status: 'active' | 'disabled'
}

interface IpWhitelist {
  id: string
  ip: string
  description: string
  created: string
  status: 'active' | 'disabled'
}

interface SecurityPolicy {
  id: string
  name: string
  type: 'jwt' | 'oauth2' | 'api-key' | 'ip-whitelist'
  status: 'active' | 'disabled'
  createdAt: string
}

const SecurityPage = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('api-keys')
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [rateLimits, setRateLimits] = useState<RateLimit[]>([])
  const [ipWhitelist, setIpWhitelist] = useState<IpWhitelist[]>([])
  const [securityPolicies, setSecurityPolicies] = useState<SecurityPolicy[]>([])

  useEffect(() => {
    fetchSecurityData()
  }, [])

  const fetchSecurityData = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Mock data for demonstration
      setApiKeys([
        { id: '1', name: 'Production API Key', key: 'sk_prod_123456789', created: '2024-01-15', lastUsed: '2024-01-20', status: 'active' },
        { id: '2', name: 'Development API Key', key: 'sk_dev_987654321', created: '2024-01-10', lastUsed: '2024-01-19', status: 'active' }
      ])
      
      setRateLimits([
        { id: '1', path: '/api/v1/*', limit: 1000, window: '1 hour', status: 'active' },
        { id: '2', path: '/api/v1/auth/*', limit: 100, window: '1 hour', status: 'active' }
      ])
      
      setIpWhitelist([
        { id: '1', ip: '192.168.1.100', description: 'Office Network', created: '2024-01-15', status: 'active' },
        { id: '2', ip: '10.0.0.50', description: 'VPN Server', created: '2024-01-10', status: 'active' }
      ])
      
      setSecurityPolicies([
        { id: '1', name: 'JWT Authentication', type: 'jwt', status: 'active', createdAt: '2024-01-15' },
        { id: '2', name: 'API Key Authentication', type: 'api-key', status: 'active', createdAt: '2024-01-10' }
      ])
    } catch (err) {
      setError('Failed to load security data. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateApiKey = async () => {
    try {
      setSuccess('API key created successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError('Failed to create API key. Please try again.')
    }
  }

  const handleRevokeApiKey = async (keyId: string) => {
    try {
      setApiKeys(prev => prev.map(key => 
        key.id === keyId ? { ...key, status: 'revoked' as const } : key
      ))
      setSuccess('API key revoked successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError('Failed to revoke API key. Please try again.')
    }
  }

  const handleAddRateLimit = async () => {
    try {
      setSuccess('Rate limit added successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError('Failed to add rate limit. Please try again.')
    }
  }

  const handleAddIpWhitelist = async () => {
    try {
      setSuccess('IP address added to whitelist successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError('Failed to add IP to whitelist. Please try again.')
    }
  }

  const handleCreateSecurityPolicy = async () => {
    try {
      setSuccess('Security policy created successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError('Failed to create security policy. Please try again.')
    }
  }

  const tabs = [
    { id: 'api-keys', label: 'API Keys', icon: '🔑' },
    { id: 'rate-limits', label: 'Rate Limits', icon: '⏱️' },
    { id: 'ip-whitelist', label: 'IP Whitelist', icon: '🌐' },
    { id: 'policies', label: 'Security Policies', icon: '🛡️' }
  ]

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1 className="page-title">Security</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage API keys, rate limits, and security policies
            </p>
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

        {/* Loading State */}
        {loading ? (
          <div className="card">
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="spinner mx-auto mb-4"></div>
                <p className="text-gray-600 dark:text-gray-400">Loading security data...</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="card">
              <div className="border-b border-gray-200 dark:border-gray-700">
                <nav className="-mb-px flex space-x-8">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`py-2 px-1 border-b-2 font-medium text-sm ${
                        activeTab === tab.id
                          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                      }`}
                    >
                      <span className="mr-2">{tab.icon}</span>
                      {tab.label}
                    </button>
                  ))}
                </nav>
              </div>

              <div className="p-6">
                {/* API Keys Tab */}
                {activeTab === 'api-keys' && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">API Keys</h3>
                      <button onClick={handleCreateApiKey} className="btn btn-primary">
                        <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Create API Key
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Key</th>
                            <th>Created</th>
                            <th>Last Used</th>
                            <th>Status</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {apiKeys.map((key) => (
                            <tr key={key.id} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors">
                              <td>
                                <p className="font-medium text-gray-900 dark:text-white">{key.name}</p>
                              </td>
                              <td>
                                <code className="text-sm bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded font-mono">
                                  {key.key}
                                </code>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{key.created}</p>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{key.lastUsed}</p>
                              </td>
                              <td>
                                <span className={`badge ${key.status === 'active' ? 'badge-success' : 'badge-error'}`}>
                                  {key.status}
                                </span>
                              </td>
                              <td>
                                {key.status === 'active' && (
                                  <button
                                    onClick={() => handleRevokeApiKey(key.id)}
                                    className="btn btn-ghost btn-sm text-error-600 hover:text-error-700"
                                  >
                                    Revoke
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Rate Limits Tab */}
                {activeTab === 'rate-limits' && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">Rate Limits</h3>
                      <button onClick={handleAddRateLimit} className="btn btn-primary">
                        <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Add Rate Limit
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Path</th>
                            <th>Limit</th>
                            <th>Window</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rateLimits.map((limit) => (
                            <tr key={limit.id} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors">
                              <td>
                                <p className="font-medium text-gray-900 dark:text-white">{limit.path}</p>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{limit.limit}</p>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{limit.window}</p>
                              </td>
                              <td>
                                <span className={`badge ${limit.status === 'active' ? 'badge-success' : 'badge-gray'}`}>
                                  {limit.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* IP Whitelist Tab */}
                {activeTab === 'ip-whitelist' && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">IP Whitelist</h3>
                      <button onClick={handleAddIpWhitelist} className="btn btn-primary">
                        <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Add IP Address
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>IP Address</th>
                            <th>Description</th>
                            <th>Created</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ipWhitelist.map((ip) => (
                            <tr key={ip.id} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors">
                              <td>
                                <p className="font-medium text-gray-900 dark:text-white">{ip.ip}</p>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{ip.description}</p>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{ip.created}</p>
                              </td>
                              <td>
                                <span className={`badge ${ip.status === 'active' ? 'badge-success' : 'badge-gray'}`}>
                                  {ip.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Security Policies Tab */}
                {activeTab === 'policies' && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white">Security Policies</h3>
                      <button onClick={handleCreateSecurityPolicy} className="btn btn-primary">
                        <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Create Policy
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Created</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {securityPolicies.map((policy) => (
                            <tr key={policy.id} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover transition-colors">
                              <td>
                                <p className="font-medium text-gray-900 dark:text-white">{policy.name}</p>
                              </td>
                              <td>
                                <span className="badge badge-primary">{policy.type}</span>
                              </td>
                              <td>
                                <p className="text-sm text-gray-600 dark:text-gray-400">{policy.createdAt}</p>
                              </td>
                              <td>
                                <span className={`badge ${policy.status === 'active' ? 'badge-success' : 'badge-gray'}`}>
                                  {policy.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}

export default SecurityPage