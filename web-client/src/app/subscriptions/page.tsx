'use client'

import React, { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ConfirmModal from '@/components/ConfirmModal'

interface SubsPayload {
  apis: string[]
}

export default function SubscriptionsPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [currentSubs, setCurrentSubs] = useState<string[]>([])
  const [username, setUsername] = useState('')
  const [apiName, setApiName] = useState('')
  const [apiVersion, setApiVersion] = useState('v1')
  const [showUnsubModal, setShowUnsubModal] = useState(false)
  const [unsubConfirmation, setUnsubConfirmation] = useState('')

  const loadCurrentUserSubs = async () => {
    try {
      setLoading(true); setError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/subscription/subscriptions`)
      const list = payload.apis || []
      setCurrentSubs(list)
    } catch (e:any) {
      setError(e?.message || 'Failed to load subscriptions')
      setCurrentSubs([])
    } finally { setLoading(false) }
  }

  useEffect(() => { loadCurrentUserSubs() }, [])

  const subscribe = async () => {
    try {
      setError(null); setSuccess(null)
      const body = { username: username || undefined, api_name: apiName.trim(), api_version: apiVersion.trim() }
      if (!body.api_name) throw new Error('API name is required')
      await postJson(`${SERVER_URL}/platform/subscription/subscribe`, body)
      setSuccess('Subscribed')
      setTimeout(() => setSuccess(null), 1500)
      await loadCurrentUserSubs()
    } catch (e:any) { setError(e?.message || 'Subscribe failed') }
  }

  const openUnsubModal = () => {
    if (!apiName.trim()) {
      setError('API name is required')
      return
    }
    setShowUnsubModal(true)
  }

  const unsubscribe = async () => {
    try {
      setError(null); setSuccess(null)
      const body = { username: username || undefined, api_name: apiName.trim(), api_version: apiVersion.trim() }
      if (!body.api_name) throw new Error('API name is required')
      await postJson(`${SERVER_URL}/platform/subscription/unsubscribe`, body)
      setSuccess('Unsubscribed')
      setTimeout(() => setSuccess(null), 1500)
      await loadCurrentUserSubs()
      setShowUnsubModal(false)
      setUnsubConfirmation('')
    } catch (e:any) { setError(e?.message || 'Unsubscribe failed') }
  }

  return (
    <ProtectedRoute requiredPermission="manage_subscriptions">
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Subscriptions</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">Manage API subscriptions</p>
          </div>
          <button onClick={loadCurrentUserSubs} className="btn btn-secondary">Refresh</button>
        </div>

        {error && <div className="rounded-md bg-error-50 border border-error-200 p-3 text-error-700 text-sm">{error}</div>}
        {success && <div className="rounded-md bg-success-50 border border-success-200 p-3 text-success-700 text-sm">{success}</div>}

        <div className="card">
          <div className="card-header"><h3 className="card-title">Subscribe/Unsubscribe</h3></div>
          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium">Username (optional)</label>
              <input className="input" value={username} onChange={e => setUsername(e.target.value)} placeholder="admin" />
            </div>
            <div>
              <label className="block text-sm font-medium">API Name</label>
              <input className="input" value={apiName} onChange={e => setApiName(e.target.value)} placeholder="orders" />
            </div>
            <div>
              <label className="block text-sm font-medium">API Version</label>
              <input className="input" value={apiVersion} onChange={e => setApiVersion(e.target.value)} placeholder="v1" />
            </div>
            <div className="md:col-span-3 flex gap-2">
              <button className="btn btn-primary" onClick={subscribe}>Subscribe</button>
              <button className="btn btn-error" onClick={openUnsubModal}>Unsubscribe</button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h3 className="card-title">Current User Subscriptions</h3></div>
          <div className="p-6">
            {loading ? (
              <div className="text-gray-500">Loading...</div>
            ) : (
              <ul className="list-disc pl-6 text-sm text-gray-700 dark:text-gray-300">
                {currentSubs.map((s, i) => <li key={i}>{s}</li>)}
                {currentSubs.length === 0 && <li className="text-gray-500">No subscriptions</li>}
              </ul>
            )}
          </div>
        </div>
      </div>

      <ConfirmModal
        open={showUnsubModal}
        title="Unsubscribe"
        message={<>
          This will unsubscribe {username || 'current user'} from <span className="font-mono">{apiName.trim()}/{apiVersion.trim()}</span>.
        </>}
        confirmLabel="Unsubscribe"
        cancelLabel="Cancel"
        onCancel={() => setShowUnsubModal(false)}
        onConfirm={unsubscribe}
      />
    </Layout>
    </ProtectedRoute>
  )
}
