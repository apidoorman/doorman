'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function Home() {
  const router = useRouter()

  // TODO: Check session. If session is valid, redirect to dashboard. If not, redirect to login.
  useEffect(() => {
    router.push('/login')
  }, [router])

  return null
}