'use client'

import React, { useState } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import OpenApiViewer from '@/components/OpenApiViewer'
import { SERVER_URL } from '@/utils/config'

const TabButton: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({ active, onClick, children }) => (
  <button
    onClick={onClick}
    className={
      'relative px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:rounded-md ' +
      (active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-white/70 hover:text-gray-900 dark:hover:text-white')
    }
  >
    {children}
    <span className={'absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-all ' + (active ? 'bg-blue-600 dark:bg-blue-400' : 'bg-transparent')} />
  </button>
)

export default function ApiReferencePage() {
  const redocUrl = `${SERVER_URL}/platform/redoc`
  const swaggerUrl = `${SERVER_URL}/platform/docs`
  const openapiUrl = `${SERVER_URL}/platform/openapi.json`
  const [active, setActive] = useState<'branded' | 'redoc' | 'swagger'>('branded')

  return (
    <ProtectedRoute>
      <Layout>
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">API Reference</h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Generated live from the gateway’s OpenAPI spec</p>
            </div>
          </div>

          <div>
            <div role="tablist" className="-mb-px flex gap-2 overflow-x-auto no-scrollbar border-b border-gray-200 dark:border-white/10">
              <TabButton active={active === 'branded'} onClick={() => setActive('branded')}>Branded</TabButton>
              <TabButton active={active === 'redoc'} onClick={() => setActive('redoc')}>Redoc</TabButton>
              <TabButton active={active === 'swagger'} onClick={() => setActive('swagger')}>Swagger UI</TabButton>
            </div>

            <div className="relative rounded-lg border border-gray-200 dark:border-white/10 bg-white dark:bg-dark-surface shadow-sm overflow-hidden p-4">
              {active === 'branded' && (
                <OpenApiViewer openapiUrl={openapiUrl} />
              )}
              {active === 'redoc' && (
                <iframe title="Redoc" src={redocUrl} className="w-full" style={{ minHeight: 'calc(100vh - 220px)', border: '0' }} />
              )}
              {active === 'swagger' && (
                <iframe title="Swagger UI" src={swaggerUrl} className="w-full" style={{ minHeight: 'calc(100vh - 220px)', border: '0' }} />
              )}
            </div>
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
