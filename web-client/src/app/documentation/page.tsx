'use client'

import React from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'

export default function DocumentationPage() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const docsUrl = `${backendUrl}/platform/docs`

  return (
    <ProtectedRoute>
      <Layout>
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">API Documentation</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Interactive API documentation powered by Swagger UI
            </p>
          </div>

          <div className="bg-white dark:bg-dark-surface rounded-lg shadow-sm border border-gray-200 dark:border-white/[0.08] overflow-hidden">
            <iframe
              src={docsUrl}
              className="w-full border-0"
              style={{ height: 'calc(100vh - 200px)', minHeight: '600px' }}
              title="API Documentation"
            />
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300">
                  About this documentation
                </h3>
                <div className="mt-2 text-sm text-blue-700 dark:text-blue-400">
                  <p>
                    This interactive documentation is automatically generated from the Doorman API endpoints.
                    You can explore all available endpoints, view request/response schemas, and even test API calls directly from this interface.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
