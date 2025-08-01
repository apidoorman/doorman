'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated, hasUIAccess } = useAuth()

  useEffect(() => {
    // Check if user is authenticated and has UI access
    if (isAuthenticated && hasUIAccess) {
      router.push('/dashboard')
    } else {
      router.push('/login')
    }
  }, [isAuthenticated, hasUIAccess, router])

  return null
}