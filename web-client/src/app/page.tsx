'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated, authResolved, hasUIAccess } = useAuth()

  useEffect(() => {
    if (!authResolved) {
      return
    }
    if (isAuthenticated && hasUIAccess) {
      router.push('/dashboard')
    } else {
      router.push('/login')
    }
  }, [authResolved, isAuthenticated, hasUIAccess, router])

  return null
}
