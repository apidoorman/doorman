'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson, putJson, delJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ConfirmModal from '@/components/ConfirmModal'

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
  const [usersPage, setUsersPage] = useState(1)
  const [usersPageSize, setUsersPageSize] = useState(10)
  const [usersHasNext, setUsersHasNext] = useState(false)
  const [selectedUser, setSelectedUser] = useState('')
  const [userDetail, setUserDetail] = useState<UserCreditsRow | null>(null)
  const [userWorking, setUserWorking] = useState(false)
  const [userError, setUserError] = useState<string | null>(null)
  const [userSuccess, setUserSuccess] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

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

  const openDeleteModal = () => {
    if (!form.api_credit_group.trim()) {
      setForm(f => ({ ...f, error: 'Credit group is required' }));
      return;
    }
    setShowDeleteModal(true)
  }

  const handleDeleteConfirm = async () => {
    if (deleteConfirmation !== form.api_credit_group.trim()) return
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      if (!form.api_credit_group.trim()) throw new Error('Credit group is required')
      await delJson(`${SERVER_URL}/platform/credit/${encodeURIComponent(form.api_credit_group.trim())}`)
      setForm(f => ({ ...f, success: 'Credit definition deleted' }))
      setShowDeleteModal(false)
      setDeleteConfirmation('')
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to delete credit definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  const loadAllUserTokens = async () => {
    try {
      setUsersLoading(true); setUserError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/credit/all?page=${usersPage}&page_size=${usersPageSize}`)
      const items = payload?.items || payload?.user_credits || []
      setUserRows(items)
      setUsersHasNext((items || []).length === usersPageSize)
    } catch (e:any) {
      setUserError(e?.message || 'Failed to load user credits')
      setUserRows([])
      setUsersHasNext(false)
    } finally {
      setUsersLoading(false)
    }
  }

  const loadUserTokens = async (username: string) => {
    if (!username.trim()) return
    try {
      setUserError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/credit/${encodeURIComponent(username.trim())}`)
      setUserDetail({ username: username.trim(), users_credits: payload.users_credits || {} })
    } catch (e:any) {
      setUserError(e?.message || 'Failed to load user credits')
      setUserDetail(null)
    }
  }

  const saveUserTokens = async () => {
    if (!userDetail) return
    try {
      setUserWorking(true); setUserError(null); setUserSuccess(null)
      await postJson(`${SERVER_URL}/platform/credit/${encodeURIComponent(userDetail.username)}`, { username: userDetail.username, users_credits: userDetail.users_credits })
      setUserSuccess('User credits saved')
      setTimeout(() => setUserSuccess(null), 2000)
      await loadAllUserTokens()
    } catch (e:any) {
      setUserError(e?.message || 'Failed to save user credits')
    } finally {
      setUserWorking(false)
    }
  }

  useEffect(() => {
    loadAllUserTokens()
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

        {/* Credit Definitions CTA */}
        <div className="card">
          <div className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="card-title">Credit Definitions</h3>
              <p className="text-gray-600 dark:text-gray-400">Create and manage credit groups, headers, and tiers</p>
            </div>
            <div className="flex gap-2">
              <a href="/credit-defs" className="btn btn-secondary">View Definitions</a>
              <a href="/credit-defs/add" className="btn btn-primary">Add Definition</a>
            </div>
          </div>
        </div>

        {/* User Credits */}
        <div className="card">
          <div className="card-header"><h3 className="card-title">User Credits</h3></div>
          <div className="p-6 space-y-4">
            {userError && <div className="text-sm text-error-600">{userError}</div>}
            {userSuccess && <div className="text-sm text-success-600">{userSuccess}</div>}
            <div className="flex gap-2 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium">Username</label>
                <input className="input" value={selectedUser} onChange={e => setSelectedUser(e.target.value)} placeholder="username" />
              </div>
              <button className="btn btn-secondary" onClick={() => loadUserTokens(selectedUser)}>Load</button>
            </div>
            {userDetail && (
              <div className="space-y-3">
                <div className="text-sm text-gray-600">Editing credits for <span className="font-medium">{userDetail.username}</span></div>
                <div className="space-y-2">
                  {Object.entries(userDetail.users_credits).map(([group, info]) => (
                    <div key={group} className="flex items-center gap-2">
                      <span className="badge badge-gray min-w-[8rem]">{group}</span>
                      <input className="input w-28" type="number" value={info.available_credits}
                        onChange={e => setUserDetail(prev => prev ? ({ ...prev, users_credits: { ...prev.users_credits, [group]: { ...prev.users_credits[group], available_credits: Number(e.target.value || 0) } } }) : prev)} />
                      <input className="input flex-1" placeholder="user API key (optional)" value={info.user_api_key || ''}
                        onChange={e => setUserDetail(prev => prev ? ({ ...prev, users_credits: { ...prev.users_credits, [group]: { ...prev.users_credits[group], user_api_key: e.target.value } } }) : prev)} />
                    </div>
                  ))}
                  <button className="btn btn-secondary" onClick={() => setUserDetail(prev => prev ? ({ ...prev, users_credits: { ...prev.users_credits, 'new-group': { tier_name: 'basic', available_credits: 0 } } }) : prev)}>Add Group</button>
                </div>
                <div>
                  <button className="btn btn-primary" disabled={userWorking} onClick={saveUserTokens}>{userWorking ? 'Saving...' : 'Save Credits'}</button>
                </div>
              </div>
            )}

            <div className="mt-6">
              <div className="text-sm font-medium mb-2">All Users (paged)</div>
              {usersLoading ? (
                <div className="text-gray-500">Loading...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="table">
                    <thead><tr><th>Username</th><th>Groups</th></tr></thead>
                    <tbody>
                      {userRows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-dark-surfaceHover">
                          <td className="font-medium">{row.username}</td>
                          <td className="text-sm text-gray-600">
                            {Object.keys(row.users_credits || {}).join(', ') || '-'}
                          </td>
                        </tr>
                      ))}
                      {userRows.length === 0 && (
                        <tr><td colSpan={2} className="text-gray-500 text-center py-6">No user token records</td></tr>
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

      {/* No delete modal needed on this page anymore */}
    </Layout>
    </ProtectedRoute>
  )
}
