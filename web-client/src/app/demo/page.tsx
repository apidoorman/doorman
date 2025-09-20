'use client'

import React, { useState } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { SERVER_URL } from '@/utils/config'
import { fetchJson } from '@/utils/http'

export default function DemoSeedPage() {
  const [users, setUsers] = useState(60)
  const [apis, setApis] = useState(20)
  const [endpoints, setEndpoints] = useState(6)
  const [groups, setGroups] = useState(10)
  const [protos, setProtos] = useState(6)
  const [logs, setLogs] = useState(2000)
  const [seed, setSeed] = useState<string>('')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)

  const run = async () => {
    try {
      setWorking(true); setError(null); setResult(null)
      const params = new URLSearchParams({
        users: String(users), apis: String(apis), endpoints: String(endpoints), groups: String(groups), protos: String(protos), logs: String(logs)
      })
      if (seed.trim()) params.set('seed', seed.trim())
      const url = `${SERVER_URL}/platform/demo/seed?${params.toString()}`
      const res = await fetchJson<any>(url, { method: 'POST' })
      setResult(res)
    } catch (e:any) {
      setError(e?.message || 'Failed to seed demo data')
    } finally {
      setWorking(false)
    }
  }

  return (
    <ProtectedRoute requiredPermission="manage_gateway">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Demo Data Seeder</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Populate the running server with demo users, APIs, endpoints, tokens, logs, and metrics</p>
            </div>
            <button className="btn btn-primary" onClick={run} disabled={working}>{working ? 'Seeding…' : 'Run Seeder'}</button>
          </div>

          <div className="card">
            <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium">Users</label>
                <input className="input" type="number" value={users} onChange={e => setUsers(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="block text-sm font-medium">APIs</label>
                <input className="input" type="number" value={apis} onChange={e => setApis(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="block text-sm font-medium">Endpoints / API</label>
                <input className="input" type="number" value={endpoints} onChange={e => setEndpoints(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="block text-sm font-medium">Groups</label>
                <input className="input" type="number" value={groups} onChange={e => setGroups(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="block text-sm font-medium">Protos</label>
                <input className="input" type="number" value={protos} onChange={e => setProtos(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="block text-sm font-medium">Logs</label>
                <input className="input" type="number" value={logs} onChange={e => setLogs(Number(e.target.value || 0))} />
              </div>
              <div className="md:col-span-3">
                <label className="block text-sm font-medium">RNG Seed (optional)</label>
                <input className="input" value={seed} onChange={e => setSeed(e.target.value)} placeholder="e.g. 12345" />
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
              <div className="flex">
                <svg className="h-5 w-5 text-error-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="ml-3"><p className="text-sm text-error-700">{error}</p></div>
              </div>
            </div>
          )}

          {result && (
            <div className="card">
              <div className="card-header"><h3 className="card-title">Seed Results</h3></div>
              <div className="p-6">
                <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
              </div>
            </div>
          )}
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

