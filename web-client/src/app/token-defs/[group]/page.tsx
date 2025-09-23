'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { SERVER_URL } from '@/utils/config'
import { getJson, putJson, delJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ConfirmModal from '@/components/ConfirmModal'

export default function EditTokenDefPage() {
  const params = useParams<{ group: string }>()
  const router = useRouter()
  const group = decodeURIComponent(params.group)
  const [api_token_group] = useState(group)
  const [api_key_header, setHeader] = useState('x-api-key')
  const [api_key, setKey] = useState('')
  const [tokenTiersText, setTiersText] = useState('[]')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showDelete, setShowDelete] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  useEffect(() => { load() }, [])
  const load = async () => {
    try {
      setError(null)
      const res = await getJson<any>(`${SERVER_URL}/platform/token/defs/${encodeURIComponent(group)}`)
      const data = res?.response || res
      setHeader(data.api_key_header || 'x-api-key')
      setTiersText(JSON.stringify(data.token_tiers || [], null, 2))
    } catch (e:any) {
      setError(e?.message || 'Failed to load token definition')
    }
  }

  const update = async () => {
    setWorking(true); setError(null); setSuccess(null)
    try {
      const tiers = JSON.parse(tokenTiersText || '[]')
      const payload: any = { api_token_group, api_key_header, token_tiers: tiers }
      if (api_key) payload.api_key = api_key // set only if provided
      await putJson(`${SERVER_URL}/platform/token/${encodeURIComponent(api_token_group)}`, payload)
      setSuccess('Token definition updated')
      setKey('')
    } catch (e:any) {
      setError(e?.message || 'Failed to update token definition')
    } finally {
      setWorking(false)
    }
  }

  const onDelete = async () => {
    if (confirmText !== api_token_group) return
    setWorking(true)
    try {
      await delJson(`${SERVER_URL}/platform/token/${encodeURIComponent(api_token_group)}`)
      router.push('/token-defs')
    } catch (e:any) {
      setError(e?.message || 'Failed to delete token definition')
    } finally {
      setWorking(false)
    }
  }

  return (
    <ProtectedRoute requiredPermission="manage_tokens">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Edit Token Definition</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">{api_token_group}</p>
            </div>
            <Link href="/token-defs" className="btn btn-secondary">Back to Token Definitions</Link>
          </div>

          <div className="card">
            <div className="p-6 space-y-4">
              {error && <div className="text-sm text-error-600">{error}</div>}
              {success && <div className="text-sm text-success-600">{success}</div>}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium">API Token Group</label>
                  <input className="input" value={api_token_group} readOnly />
                </div>
                <div>
                  <label className="block text-sm font-medium">API Key Header</label>
                  <input className="input" value={api_key_header} onChange={e => setHeader(e.target.value)} />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium">API Key (leave blank to keep existing)</label>
                  <input className="input" value={api_key} onChange={e => setKey(e.target.value)} placeholder="sk_live_..." />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium">Token Tiers (JSON)</label>
                  <textarea className="input font-mono text-xs h-48" value={tokenTiersText} onChange={e => setTiersText(e.target.value)} />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={update} disabled={working} className="btn btn-primary">{working ? 'Saving...' : 'Save Changes'}</button>
                <button onClick={() => setShowDelete(true)} className="btn btn-error">Delete</button>
                <Link href="/token-defs" className="btn btn-ghost">Cancel</Link>
              </div>
            </div>
          </div>

          <ConfirmModal
            open={showDelete}
            title="Delete Token Definition"
            message={<div>
              Type <span className="font-mono">{api_token_group}</span> to confirm deletion.
              <div className="mt-3"><input className="input w-full" value={confirmText} onChange={e => setConfirmText(e.target.value)} /></div>
            </div>}
            confirmLabel={working ? 'Deleting...' : 'Delete'}
            cancelLabel="Cancel"
            onCancel={() => setShowDelete(false)}
            onConfirm={onDelete}
          />
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

