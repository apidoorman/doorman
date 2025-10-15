'use client'

import React, { ReactNode, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface ProtectedRouteProps {
  children: ReactNode
  requiredPermission?: string
  fallback?: ReactNode
}

export function ProtectedRoute({
  children,
  requiredPermission,
  fallback
}: ProtectedRouteProps) {
  const DEBUG = process.env.NODE_ENV !== 'production'
  const { isAuthenticated, hasUIAccess, canAccessPage } = useAuth()
  const router = useRouter()
  const [redirecting, setRedirecting] = useState(false)

  useEffect(() => {
    if (redirecting) return;

    if (!isAuthenticated || !hasUIAccess) {
      setRedirecting(true);
      if (DEBUG) console.log('ProtectedRoute - Redirecting to login:', { isAuthenticated, hasUIAccess })
      router.push('/login')
      return
    }
  }, [isAuthenticated, hasUIAccess, router, redirecting])

  if (redirecting) {
    return fallback || (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Redirecting...
            </h2>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return fallback || (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Authentication Required
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              Please log in to access this page.
            </p>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!hasUIAccess) {
    return fallback || (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              UI Access Denied
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              You do not have permission to access the web interface.
            </p>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          </div>
        </div>
      </div>
    )
  }

  if (requiredPermission && !canAccessPage(requiredPermission)) {
    const permissionMessages: Record<string, string> = {
      'manage_users': 'User Management',
      'manage_apis': 'API Management',
      'manage_endpoints': 'Endpoint Management',
      'manage_groups': 'Group Management',
      'manage_roles': 'Role Management',
      'manage_routings': 'Routing Management',
      'manage_gateway': 'Gateway Management',
      'manage_subscriptions': 'Subscription Management',
      'manage_security': 'Security Management'
    }

    const permissionName = permissionMessages[requiredPermission] || requiredPermission

    return fallback || (
      <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-6">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900 mb-4">
              <svg className="h-6 w-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              Access Denied
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-2">
              You don't have permission to access this page.
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              Required permission: <span className="font-medium">{permissionName}</span>
            </p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => router.back()}
                className="bg-gray-600 hover:bg-gray-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                Go Back
              </button>
              <button
                onClick={() => router.push('/dashboard')}
                className="bg-primary-600 hover:bg-primary-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
              >
                Dashboard
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
