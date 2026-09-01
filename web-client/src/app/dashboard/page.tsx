'use client'

import React, { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { SERVER_URL } from '@/utils/config'
import { useAuth } from '@/contexts/AuthContext'
import { SignalMetric, SignalPageHeader, SignalPanel, SignalSidebarRail, SignalStatusTag, SignalTable } from '@/components/signal/Signal'

interface DashboardData {
  totalRequests: number
  activeUsers: number
  newApis: number
  monthlyUsage: Record<string, number>
  activeUsersList: Array<{ username: string; requests: string; subscribers: number }>
  popularApis: Array<{ name: string; requests: string; subscribers: number }>
}

const emptyDashboard: DashboardData = { totalRequests: 0, activeUsers: 0, newApis: 0, monthlyUsage: {}, activeUsersList: [], popularApis: [] }
const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function Dashboard() {
  const { isAuthenticated, hasUIAccess } = useAuth()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dashboardData, setDashboardData] = useState<DashboardData>(emptyDashboard)

  const fetchData = async () => {
    try {
      setLoading(true); setError(null)
      const { fetchJson } = await import('@/utils/http')
      setDashboardData(await fetchJson<DashboardData>(`${SERVER_URL}/platform/dashboard`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally { setLoading(false) }
  }

  useEffect(() => { if (isAuthenticated && hasUIAccess) fetchData() }, [isAuthenticated, hasUIAccess])
  const values = months.map(month => dashboardData.monthlyUsage[month] || 0)
  const maxValue = Math.max(...values, 1)

  return <ProtectedRoute><Layout><div className="space-y-7">
    <SignalPageHeader kicker="Gateway overview" title={<>API<br className="sm:hidden" /> Gateway.</>} description="Live configuration, traffic, and access-control signals from this Doorman deployment." actions={<button onClick={fetchData} disabled={loading} className="signal-button">{loading ? 'Refreshing' : 'Refresh data'}</button>} />
    {error && <SignalPanel tone="terracotta" title="Gateway data unavailable"><p className="font-mono text-sm">{error}</p></SignalPanel>}
    {loading ? <SignalPanel tone="blue" title="Reading gateway telemetry"><p className="font-mono text-sm">Loading live configuration and usage data…</p></SignalPanel> : <>
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_300px]">
        <SignalPanel tone="white" title="API Gateway" kicker="Traffic health"><div className="grid gap-3 sm:grid-cols-2"><SignalMetric label="Total requests" value={dashboardData.totalRequests.toLocaleString()} tone="lime" detail="Reported by gateway dashboard" /><SignalMetric label="Active users" value={dashboardData.activeUsers.toLocaleString()} tone="blue" detail="Current reporting period" /></div><div className="mt-5 flex items-center justify-between border-t-2 border-signal-ink pt-4"><span className="font-mono text-xs uppercase tracking-wide">Route activity</span><SignalStatusTag status="healthy">Live data</SignalStatusTag></div></SignalPanel>
        <SignalPanel tone="terracotta" title="AI service posture" kicker="Protocol capability"><div className="grid gap-3 sm:grid-cols-2"><SignalMetric label="New API definitions" value={dashboardData.newApis.toLocaleString()} tone="white" detail="Current reporting period" /><div className="border-[3px] border-signal-ink bg-white p-4"><p className="font-mono text-[11px] font-bold uppercase tracking-[.08em]">Configured traffic</p><p className="mt-5 text-2xl font-extrabold tracking-tight">REST · GraphQL<br />gRPC · SOAP</p><p className="mt-3 font-mono text-xs text-signal-mist">Use API configuration to govern supported service traffic.</p></div></div></SignalPanel>
        <SignalSidebarRail title="System assurance"><h2 className="mt-2 text-2xl font-extrabold tracking-tight">Gateway ready.</h2><ul className="mt-4 list-none p-0"><li><SignalStatusTag status="healthy">Healthy</SignalStatusTag></li><li>Apache 2.0 licensed</li><li>Self-hosted control plane</li><li>Cloud or private network</li><li>Multi-protocol gateway</li><li>Built-in auth and policy</li></ul></SignalSidebarRail>
      </section>
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.8fr)]">
        <SignalPanel tone="white" title="Request volume" kicker="Deployment summary"><div className="flex h-64 items-end gap-2 border-b-[3px] border-signal-ink px-2 pb-8">{months.map(month => { const value = dashboardData.monthlyUsage[month] || 0; return <div key={month} className="group flex h-full flex-1 flex-col justify-end"><div className="bg-signal-lime border-[2px] border-signal-ink transition-colors group-hover:bg-signal-terra" style={{ height: `${Math.max((value / maxValue) * 190, 4)}px` }} title={`${month}: ${value}`} /><span className="mt-2 text-center font-mono text-[10px] text-signal-mist">{month}</span></div> })}</div></SignalPanel>
        <SignalPanel tone="blue" title="Active users" kicker="Access activity"><div className="divide-y-2 divide-signal-ink">{dashboardData.activeUsersList.length ? dashboardData.activeUsersList.map(user => <div className="py-3" key={user.username}><p className="font-bold">{user.username}</p><p className="mt-1 font-mono text-xs text-signal-mist">{user.requests} requests · {user.subscribers} subscribers</p></div>) : <p className="font-mono text-sm">No active-user records for this period.</p>}</div></SignalPanel>
      </section>
      <SignalPanel tone="white" title="Popular APIs" kicker="Route activity"><SignalTable><thead><tr><th>API</th><th>Requests</th><th>Subscribers</th></tr></thead><tbody>{dashboardData.popularApis.length ? dashboardData.popularApis.map(api => <tr key={api.name}><td data-label="API" className="font-bold">{api.name}</td><td data-label="Requests">{api.requests}</td><td data-label="Subscribers">{api.subscribers}</td></tr>) : <tr><td colSpan={3} className="text-center font-mono">No API activity for this period.</td></tr>}</tbody></SignalTable></SignalPanel>
    </>}
  </div></Layout></ProtectedRoute>
}

export default Dashboard
