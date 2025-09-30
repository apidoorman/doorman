'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

interface AccessDeniedNotificationProps {
  requiredPermission?: string
}

export function AccessDeniedNotification({ requiredPermission }: AccessDeniedNotificationProps) {
  const { canAccessPage } = useAuth()
  const [showNotification, setShowNotification] = useState(false)

  useEffect(() => {
    if (requiredPermission && !canAccessPage(requiredPermission)) {
      setShowNotification(true)
      // Auto-hide after 5 seconds
      const timer = setTimeout(() => setShowNotification(false), 5000)
      return () => clearTimeout(timer)
    }
  }, [requiredPermission, canAccessPage])

  if (!showNotification) return null

  const permissionMessages: Record<string, string> = {
    'manage_users': 'User Management',
    'manage_apis': 'API Management',
    'manage_endpoints': 'Endpoint Management',
    'manage_groups': 'Group Management',
    'manage_roles': 'Role Management',
    'manage_routings': 'Routing Management',
    'manage_gateway': 'Gateway Management',
    'manage_subscriptions': 'Subscription Management',
    'view_logs': 'Log Viewing',
    'export_logs': 'Log Export'
  }

  const permissionName = permissionMessages[requiredPermission!] || requiredPermission

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm w-full">
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 shadow-lg">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400 dark:text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
              Access Denied
            </h3>
            <div className="mt-2 text-sm text-red-700 dark:text-red-300">
              <p>You don't have permission to access this feature.</p>
              <p className="mt-1">
                Required: <span className="font-medium">{permissionName}</span>
              </p>
            </div>
          </div>
          <div className="ml-auto pl-3">
            <div className="-mx-1.5 -my-1.5">
              <button
                onClick={() => setShowNotification(false)}
                className="inline-flex rounded-md p-1.5 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 focus:outline-none focus:ring-2 focus:ring-red-600 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
              >
                <span className="sr-only">Dismiss</span>
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}