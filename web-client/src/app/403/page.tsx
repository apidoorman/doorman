'use client'

import React from 'react'
import Link from 'next/link'
import Layout from '@/components/Layout'

export default function ForbiddenPage() {
  return (
    <Layout>
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="max-w-md w-full bg-white dark:bg-dark-surface border border-gray-200 dark:border-white/10 rounded-lg p-8 text-center shadow-sm">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/20 mb-4">
            <svg className="h-6 w-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white mb-2">403 — Forbidden</h1>
          <p className="text-gray-600 dark:text-gray-300 mb-6">You do not have permission to access the admin UI.</p>
          <div className="flex gap-3 justify-center">
            <Link href="/login" className="btn btn-secondary">
              Back to Login
            </Link>
            <Link href="/" className="btn btn-outline">
              Home
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  )
}
