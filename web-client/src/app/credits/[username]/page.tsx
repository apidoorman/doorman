'use client'

import React, { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson } from '@/utils/api'

type TierMeta = { credits: number; reset_frequency?: string }

export default function UserCreditsDetailPage() {
  const { username } = useParams<{ username: string }>()
  const router = useRouter()
  const uname = decodeURIComponent(username)

  const [defs, setDefs] = useState<Record<string, { [tier: string]: TierMeta }>>({})
  const [userCredits, setUserCredits] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadDefs = async () => {
    try {
      const res = await getJson<any>(`${SERVER_URL}/platform/credit/defs?page=1&page_size=1000`)
      const items = res?.items || res?.response?.items || []
      const map: Record<string, { [tier: string]: TierMeta }> = {}
      for (const it of items) {
        const tierMap: Record<string, TierMeta> = {}
        for (const t of (it.credit_tiers || [])) {
          tierMap[t.tier_name] = { credits: Number(t.credits || 0), reset_frequency: t.reset_frequency }
        }
        map[it.api_credit_group] = tierMap
      }
      setDefs(map)
    } catch {}
  }

  const loadUser = async () => {
    try {
      setError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/credit/${encodeURIComponent(uname)}`)
      setUserCredits(payload.users_credits || {})
    } catch (e:any) {
      setError(e?.message || 'Failed to load user credits')
      setUserCredits({})
    }
  }

  useEffect(() => {
    (async () => {
      setLoading(true)
      await Promise.all([loadDefs(), loadUser()])
      setLoading(false)
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uname])

  const save = async () => {
    try {
      setSaving(true); setError(null); setSuccess(null)
      await postJson(`${SERVER_URL}/platform/credit/${encodeURIComponent(uname)}`, { username: uname, users_credits: userCredits })
      setSuccess('User credits saved')
      setTimeout(() => setSuccess(null), 2000)
    } catch (e:any) {
      setError(e?.message || 'Failed to save user credits')
    } finally { setSaving(false) }
  }

  return (
    <ProtectedRoute requiredPermission="manage_credits">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Credits for {uname}</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">View and edit per-group credit allocations</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => router.push('/credits')} className="btn btn-secondary">Back to Credits</button>
              <button onClick={save} disabled={saving} className="btn btn-primary">{saving ? 'Saving…' : 'Save'}</button>
            </div>
          </div>

          {error && <div className="rounded-md bg-error-50 border border-error-200 p-3 text-error-700 text-sm">{error}</div>}
          {success && <div className="rounded-md bg-success-50 border border-success-200 p-3 text-success-700 text-sm">{success}</div>}

          {loading ? (
            <div className="card"><div className="p-6 text-gray-500">Loading…</div></div>
          ) : (
            <div className="card">
              <div className="p-6 space-y-3">
                {Object.entries(userCredits).length === 0 && (
                  <div className="text-gray-500">No credit groups for this user</div>
                )}
                {Object.entries(userCredits).map(([group, info]) => {
                  const tierMap = defs[group] || {}
                  const meta = tierMap[(info as any).tier_name] || { credits: 0, reset_frequency: undefined }
                  const total = meta.credits || 0
                  const available = Number((info as any).available_credits || 0)
                  const used = total > 0 ? Math.max(total - available, 0) : 0
                  return (
                    <div key={group} className="grid grid-cols-1 md:grid-cols-12 items-center gap-2">
                      <div className="md:col-span-2">
                        <span className="badge badge-gray w-full justify-center">{group}</span>
                      </div>
                      <div className="md:col-span-2 text-sm">
                        <div className="text-gray-600">Tier</div>
                        <div className="font-medium">{(info as any).tier_name || '-'}</div>
                      </div>
                      <div className="md:col-span-2 text-sm">
                        <div className="text-gray-600">Total</div>
                        <div className="font-medium">{total || 0}</div>
                      </div>
                      <div className="md:col-span-2 text-sm">
                        <div className="text-gray-600">Used</div>
                        <div className="font-medium">{used}</div>
                      </div>
                      <div className="md:col-span-2 text-sm">
                        <div className="text-gray-600">Left</div>
                        <div className="font-medium">{available}</div>
                      </div>
                      <div className="md:col-span-1 text-sm">
                        <div className="text-gray-600">Reset Freq</div>
                        <div className="font-medium">{meta.reset_frequency || '-'}</div>
                      </div>
                      <div className="md:col-span-1 text-sm">
                        <div className="text-gray-600">Reset Date</div>
                        <div className="font-medium">{(info as any).reset_date || '-'}</div>
                      </div>
                      <div className="md:col-span-12 flex items-center gap-2">
                        <input
                          className="input w-32"
                          type="number"
                          value={(info as any).available_credits}
                          onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], available_credits: Number(e.target.value || 0) } }))}
                        />
                        <input
                          className="input flex-1"
                          placeholder="user API key (optional)"
                          value={(info as any).user_api_key || ''}
                          onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], user_api_key: e.target.value } }))}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

