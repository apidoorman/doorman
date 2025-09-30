'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson, putJson, delJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
// ConfirmModal no longer used on this page

interface CreditTier {
  tier_name: string
  credits: number
  input_limit: number
  output_limit: number
  reset_frequency: string
}

interface CreditDefForm {
  api_credit_group: string
  api_key: string
  api_key_header: string
  credit_tiers_text: string
  working: boolean
  error: string | null
  success: string | null
}

interface UserCreditInfo {
  tier_name: string
  available_credits: number
  reset_date?: string
  user_api_key?: string
}

interface UserCreditsRow {
  username: string
  users_credits: Record<string, UserCreditInfo>
}

export default function CreditsPage() {
  const router = useRouter()
  const [form, setForm] = useState<CreditDefForm>({
    api_credit_group: '',
    api_key: '',
    api_key_header: 'x-api-key',
    credit_tiers_text: '[\n  {"tier_name":"basic","credits":100,"input_limit":150,"output_limit":150,"reset_frequency":"monthly"}\n] ',
    working: false,
    error: null,
    success: null
  })
  const [usersLoading, setUsersLoading] = useState(false)
  const [userRows, setUserRows] = useState<UserCreditsRow[]>([])
  const [allUserRows, setAllUserRows] = useState<UserCreditsRow[]>([])
  const [usersPage, setUsersPage] = useState(1)
  const [usersPageSize, setUsersPageSize] = useState(10)
  const [usersHasNext, setUsersHasNext] = useState(false)
  const [userSearch, setUserSearch] = useState('')
  const [userWorking, setUserWorking] = useState(false)
  const [userError, setUserError] = useState<string | null>(null)
  const [userSuccess, setUserSuccess] = useState<string | null>(null)

  // Credit definitions cache for computing totals/used per group
  type TierMeta = { credits: number; reset_frequency?: string }
  const [defs, setDefs] = useState<Record<string, { [tier: string]: TierMeta }>>({})

  const loadDefs = async () => {
    try {
      const res = await getJson<any>(`${SERVER_URL}/platform/credit/defs?page=1&page_size=1000`)
      const items = res?.items || res?.response?.items || []
      const map: Record<string, { [tier: string]: TierMeta }> = {}
      for (const it of items) {
        const tiers = it.credit_tiers || []
        const tierMap: Record<string, TierMeta> = {}
        for (const t of tiers) tierMap[t.tier_name] = { credits: Number(t.credits || 0), reset_frequency: t.reset_frequency }
        map[it.api_credit_group] = tierMap
      }
      setDefs(map)
    } catch (e) {
      // Non-fatal; UI will just omit totals/used if defs missing
    }
  }

  const parseTiers = (): CreditTier[] => {
    try { return JSON.parse(form.credit_tiers_text || '[]') } catch { return [] }
  }

  const handleCreate = async () => {
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      const tiers = parseTiers()
      if (!form.api_credit_group.trim()) throw new Error('Credit group is required')
      await postJson(`${SERVER_URL}/platform/credit`, { api_credit_group: form.api_credit_group.trim(), api_key: form.api_key, api_key_header: form.api_key_header, credit_tiers: tiers })
      setForm(f => ({ ...f, success: 'Credit definition created' }))
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to create credit definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  const handleUpdate = async () => {
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      const tiers = parseTiers()
      if (!form.api_credit_group.trim()) throw new Error('Credit group is required')
      await putJson(`${SERVER_URL}/platform/credit/${encodeURIComponent(form.api_credit_group.trim())}`, { api_credit_group: form.api_credit_group.trim(), api_key: form.api_key, api_key_header: form.api_key_header, credit_tiers: tiers })
      setForm(f => ({ ...f, success: 'Credit definition updated' }))
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to update credit definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  // Delete modal and handlers removed; definitions managed on /credit-defs

  const loadAllUserTokens = async () => {
    try {
      setUsersLoading(true); setUserError(null)
      const q = userSearch.trim() ? `&search=${encodeURIComponent(userSearch.trim())}` : ''
      const payload = await getJson<any>(`${SERVER_URL}/platform/credit/all?page=${usersPage}&page_size=${usersPageSize}${q}`)
      const items = payload?.items || payload?.user_credits || []
      setAllUserRows(items)
      setUserRows(items)
      setUsersHasNext((items || []).length === usersPageSize)
    } catch (e:any) {
      setUserError(e?.message || 'Failed to load user credits')
      setUserRows([])
      setAllUserRows([])
      setUsersHasNext(false)
    } finally {
      setUsersLoading(false)
    }
  }

  // User detail moved to /credits/[username]

  // Saving handled on detail page

  useEffect(() => {
    loadAllUserTokens()
    loadDefs()
  }, [usersPage, usersPageSize])

  return (
    <ProtectedRoute requiredPermission="manage_credits">
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Credits</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">Manage credit definitions and user credit balances</p>
          </div>
        </div>

        <div className="card">
          <div className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="card-title">Credit Definitions</h3>
              <p className="text-gray-600 dark:text-gray-400">Create and manage credit groups, headers, and tiers</p>
            </div>
            <div className="flex gap-2">
              <Link href="/credit-defs" className="btn btn-secondary">View Definitions</Link>
              <Link href="/credit-defs/add" className="btn btn-primary">Add Definition</Link>
            </div>
          </div>
        </div>

        <div className="card -mt-3">
          <form onSubmit={(e) => { e.preventDefault(); setUsersPage(1); loadAllUserTokens() }} className="flex-1">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                className="search-input"
                placeholder="Search users by username or group..."
                value={userSearch}
                onChange={(e) => {
                  const val = e.target.value
                  setUserSearch(val)
                  const term = val.trim().toLowerCase()
                  if (!term) { setUserRows(allUserRows); return }
                  const filtered = allUserRows.filter(r =>
                    r.username.toLowerCase().includes(term) ||
                    Object.keys(r.users_credits || {}).some(g => g.toLowerCase().includes(term))
                  )
                  setUserRows(filtered)
                }}
              />
            </div>
          </form>
        </div>

        <div className="card">
          <div className="card-header"><h3 className="card-title">User Credits</h3></div>
          <div className="p-6 space-y-4">
            {userError && <div className="text-sm text-error-600">{userError}</div>}
            {userSuccess && <div className="text-sm text-success-600">{userSuccess}</div>}

            <div className="mt-2">
              {usersLoading ? (
                <div className="text-gray-500">Loading...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="table">
                    <thead><tr><th>Username</th><th>Groups</th><th>Total</th><th>Used</th><th>Left</th><th>Reset Freq</th><th>Reset Dates</th></tr></thead>
                    <tbody>
                      {userRows.map((row, idx) => {
                        let total = 0, available = 0
                        const freqs = new Set<string>()
                        const dates = new Set<string>()
                        for (const [group, info] of Object.entries(row.users_credits || {})) {
                          const tmap = defs[group] || {}
                          const meta = tmap[(info as any).tier_name] || { credits: 0, reset_frequency: undefined }
                          total += Number(meta.credits || 0)
                          available += Number((info as any).available_credits || 0)
                          if (meta.reset_frequency) freqs.add(meta.reset_frequency)
                          const rd = (info as any).reset_date
                          if (rd) dates.add(String(rd))
                        }
                        const used = total > 0 ? Math.max(total - available, 0) : 0
                        return (
                          <tr
                            key={idx}
                            className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover cursor-pointer"
                            onClick={() => router.push(`/credits/${encodeURIComponent(row.username)}`)}
                          >
                            <td className="font-medium">{row.username}</td>
                            <td className="text-sm text-gray-600">{Object.keys(row.users_credits || {}).join(', ') || '-'}</td>
                            <td className="text-sm">{total || 0}</td>
                            <td className="text-sm">{used}</td>
                            <td className="text-sm">{available || 0}</td>
                            <td className="text-sm">{freqs.size ? Array.from(freqs).join(', ') : '-'}</td>
                            <td className="text-sm">{dates.size ? Array.from(dates).join(', ') : '-'}</td>
                          </tr>
                        )
                      })}
                      {userRows.length === 0 && (
                        <tr><td colSpan={7} className="text-gray-500 text-center py-6">No user token records</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
              <Pagination
                page={usersPage}
                pageSize={usersPageSize}
                onPageChange={setUsersPage}
                onPageSizeChange={(s) => { setUsersPageSize(s); setUsersPage(1) }}
                hasNext={usersHasNext}
              />
              <div className="mt-2"><button onClick={loadAllUserTokens} className="btn btn-secondary">Refresh</button></div>
            </div>
          </div>
        </div>
      </div>

    </Layout>
    </ProtectedRoute>
  )
}
