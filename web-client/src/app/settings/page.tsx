'use client'

import React, { useState, useEffect } from 'react'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { getJson, putJson } from '@/utils/api'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/contexts/ToastContext'

interface UserSettings {
  username: string
  email: string
  currentPassword: string
  newPassword: string
  confirmPassword: string
  originalUsername: string
  originalEmail: string
}

const SettingsPage = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const { refreshAuth } = useAuth()
  const toast = useToast()
  const [settings, setSettings] = useState<UserSettings>({
    username: '',
    email: '',
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    originalUsername: '',
    originalEmail: '',
  })

  useEffect(() => {
    fetchUserSettings()
  }, [])

  const fetchUserSettings = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getJson<any>(`${SERVER_URL}/platform/user/me`)
      setSettings(prev => ({
        ...prev,
        username: data.username,
        email: data.email,
        originalUsername: data.username,
        originalEmail: data.email,
      }))
    } catch (err) {
      setError('Failed to load user settings. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setSettings(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)

    if (settings.newPassword !== settings.confirmPassword) {
      setError('New passwords do not match')
      return
    }

    try {
      // Track whether we made any change requests
      let didChange = false

      // 1) Profile updates (username/email) via PUT /platform/user/{username}
      const profileUpdates: any = {}
      if (settings.username && settings.username !== settings.originalUsername) {
        profileUpdates.username = settings.username
      }
      if (settings.email && settings.email !== settings.originalEmail) {
        profileUpdates.email = settings.email
      }
      if (Object.keys(profileUpdates).length > 0) {
        await putJson(`${SERVER_URL}/platform/user/${encodeURIComponent(settings.originalUsername)}`, profileUpdates)
        didChange = true
      }

      // 2) Password update via PUT /platform/user/{username}/update-password
      if (settings.newPassword) {
        await putJson(`${SERVER_URL}/platform/user/${encodeURIComponent(settings.originalUsername)}/update-password`, { new_password: settings.newPassword })
        didChange = true
      }

      if (!didChange) {
        setError('No changes to save')
        return
      }

      setSuccess('Settings updated successfully!')
      setSettings(prev => ({
        ...prev,
        originalUsername: settings.username,
        originalEmail: settings.email,
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      }))
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to update settings. Please try again.')
      }
    }
  }

  // no-op leftover cleanup (import UI moved to its own page)

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage your account settings and preferences
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={refreshing}
              onClick={async () => {
                try {
                  setRefreshing(true)
                  await refreshAuth()
                  toast.success('Session extended')
                } catch (e) {
                  toast.error('Failed to extend session')
                } finally {
                  setRefreshing(false)
                }
              }}
            >
              {refreshing ? 'Extending…' : 'Extend Session'}
            </button>
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
                <p className="text-gray-600 dark:text-gray-400">Loading settings...</p>
              </div>
            </div>
          </div>
        ) : (
          /* Settings Form */
          <div className="card max-w-2xl">
            <div className="card-header">
              <h3 className="card-title">Account Settings</h3>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              <div className="space-y-4">
                <h4 className="text-lg font-medium text-gray-900 dark:text-white">Profile Information</h4>

                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Username
                  </label>
                  <input
                    type="text"
                    id="username"
                    name="username"
                    value={settings.username}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Enter your username"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={settings.email}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Enter your email address"
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="space-y-4 pt-6 border-t border-gray-200 dark:border-gray-700">
                <h4 className="text-lg font-medium text-gray-900 dark:text-white">Change Password</h4>

                <div>
                  <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Current Password
                  </label>
                  <input
                    type="password"
                    id="currentPassword"
                    name="currentPassword"
                    value={settings.currentPassword}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Enter your current password"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    New Password
                  </label>
                  <input
                    type="password"
                    id="newPassword"
                    name="newPassword"
                    value={settings.newPassword}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Enter your new password"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    id="confirmPassword"
                    name="confirmPassword"
                    value={settings.confirmPassword}
                    onChange={handleInputChange}
                    className="input"
                    placeholder="Confirm your new password"
                    disabled={loading}
                  />
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
                      Saving...
                    </div>
                  ) : (
                    'Save Changes'
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSettings(prev => ({
                      ...prev,
                      username: prev.originalUsername,
                      email: prev.originalEmail,
                      currentPassword: '',
                      newPassword: '',
                      confirmPassword: ''
                    }))
                    setError(null)
                  }}
                  className="btn btn-secondary flex-1"
                >
                  Reset
                </button>
              </div>
            </form>
          </div>
        )}

      </div>
    </Layout>
  )
}

export default SettingsPage
