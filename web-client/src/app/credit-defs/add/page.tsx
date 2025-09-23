'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { postJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'

export default function AddCreditDefPage() {
  const [api_credit_group, setGroup] = useState('')
  const [api_key_header, setHeader] = useState('x-api-key')
  const [api_key, setKey] = useState('')
  const [creditTiersText, setTiersText] = useState('[\n  {"tier_name":"basic","credits":100,"input_limit":150,"output_limit":150,"reset_frequency":"monthly"}\n]')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const create = async () => {
    setWorking(true); setError(null); setSuccess(null)
    try {
      if (!api_credit_group.trim()) throw new Error('Group is required')
      const tiers = JSON.parse(creditTiersText || '[]')
      await postJson(`${SERVER_URL}/platform/credit`, { api_credit_group: api_credit_group.trim(), api_key, api_key_header, credit_tiers: tiers })
      setSuccess('Credit definition created')
    } catch (e: any) {
      setError(e?.message || 'Failed to create credit definition')
    } finally {
      setWorking(false)
    }
  }

  return (
    <ProtectedRoute requiredPermission="manage_credits">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Add Credit Definition</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Create a credit group and tiers</p>
            </div>
            <Link href="/credit-defs" className="btn btn-secondary">Back to Credit Definitions</Link>
          </div>

          <div className="card">
            <div className="p-6 space-y-4">
              {error && <div className="text-sm text-error-600">{error}</div>}
              {success && <div className="text-sm text-success-600">{success}</div>}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium">API Credit Group</label>
                  <input className="input" value={api_credit_group} onChange={e => setGroup(e.target.value)} placeholder="ai-basic" />
                </div>
                <div>
                  <label className="block text-sm font-medium">API Key Header</label>
                  <input className="input" value={api_key_header} onChange={e => setHeader(e.target.value)} placeholder="x-api-key" />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium">API Key</label>
                  <input className="input" value={api_key} onChange={e => setKey(e.target.value)} placeholder="sk_live_..." />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium">Credit Tiers (JSON)</label>
                  <textarea className="input font-mono text-xs h-48" value={creditTiersText} onChange={e => setTiersText(e.target.value)} />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={create} disabled={working} className="btn btn-primary">{working ? 'Saving...' : 'Create'}</button>
                <Link href="/credit-defs" className="btn btn-ghost">Cancel</Link>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
