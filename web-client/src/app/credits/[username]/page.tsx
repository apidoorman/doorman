'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import InfoTooltip from '@/components/InfoTooltip'
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
  const [addGroupName, setAddGroupName] = useState('')
  const [addGroupTier, setAddGroupTier] = useState('')
  const [addGroupCredits, setAddGroupCredits] = useState<number | ''>('')
  const [addResetDate, setAddResetDate] = useState('')

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

  const availableGroupsToAdd = useMemo(() => {
    const current = new Set(Object.keys(userCredits || {}))
    return Object.keys(defs || {}).filter(g => !current.has(g))
  }, [defs, userCredits])

  // Inline validation: available must be within [0, total]
  const invalidGroups = useMemo(() => {
    const bad: string[] = []
    for (const [group, info] of Object.entries(userCredits || {})) {
      const tier = (info as any).tier_name
      const total = defs[group]?.[tier || '']?.credits || 0
      const available = Number((info as any).available_credits || 0)
      if (available < 0 || (total > 0 && available > total)) {
        bad.push(group)
      }
    }
    return bad
  }, [userCredits, defs])

  const addGroupToUser = () => {
    if (!addGroupName) return
    const tier = addGroupTier || Object.keys(defs[addGroupName] || {})[0]
    const total = defs[addGroupName]?.[tier || '']?.credits || 0
    let avail = typeof addGroupCredits === 'number' ? addGroupCredits : total
    if (avail < 0) avail = 0
    if (total > 0 && avail > total) avail = total
    setUserCredits(prev => ({
      ...prev,
      [addGroupName]: {
        tier_name: tier,
        available_credits: avail,
        reset_date: addResetDate || '',
      }
    }))
    setAddGroupName(''); setAddGroupTier(''); setAddGroupCredits(''); setAddResetDate('')
  }

  const removeGroupFromUser = (group: string) => {
    const next = { ...userCredits }
    delete next[group]
    setUserCredits(next)
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
              <button onClick={save} disabled={saving || invalidGroups.length > 0} className="btn btn-primary">{saving ? 'Saving…' : (invalidGroups.length>0 ? 'Fix Errors to Save' : 'Save')}</button>
              </div>
            </div>

          {error && <div className="rounded-md bg-error-50 border border-error-200 p-3 text-error-700 text-sm">{error}</div>}
          {success && <div className="rounded-md bg-success-50 border border-success-200 p-3 text-success-700 text-sm">{success}</div>}

          {loading ? (
            <div className="card"><div className="p-6 text-gray-500">Loading…</div></div>
          ) : (
            <>
              <div className="card">
                <div className="card-header"><h3 className="card-title">Add Credit Group</h3></div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
                  <div>
                    <label className="block text-sm font-medium mb-1">Group <InfoTooltip text="Credit group to assign to this user" /></label>
                    <select className="input" value={addGroupName} onChange={e => { setAddGroupName(e.target.value); setAddGroupTier('') }}>
                      <option value="">Select group</option>
                      {availableGroupsToAdd.map(g => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Tier <InfoTooltip text="Tier within the selected group determining total credits" /></label>
                    <select className="input" value={addGroupTier} onChange={e => setAddGroupTier(e.target.value)} disabled={!addGroupName}>
                      <option value="">{addGroupName ? 'Select tier' : 'Select group first'}</option>
                      {addGroupName && Object.keys(defs[addGroupName] || {}).map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Available Credits <InfoTooltip text="Initial available credits; must be between 0 and the tier total" /></label>
                    <input className="input" type="number" value={addGroupCredits as any}
                           onChange={e => setAddGroupCredits(e.target.value === '' ? '' : Number(e.target.value))} placeholder="auto" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Tier Total <InfoTooltip text="Total credits configured for the chosen tier" /></label>
                    <div className="flex items-center gap-2">
                      <div className="text-sm text-gray-700 dark:text-gray-300">
                        {addGroupName && (defs[addGroupName]?.[addGroupTier || Object.keys(defs[addGroupName]||{})[0]]?.credits || 0)}
                      </div>
                      <button className="btn btn-secondary" disabled={!addGroupName} onClick={() => {
                        const t = addGroupTier || Object.keys(defs[addGroupName] || {})[0]
                        const total = defs[addGroupName]?.[t || '']?.credits || 0
                        setAddGroupCredits(total)
                      }}>Use Full</button>
                    </div>
                    {addGroupName && typeof addGroupCredits === 'number' && (() => {
                      const t = addGroupTier || Object.keys(defs[addGroupName] || {})[0]
                      const total = defs[addGroupName]?.[t || '']?.credits || 0
                      const bad = addGroupCredits < 0 || (total > 0 && addGroupCredits > total)
                      return bad ? <div className="text-xs text-error-600 mt-1">Must be between 0 and {total}</div> : null
                    })()}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Reset Date <InfoTooltip text="Optional date when the user's credits reset for this group" /></label>
                    <input className="input" type="date" value={addResetDate} onChange={e => setAddResetDate(e.target.value)} />
                  </div>
                  <div>
                    <button className="btn btn-primary w-full" onClick={addGroupToUser} disabled={!addGroupName || (()=>{
                      if (addGroupName && typeof addGroupCredits === 'number'){
                        const t = addGroupTier || Object.keys(defs[addGroupName] || {})[0]
                        const total = defs[addGroupName]?.[t || '']?.credits || 0
                        return addGroupCredits < 0 || (total > 0 && addGroupCredits > total)
                      }
                      return false
                    })()}>Add</button>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-header"><h3 className="card-title">Allocations</h3></div>
                <div className="p-6 space-y-4">
                  {Object.entries(userCredits).length === 0 && (
                    <div className="text-gray-500">No credit groups for this user</div>
                  )}
                  {Object.entries(userCredits).map(([group, info]) => {
                    const tierMap = defs[group] || {}
                    const currentTier = (info as any).tier_name
                    const meta = tierMap[currentTier] || { credits: 0, reset_frequency: undefined }
                    const total = meta.credits || 0
                    const available = Number((info as any).available_credits || 0)
                    const used = total > 0 ? Math.max(total - available, 0) : 0
                    const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((used / total) * 100))) : 0
                    return (
                      <div key={group} className="border rounded-lg p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="badge badge-gray">{group}</span>
                            <div className="text-xs text-gray-500">Reset: {meta.reset_frequency || '-'} | Date: {(info as any).reset_date || '-'}</div>
                          </div>
                          <button className="btn btn-ghost text-error-600" onClick={() => removeGroupFromUser(group)}>Remove</button>
                        </div>
                        <div className="mt-3">
                          <div className="h-2 bg-gray-200 dark:bg-gray-800 rounded">
                            <div className="h-2 bg-primary-500 rounded" style={{ width: `${pct}%` }} />
                          </div>
                          <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">{used} used of {total} · {available} left</div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
                          <div>
                            <label className="block text-sm font-medium mb-1">Tier</label>
                            <select className="input" value={(info as any).tier_name || ''}
                                    onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], tier_name: e.target.value } }))}>
                              {Object.keys(tierMap).map(t => (<option key={t} value={t}>{t}</option>))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium mb-1">Available Credits</label>
                            <div className="flex flex-wrap gap-2 items-center">
                              <input className={`input flex-1 ${invalidGroups.includes(group)?'border-error-500':''}`} type="number" value={(info as any).available_credits}
                                     onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], available_credits: Number(e.target.value || 0) } }))} />
                              <button className="btn btn-secondary" onClick={() => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], available_credits: Number((prev as any)[group].available_credits || 0) + 10 } }))}>+10</button>
                              <button className="btn btn-secondary" onClick={() => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], available_credits: Math.max(0, Number((prev as any)[group].available_credits || 0) - 10) } }))}>-10</button>
                              <button className="btn btn-secondary" onClick={() => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], available_credits: total } }))}>Full</button>
                            </div>
                            {invalidGroups.includes(group) && (
                              <div className="text-xs text-error-600 mt-1">Must be between 0 and {total}</div>
                            )}
                          </div>
                          <div>
                            <label className="block text-sm font-medium mb-1">Reset Date</label>
                            <input className="input" type="date" value={(info as any).reset_date || ''}
                                   onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], reset_date: e.target.value } }))} />
                          </div>
                          <div>
                            <label className="block text-sm font-medium mb-1">User API Key (optional)</label>
                            <input className="input" placeholder="user API key"
                                   value={(info as any).user_api_key || ''}
                                   onChange={e => setUserCredits(prev => ({ ...prev, [group]: { ...(prev as any)[group], user_api_key: e.target.value } }))} />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
