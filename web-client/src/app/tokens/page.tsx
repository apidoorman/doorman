'use client'

import React, { useEffect, useMemo, useState } from 'react'
import Layout from '@/components/Layout'
import Pagination from '@/components/Pagination'
import { SERVER_URL } from '@/utils/config'
import { getJson, postJson, putJson, delJson } from '@/utils/api'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import ConfirmModal from '@/components/ConfirmModal'

interface TokenTier {
  tier_name: string
  tokens: number
  input_limit: number
  output_limit: number
  reset_frequency: string
}

interface TokenDefForm {
  api_token_group: string
  api_key: string
  api_key_header: string
  token_tiers_text: string
  working: boolean
  error: string | null
  success: string | null
}

interface UserTokenInfo {
  tier_name: string
  available_tokens: number
  reset_date?: string
  user_api_key?: string
}

interface UserTokensRow {
  username: string
  users_tokens: Record<string, UserTokenInfo>
}

export default function TokensPage() {
  const [form, setForm] = useState<TokenDefForm>({
    api_token_group: '',
    api_key: '',
    api_key_header: 'x-api-key',
    token_tiers_text: '[\n  {"tier_name":"basic","tokens":100,"input_limit":150,"output_limit":150,"reset_frequency":"monthly"}\n] ',
    working: false,
    error: null,
    success: null
  })
  const [usersLoading, setUsersLoading] = useState(false)
  const [userRows, setUserRows] = useState<UserTokensRow[]>([])
  const [usersPage, setUsersPage] = useState(1)
  const [usersPageSize, setUsersPageSize] = useState(10)
  const [usersHasNext, setUsersHasNext] = useState(false)
  const [selectedUser, setSelectedUser] = useState('')
  const [userDetail, setUserDetail] = useState<UserTokensRow | null>(null)
  const [userWorking, setUserWorking] = useState(false)
  const [userError, setUserError] = useState<string | null>(null)
  const [userSuccess, setUserSuccess] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

  const parseTiers = (): TokenTier[] => {
    try { return JSON.parse(form.token_tiers_text || '[]') } catch { return [] }
  }

  const handleCreate = async () => {
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      const tiers = parseTiers()
      if (!form.api_token_group.trim()) throw new Error('Token group is required')
      await postJson(`${SERVER_URL}/platform/token`, { api_token_group: form.api_token_group.trim(), api_key: form.api_key, api_key_header: form.api_key_header, token_tiers: tiers })
      setForm(f => ({ ...f, success: 'Token definition created' }))
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to create token definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  const handleUpdate = async () => {
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      const tiers = parseTiers()
      if (!form.api_token_group.trim()) throw new Error('Token group is required')
      await putJson(`${SERVER_URL}/platform/token/${encodeURIComponent(form.api_token_group.trim())}`, { api_token_group: form.api_token_group.trim(), api_key: form.api_key, api_key_header: form.api_key_header, token_tiers: tiers })
      setForm(f => ({ ...f, success: 'Token definition updated' }))
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to update token definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  const openDeleteModal = () => {
    if (!form.api_token_group.trim()) {
      setForm(f => ({ ...f, error: 'Token group is required' }));
      return;
    }
    setShowDeleteModal(true)
  }

  const handleDeleteConfirm = async () => {
    if (deleteConfirmation !== form.api_token_group.trim()) return
    setForm(f => ({ ...f, working: true, error: null, success: null }))
    try {
      if (!form.api_token_group.trim()) throw new Error('Token group is required')
      await delJson(`${SERVER_URL}/platform/token/${encodeURIComponent(form.api_token_group.trim())}`)
      setForm(f => ({ ...f, success: 'Token definition deleted' }))
      setShowDeleteModal(false)
      setDeleteConfirmation('')
    } catch (e:any) {
      setForm(f => ({ ...f, error: e?.message || 'Failed to delete token definition' }))
    } finally {
      setForm(f => ({ ...f, working: false }))
    }
  }

  const loadAllUserTokens = async () => {
    try {
      setUsersLoading(true); setUserError(null)
      const payload = await getJson<any>(`${SERVER_URL}/platform/token/all?page=${usersPage}&page_size=${usersPageSize}`)
      const items = payload?.items || payload?.user_tokens || []
      setUserRows(items)
      setUsersHasNext((items || []).length === usersPageSize)
    } catch (e:any) {
      setUserError(e?.message || 'Failed to load user tokens')
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
      const payload = await getJson<any>(`${SERVER_URL}/platform/token/${encodeURIComponent(username.trim())}`)
      setUserDetail({ username: username.trim(), users_tokens: payload.users_tokens || {} })
    } catch (e:any) {
      setUserError(e?.message || 'Failed to load user tokens')
      setUserDetail(null)
    }
  }

  const saveUserTokens = async () => {
    if (!userDetail) return
    try {
      setUserWorking(true); setUserError(null); setUserSuccess(null)
      await postJson(`${SERVER_URL}/platform/token/${encodeURIComponent(userDetail.username)}`, { username: userDetail.username, users_tokens: userDetail.users_tokens })
      setUserSuccess('User tokens saved')
      setTimeout(() => setUserSuccess(null), 2000)
      await loadAllUserTokens()
    } catch (e:any) {
      setUserError(e?.message || 'Failed to save user tokens')
    } finally {
      setUserWorking(false)
    }
  }

  useEffect(() => {
    loadAllUserTokens()
  }, [usersPage, usersPageSize])

  return (
    <ProtectedRoute requiredPermission="manage_tokens">
    <Layout>
      <div className="space-y-6">
        <div className="page-header">
          <div>
            <h1 className="page-title">Tokens</h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">Manage token definitions and user token balances</p>
          </div>
        </div>

        {/* Token Definition */}
        <div className="card">
          <div className="card-header"><h3 className="card-title">Token Definition</h3></div>
          <div className="p-6 space-y-4">
            {form.error && <div className="text-sm text-error-600">{form.error}</div>}
            {form.success && <div className="text-sm text-success-600">{form.success}</div>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium">API Token Group</label>
                <input className="input" value={form.api_token_group} onChange={e => setForm(f => ({ ...f, api_token_group: e.target.value }))} placeholder="ai-group-1" />
              </div>
              <div>
                <label className="block text-sm font-medium">API Key Header</label>
                <input className="input" value={form.api_key_header} onChange={e => setForm(f => ({ ...f, api_key_header: e.target.value }))} placeholder="x-api-key" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium">API Key</label>
                <input className="input" value={form.api_key} onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))} placeholder="sk_live_xxx" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium">Token Tiers (JSON)</label>
                <textarea className="input font-mono text-xs h-40" value={form.token_tiers_text} onChange={e => setForm(f => ({ ...f, token_tiers_text: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleCreate} disabled={form.working} className="btn btn-primary">Create</button>
              <button onClick={handleUpdate} disabled={form.working} className="btn btn-secondary">Update</button>
              <button onClick={openDeleteModal} disabled={form.working} className="btn btn-error">Delete</button>
            </div>
          </div>
        </div>

        {/* User Tokens */}
        <div className="card">
          <div className="card-header"><h3 className="card-title">User Tokens</h3></div>
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
                <div className="text-sm text-gray-600">Editing tokens for <span className="font-medium">{userDetail.username}</span></div>
                <div className="space-y-2">
                  {Object.entries(userDetail.users_tokens).map(([group, info]) => (
                    <div key={group} className="flex items-center gap-2">
                      <span className="badge badge-gray min-w-[8rem]">{group}</span>
                      <input className="input w-28" type="number" value={info.available_tokens}
                        onChange={e => setUserDetail(prev => prev ? ({ ...prev, users_tokens: { ...prev.users_tokens, [group]: { ...prev.users_tokens[group], available_tokens: Number(e.target.value || 0) } } }) : prev)} />
                      <input className="input flex-1" placeholder="user API key (optional)" value={info.user_api_key || ''}
                        onChange={e => setUserDetail(prev => prev ? ({ ...prev, users_tokens: { ...prev.users_tokens, [group]: { ...prev.users_tokens[group], user_api_key: e.target.value } } }) : prev)} />
                    </div>
                  ))}
                  <button className="btn btn-secondary" onClick={() => setUserDetail(prev => prev ? ({ ...prev, users_tokens: { ...prev.users_tokens, 'new-group': { tier_name: 'basic', available_tokens: 0 } } }) : prev)}>Add Group</button>
                </div>
                <div>
                  <button className="btn btn-primary" disabled={userWorking} onClick={saveUserTokens}>{userWorking ? 'Saving...' : 'Save Tokens'}</button>
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
                            {Object.keys(row.users_tokens || {}).join(', ') || '-'}
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

      <ConfirmModal
        open={showDeleteModal}
        title="Delete Token Definition"
        message={<>
          This action cannot be undone. This will permanently delete the token definition for group "{form.api_token_group.trim()}".
        </>}
        confirmLabel={form.working ? 'Deleting...' : 'Delete'}
        cancelLabel="Cancel"
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={handleDeleteConfirm}
      />
    </Layout>
    </ProtectedRoute>
  )
}
