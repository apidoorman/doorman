'use client'

import React, { useState, useEffect } from 'react'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson, putJson, delJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuth } from '@/contexts/AuthContext'

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

interface SecuritySettings {
  enable_auto_save: boolean
  auto_save_frequency_seconds: number
  dump_path: string
}

const SecurityPage = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  // Tabs removed; render sections directly
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [rateLimits, setRateLimits] = useState<RateLimit[]>([])
  const [ipWhitelist, setIpWhitelist] = useState<IpWhitelist[]>([])
  const [securityPolicies, setSecurityPolicies] = useState<SecurityPolicy[]>([])
  const [activeTab, setActiveTab] = useState('')
  const tabs: { id: string; label: string; icon: string }[] = []
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settings, setSettings] = useState<SecuritySettings>({
    enable_auto_save: false,
    auto_save_frequency_seconds: 900,
    dump_path: 'generated/memory_dump.bin'
  })
  const [memoryOnly, setMemoryOnly] = useState(false)
  const [restorePath, setRestorePath] = useState('')
  const { permissions } = useAuth()

  useEffect(() => {
    fetchSecurityData()
    fetchSecuritySettings()
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

  const fetchSecuritySettings = async () => {
    try {
      setSettingsLoading(true)
      setError(null)
      const data = await getJson<any>(`${SERVER_URL}/platform/security/settings`)
      setSettings({
        enable_auto_save: !!data.enable_auto_save,
        auto_save_frequency_seconds: Number(data.auto_save_frequency_seconds || 900),
        dump_path: data.dump_path || 'generated/memory_dump.bin'
      })
      setMemoryOnly(!!data.memory_only)
    } catch (err) {
      setError('Failed to load security settings. Please try again later.')
    } finally {
      setSettingsLoading(false)
    }
  }

  const handleSaveSettings = async () => {
    try {
      setSettingsSaving(true)
      setError(null)
      await putJson(`${SERVER_URL}/platform/security/settings`, settings)
      setSuccess('Security settings saved')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSettingsSaving(false)
    }
  }

  const handleDumpNow = async () => {
    try {
      setError(null)
      const data = await postJson<any>(`${SERVER_URL}/platform/memory/dump`, { path: settings.dump_path })
      setSuccess(`Memory dump created at ${data.response?.path || settings.dump_path}`)
      setTimeout(() => setSuccess(null), 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create memory dump')
    }
  }

  const handleRestore = async () => {
    try {
      setError(null)
      const data = await postJson<any>(`${SERVER_URL}/platform/memory/restore`, { path: restorePath || settings.dump_path })
      setSuccess(`Memory restored (created at ${data.response?.created_at || 'unknown'})`)
      setTimeout(() => setSuccess(null), 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restore memory dump')
    }
  }

  const handleClearCaches = async () => {
    try {
      setError(null)
      await delJson<any>(`${SERVER_URL}/api/caches`)
      setSuccess('All gateway caches cleared')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear caches')
    }
  }

  const handleRestartGateway = async () => {
    try {
      setError(null)
      const res = await postJson<any>(`${SERVER_URL}/platform/security/restart`, {})
      setSuccess(res?.message || 'Restart scheduled')
      setTimeout(() => setSuccess(null), 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule restart')
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

  // No tabs for this page; show all sections inline

  return (
    <ProtectedRoute requiredPermission="manage_security">
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="page-title">Security</h1>
              {memoryOnly && (
                <span className="badge badge-gray">Memory Mode</span>
              )}
            </div>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage API keys, rate limits, and security policies
            </p>
          </div>
        </div>

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
                <p className="text-gray-600 dark:text-gray-400">Loading security data...</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="card">
              <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">Memory & Security Settings</h3>
                    {memoryOnly && (
                      <span className="badge badge-gray">Memory Mode</span>
                    )}
                  </div>
                  <FormHelp docHref="/docs/using-fields.html#security">Configure encrypted memory dumps and clear caches safely.</FormHelp>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className={`block text-sm font-medium ${memoryOnly ? 'text-gray-400 dark:text-gray-500' : 'text-gray-700 dark:text-gray-300'}`}>
                      Enable Auto-save
                      <InfoTooltip text="When enabled, Doorman periodically writes an encrypted memory dump to the configured path. Requires MEM_ENCRYPTION_KEY on the server. In memory-only mode this is always on." />
                    </label>
                    <div className={`flex items-center gap-3 ${memoryOnly ? 'opacity-60 cursor-not-allowed' : ''}`}>
                      <input
                        type="checkbox"
                        checked={memoryOnly ? true : settings.enable_auto_save}
                        onChange={(e) => setSettings(s => ({ ...s, enable_auto_save: e.target.checked }))}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        disabled={settingsLoading || settingsSaving || memoryOnly}
                      />
                      <span className={`text-sm ${memoryOnly ? 'text-gray-500 dark:text-gray-500' : 'text-gray-600 dark:text-gray-400'}`}>
                        {memoryOnly ? 'Always on in memory mode' : 'Periodically save encrypted memory dump'}
                      </span>
                    </div>
                    {memoryOnly && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">Auto-save is enforced in memory mode; adjust only the frequency and dump path.</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Auto-save Frequency (seconds)
                      <InfoTooltip text="Minimum 60s. Choose a value that balances RPO vs. IO overhead. Applies only when auto-save is enabled." />
                    </label>
                    <input
                      type="number"
                      min={60}
                      value={settings.auto_save_frequency_seconds}
                      onChange={(e) => setSettings(s => ({ ...s, auto_save_frequency_seconds: Math.max(60, Number(e.target.value || 60)) }))}
                      className="input"
                      placeholder="900"
                      disabled={settingsLoading || settingsSaving}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400">Minimum 60 seconds</p>
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Dump Path
                      <InfoTooltip text="Filesystem path for the encrypted memory dump. Store on an encrypted volume if possible. Example: generated/memory_dump.bin" />
                    </label>
                    <input
                      type="text"
                      value={settings.dump_path}
                      onChange={(e) => setSettings(s => ({ ...s, dump_path: e.target.value }))}
                      className="input"
                      placeholder="generated/memory_dump.bin"
                      disabled={settingsLoading || settingsSaving}
                    />
                  </div>

                  <div className="md:col-span-2 flex gap-3">
                    <button onClick={handleSaveSettings} disabled={settingsSaving || settingsLoading} className="btn btn-primary">
                      {settingsSaving ? (
                        <div className="flex items-center"><div className="spinner mr-2"></div>Saving...</div>
                      ) : 'Save Settings'}
                    </button>
                    <button onClick={handleDumpNow} className="btn btn-secondary">Dump Now</button>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Restore From Path
                      <InfoTooltip text="Points to a previously saved encrypted dump file. Requires MEM_ENCRYPTION_KEY to decrypt and restore." />
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={restorePath}
                        onChange={(e) => setRestorePath(e.target.value)}
                        className="input flex-1"
                        placeholder={settings.dump_path}
                      />
                      <button onClick={handleRestore} className="btn btn-secondary">Restore</button>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Requires MEM_ENCRYPTION_KEY to be configured on server.</p>
                  </div>

                  {(permissions?.manage_gateway || permissions?.manage_security) && (
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Gateway</label>
                      <div className="flex gap-3">
                        <button onClick={handleClearCaches} className="btn btn-secondary">Clear All Caches</button>
                        <button onClick={handleRestartGateway} className="btn btn-danger">Restart Gateway</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
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
                {activeTab === 'settings' && (
                  <div className="space-y-6">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">Memory & Security Settings</h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Enable Auto-save</label>
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={settings.enable_auto_save}
                            onChange={(e) => setSettings(s => ({ ...s, enable_auto_save: e.target.checked }))}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                            disabled={settingsLoading || settingsSaving}
                          />
                          <span className="text-sm text-gray-600 dark:text-gray-400">Periodically save encrypted memory dump</span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Auto-save Frequency (seconds)</label>
                        <input
                          type="number"
                          min={60}
                          value={settings.auto_save_frequency_seconds}
                          onChange={(e) => setSettings(s => ({ ...s, auto_save_frequency_seconds: Math.max(60, Number(e.target.value || 60)) }))}
                          className="input"
                          placeholder="900"
                          disabled={settingsLoading || settingsSaving}
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400">Minimum 60 seconds</p>
                      </div>

                      <div className="space-y-2 md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Dump Path</label>
                        <input
                          type="text"
                          value={settings.dump_path}
                          onChange={(e) => setSettings(s => ({ ...s, dump_path: e.target.value }))}
                          className="input"
                          placeholder="generated/memory_dump.bin"
                          disabled={settingsLoading || settingsSaving}
                        />
                      </div>

                      <div className="md:col-span-2 flex gap-3">
                        <button onClick={handleSaveSettings} disabled={settingsSaving || settingsLoading} className="btn btn-primary">
                          {settingsSaving ? (
                            <div className="flex items-center"><div className="spinner mr-2"></div>Saving...</div>
                          ) : 'Save Settings'}
                        </button>
                        <button onClick={handleDumpNow} className="btn btn-secondary">Dump Now</button>
                      </div>

                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Restore From Path</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={restorePath}
                            onChange={(e) => setRestorePath(e.target.value)}
                            className="input flex-1"
                            placeholder={settings.dump_path}
                          />
                          <button onClick={handleRestore} className="btn btn-secondary">Restore</button>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Requires MEM_ENCRYPTION_KEY to be configured on server.</p>
                      </div>

                      {permissions?.manage_gateway && (
                        <div className="md:col-span-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Gateway</label>
                          <button onClick={handleClearCaches} className="btn btn-secondary">Clear All Caches</button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
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
    </ProtectedRoute>
  )
}

export default SecurityPage
