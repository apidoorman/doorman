'use client'

import React, { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuth } from '@/contexts/AuthContext'

export default function SubscriptionsPage() {
  const router = useRouter()
  const { user } = useAuth()

  useEffect(() => {
    if (user?.username) {
      router.replace(`/authorizations/${encodeURIComponent(user.username)}`)
    } else {
      const t = setTimeout(() => {
        if (user?.username) router.replace(`/authorizations/${encodeURIComponent(user.username)}`)
      }, 300)
      return () => clearTimeout(t)
    }
  }, [user?.username])

  return (
    <ProtectedRoute requiredPermission="manage_subscriptions">
      <div className="p-6 text-gray-600 dark:text-gray-300">Redirecting to your Authorizations…</div>
    </ProtectedRoute>
  )
}
