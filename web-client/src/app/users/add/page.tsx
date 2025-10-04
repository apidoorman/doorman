'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
import FormHelp from '@/components/FormHelp'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'

interface CreateUserData {
  username: string
  email: string
  password: string
  role: string
  groups: string[]
  rate_limit_duration?: number
  rate_limit_duration_type?: string
  throttle_duration?: number
  throttle_duration_type?: string
  throttle_wait_duration?: number
  throttle_wait_duration_type?: string
  throttle_queue_limit?: number | null
  custom_attributes: Record<string, string>
  bandwidth_limit_bytes?: number
  bandwidth_limit_window?: string
  active: boolean
  ui_access: boolean
}

const AddUserPage = () => {
  const router = useRouter()
  const [formData, setFormData] = useState<CreateUserData>({
    username: '',
    email: '',
    password: '',
    role: '',
    groups: [],
    custom_attributes: {},
    bandwidth_limit_bytes: undefined,
    bandwidth_limit_window: 'day',
    active: true,
    ui_access: false
  })
  const [newGroup, setNewGroup] = useState('')
  const [newCustomAttribute, setNewCustomAttribute] = useState({ key: '', value: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [passwordStrength, setPasswordStrength] = useState({ score: 0, message: '' })
  const customAttrCount = Object.keys(formData.custom_attributes || {}).length

  const handleInputChange = (field: keyof CreateUserData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))

    if (field === 'password') {
      checkPasswordStrength(value)
    }
  }

  const checkPasswordStrength = (password: string) => {
    let score = 0
    let message = ''

    if (password.length >= 16) score++
    if (/[A-Z]/.test(password)) score++
    if (/[a-z]/.test(password)) score++
    if (/\d/.test(password)) score++
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score++

    if (score < 3) message = 'Weak - Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character'
    else if (score < 5) message = 'Medium - Add more complexity'
    else message = 'Strong - Password meets security requirements'

    setPasswordStrength({ score, message })
  }

  const addGroup = () => {
    if (newGroup.trim()) {
      setFormData(prev => ({ ...prev, groups: [...prev.groups, newGroup.trim()] }))
      setNewGroup('')
    }
  }

  const removeGroup = (index: number) => {
    setFormData(prev => ({ ...prev, groups: prev.groups.filter((_, i) => i !== index) }))
  }

  const addCustomAttribute = () => {
    if (customAttrCount >= 10) {
      setError('Maximum 10 custom attributes allowed. Please replace an existing one.')
      return
    }
    if (newCustomAttribute.key && newCustomAttribute.value) {
      setFormData(prev => ({
        ...prev,
        custom_attributes: {
          ...prev.custom_attributes,
          [newCustomAttribute.key]: newCustomAttribute.value
        }
      }))
      setNewCustomAttribute({ key: '', value: '' })
    }
  }

  const removeCustomAttribute = (key: string) => {
    const newCustomAttributes = { ...formData.custom_attributes }
    delete newCustomAttributes[key]
    setFormData(prev => ({ ...prev, custom_attributes: newCustomAttributes }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.username || !formData.email || !formData.password || !formData.role) {
      setError('Please fill in all required fields')
      return
    }

    if (passwordStrength.score < 5) {
      setError('Password does not meet security requirements')
      return
    }

    try {
      setLoading(true)
      setError(null)

      await postJson(`${SERVER_URL}/platform/user/`, formData)

      router.push('/users')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Add New User</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Create a new user account with permissions and settings
            </p>
          </div>
          <Link href="/users" className="btn btn-secondary">
            <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Users
          </Link>
        </div>

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

        <div className="card max-w-4xl">
          <form onSubmit={handleSubmit} className="space-y-8">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Basic Information</h3>
                <FormHelp docHref="/docs/using-fields.html#users">Create user credentials, set role and UI access.</FormHelp>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Username *
                  </label>
                  <input
                    type="text"
                    id="username"
                    className="input"
                    placeholder="Enter username"
                    value={formData.username}
                    onChange={(e) => handleInputChange('username', e.target.value)}
                    minLength={3}
                    maxLength={50}
                    required
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Email *
                  </label>
                  <input
                    type="email"
                    id="email"
                    className="input"
                    placeholder="Enter email"
                    value={formData.email}
                    onChange={(e) => handleInputChange('email', e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Password *
                    <InfoTooltip text="Minimum 16 chars with upper, lower, digit, and symbol for strong security." />
                  </label>
                  <input
                    type="password"
                    id="password"
                    className="input"
                    placeholder="Enter password (min 16 chars)"
                    value={formData.password}
                    onChange={(e) => handleInputChange('password', e.target.value)}
                    minLength={16}
                    maxLength={50}
                    required
                    disabled={loading}
                  />
                  {formData.password && (
                    <div className={`mt-2 text-sm ${passwordStrength.score < 5 ? 'text-error-600 dark:text-error-400' : 'text-success-600 dark:text-success-400'}`}>
                      {passwordStrength.message}
                    </div>
                  )}
                </div>
                <div>
                  <label htmlFor="role" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Role *
                    <InfoTooltip text="Platform role controls permissions (e.g., manage_apis, view_logs)." />
                  </label>
                  <input
                    type="text"
                    id="role"
                    className="input"
                    placeholder="Enter role"
                    value={formData.role}
                    onChange={(e) => handleInputChange('role', e.target.value)}
                    minLength={2}
                    maxLength={50}
                    required
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="status" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Status
                    <InfoTooltip text="Inactive users cannot authenticate until re-enabled. Does not affect public or no-auth APIs." />
                  </label>
                  <select
                    id="status"
                    className="input"
                    value={formData.active ? 'true' : 'false'}
                    onChange={(e) => handleInputChange('active', e.target.value === 'true')}
                    disabled={loading}
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="ui_access" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    UI Access
                  </label>
                  <select
                    id="ui_access"
                    className="input"
                    value={formData.ui_access ? 'true' : 'false'}
                    onChange={(e) => handleInputChange('ui_access', e.target.value === 'true')}
                    disabled={loading}
                  >
                    <option value="false">Disabled</option>
                    <option value="true">Enabled</option>
                  </select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Controls access to the admin UI; API access is separate.</p>
                </div>
              </div>
            </div>

            <div className="space-y-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Groups</h3>
                <FormHelp docHref="/docs/using-fields.html#access-control">Groups are used for API access checks alongside roles.</FormHelp>
              </div>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {formData.groups.map((group, index) => (
                    <div key={index} className="flex items-center gap-2 bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{group}</span>
                      <button
                        type="button"
                        onClick={() => removeGroup(index)}
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
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="input flex-1"
                    placeholder="Enter group name"
                    value={newGroup}
                    onChange={(e) => setNewGroup(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addGroup())}
                    disabled={loading}
                  />
                  <button type="button" className="btn btn-primary" onClick={addGroup} disabled={loading}>
                    Add Group
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Rate Limiting</h3>
                <FormHelp docHref="/docs/using-fields.html#rate-limit">Limits requests per user over a time window.</FormHelp>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="rate_limit_duration" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Rate Limit Duration
                    <InfoTooltip text="Numeric window size (e.g., 100) combined with type (minute/hour)." />
                  </label>
                  <input
                    type="number"
                    id="rate_limit_duration"
                    className="input"
                    value={formData.rate_limit_duration || ''}
                    onChange={(e) => handleInputChange('rate_limit_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                    min="0"
                    placeholder="100"
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="rate_limit_duration_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Rate Limit Type
                    <InfoTooltip text="Unit for the rate limit window. Example: minute." />
                  </label>
                  <select
                    id="rate_limit_duration_type"
                    className="input"
                    value={formData.rate_limit_duration_type || ''}
                    onChange={(e) => handleInputChange('rate_limit_duration_type', e.target.value)}
                    disabled={loading}
                  >
                    <option value="">Select type</option>
                    <option value="second">Second</option>
                    <option value="minute">Minute</option>
                    <option value="hour">Hour</option>
                    <option value="day">Day</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="space-y-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Throttling</h3>
                <FormHelp docHref="/docs/using-fields.html#throttle">Control burst behavior with wait, duration, and queue size.</FormHelp>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="throttle_duration" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Throttle Duration
                    <InfoTooltip text="How long a throttle period lasts before resetting." />
                  </label>
                  <input
                    type="number"
                    id="throttle_duration"
                    className="input"
                    value={formData.throttle_duration || ''}
                    onChange={(e) => handleInputChange('throttle_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                    min="0"
                    placeholder="10"
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="throttle_duration_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Throttle Type
                    <InfoTooltip text="Unit for the throttle duration period." />
                  </label>
                  <select
                    id="throttle_duration_type"
                    className="input"
                    value={formData.throttle_duration_type || ''}
                    onChange={(e) => handleInputChange('throttle_duration_type', e.target.value)}
                    disabled={loading}
                  >
                    <option value="">Select type</option>
                    <option value="second">Second</option>
                    <option value="minute">Minute</option>
                    <option value="hour">Hour</option>
                    <option value="day">Day</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="throttle_wait_duration" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Wait Duration
                    <InfoTooltip text="How long requests wait when throttled before retrying." />
                  </label>
                  <input
                    type="number"
                    id="throttle_wait_duration"
                    className="input"
                    value={formData.throttle_wait_duration || ''}
                    onChange={(e) => handleInputChange('throttle_wait_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                    min="0"
                    placeholder="5"
                    disabled={loading}
                  />
                </div>
                <div>
                  <label htmlFor="throttle_wait_duration_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Wait Type
                    <InfoTooltip text="Unit for the wait duration (seconds/minutes/etc)." />
                  </label>
                  <select
                    id="throttle_wait_duration_type"
                    className="input"
                    value={formData.throttle_wait_duration_type || ''}
                    onChange={(e) => handleInputChange('throttle_wait_duration_type', e.target.value)}
                    disabled={loading}
                  >
                    <option value="">Select type</option>
                    <option value="second">Second</option>
                    <option value="minute">Minute</option>
                    <option value="hour">Hour</option>
                    <option value="day">Day</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="throttle_queue_limit" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Queue Limit
                    <InfoTooltip text="Maximum number of queued requests when throttled; null disables queueing." />
                  </label>
                  <input
                    type="number"
                    id="throttle_queue_limit"
                    className="input"
                    value={formData.throttle_queue_limit || ''}
                    onChange={(e) => handleInputChange('throttle_queue_limit', e.target.value ? parseInt(e.target.value) : null)}
                    min="0"
                    placeholder="10"
                    disabled={loading}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Bandwidth Limit</h3>
                <FormHelp docHref="/docs/using-fields.html#bandwidth">Limit total bytes per user over a time window.</FormHelp>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Bytes (limit)</label>
                  <input type="number" className="input" min={0}
                    value={formData.bandwidth_limit_bytes ?? ''}
                    onChange={(e) => handleInputChange('bandwidth_limit_bytes', e.target.value ? parseInt(e.target.value) : undefined)}
                    placeholder="e.g., 1073741824 for 1 GB" disabled={loading} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Window</label>
                  <select className="input" value={formData.bandwidth_limit_window || 'day'}
                    onChange={(e) => handleInputChange('bandwidth_limit_window', e.target.value)} disabled={loading}>
                    <option value="second">Second</option>
                    <option value="minute">Minute</option>
                    <option value="hour">Hour</option>
                    <option value="day">Day</option>
                    <option value="week">Week</option>
                    <option value="month">Month</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="space-y-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Custom Attributes</h3>
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {Object.entries(formData.custom_attributes).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2 bg-purple-100 dark:bg-purple-900/20 text-purple-800 dark:text-purple-200 px-3 py-1 rounded-full">
                      <span className="text-sm">{key}: {value}</span>
                      <button
                        type="button"
                        onClick={() => removeCustomAttribute(key)}
                        className="text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-200"
                        disabled={loading}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <input
                    type="text"
                    className="input"
                    placeholder="Key"
                    value={newCustomAttribute.key}
                    onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, key: e.target.value }))}
                    disabled={loading || customAttrCount >= 10}
                  />
                  <input
                    type="text"
                    className="input"
                    placeholder="Value"
                    value={newCustomAttribute.value}
                    onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, value: e.target.value }))}
                    disabled={loading || customAttrCount >= 10}
                  />
                  <button type="button" className="btn btn-primary" onClick={addCustomAttribute} disabled={loading || customAttrCount >= 10}>
                    Add
                  </button>
                </div>
                {customAttrCount >= 10 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">Maximum of 10 custom attributes reached. Remove one to add another.</p>
                )}
              </div>
            </div>

            <div className="flex gap-4 pt-6 border-t border-gray-200 dark:border-gray-700">
              <button type="submit" disabled={loading} className="btn btn-primary flex-1">
                {loading ? (
                  <div className="flex items-center justify-center">
                    <div className="spinner mr-2"></div>
                    Creating User...
                  </div>
                ) : (
                  'Create User'
                )}
              </button>
              <Link href="/users" className="btn btn-secondary flex-1">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  )
    if (Object.keys(formData.custom_attributes || {}).length > 10) {
      setError('Maximum 10 custom attributes allowed. Please replace an existing one.')
      return
    }
}

export default AddUserPage
