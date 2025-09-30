'use client'

import React, { useState } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { SERVER_URL } from '@/utils/config'

export default function ReportsPage() {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const preset = (hours: number) => {
    const now = new Date()
    const startDate = new Date(now.getTime() - hours * 3600 * 1000)
    const toStr = (d: Date) => d.toISOString().slice(0,16)
    setStart(toStr(startDate))
    setEnd(toStr(now))
  }

  const generate = async () => {
    try {
      setError(null); setDownloading(true)
      if (!start || !end) throw new Error('Please select a start and end date/time')
      const url = `${SERVER_URL}/platform/monitor/report?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
      const resp = await fetch(url, { credentials: 'include' })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({} as any))
        const msg = (data && (data.error_message || data.message)) || resp.statusText
        throw new Error(msg)
      }
      const blob = await resp.blob()
      const a = document.createElement('a')
      const href = URL.createObjectURL(blob)
      a.href = href
      a.download = `doorman_report_${start}_to_${end}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(href)
    } catch (e:any) {
      setError(e?.message || 'Failed to generate report')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <ProtectedRoute requiredPermission="manage_gateway">
      <Layout>
        <div className="space-y-6">
          <div className="page-header">
            <div>
              <h1 className="page-title">Reports</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">Export operational metrics to CSV for analysis</p>
            </div>
          </div>

          {error && <div className="rounded-md bg-error-50 border border-error-200 p-3 text-error-700 text-sm">{error}</div>}

          <div className="card">
            <div className="card-header"><h3 className="card-title">Generate Report</h3></div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium">Start (UTC)</label>
                  <input type="datetime-local" className="input" value={start} onChange={e => setStart(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm font-medium">End (UTC)</label>
                  <input type="datetime-local" className="input" value={end} onChange={e => setEnd(e.target.value)} />
                </div>
                <div className="flex items-end gap-2">
                  <button className="btn btn-secondary" onClick={() => preset(1)}>Last 1h</button>
                  <button className="btn btn-secondary" onClick={() => preset(24)}>Last 24h</button>
                  <button className="btn btn-secondary" onClick={() => preset(24*7)}>Last 7d</button>
                </div>
              </div>
              <div>
                <button className="btn btn-primary" onClick={generate} disabled={downloading}>{downloading ? 'Generating…' : 'Download CSV'}</button>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                The CSV includes overview, status code distribution, per-API usage (success/failure), and per-user request counts for the selected range.
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}

