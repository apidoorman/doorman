'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import {
  isAuthenticated,
  canAccessUI,
  canAccessPage,
  getCurrentUser,
  getUserPermissions,
  isTokenValid,
  hasUIAccess,
  isUserActive
} from '@/utils/auth'
import { fetchJson } from '@/utils/http'
import { SERVER_URL } from '@/utils/config'

interface AuthContextType {
  isAuthenticated: boolean
  hasUIAccess: boolean
  user: { username: string; role: string } | null
  permissions: any
  canAccessPage: (permission: string) => boolean
  logout: () => void
  checkAuth: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState({
    isAuthenticated: false,
    hasUIAccess: false,
    user: null as { username: string; role: string } | null,
    permissions: null as any
  })
  const router = useRouter()

  const checkAuth = async () => {
    console.log('=== AUTH CONTEXT DEBUG ===')
    try {
      // Validate via backend using HttpOnly cookie (no client-side token reads)
      await fetchJson(`${SERVER_URL}/platform/authorization/status`)

      // If we reach here, token is valid
      let user = null as any
      let permissions: any = null
      try {
        user = await fetchJson(`${SERVER_URL}/platform/user/me`)
        if (user?.role) {
          try {
            const role = await fetchJson(`${SERVER_URL}/platform/role/${encodeURIComponent(user.role)}`)
            // Role object is expected to contain permission booleans
            permissions = role || null
          } catch {}
        }
      } catch {}

      setAuthState({
        isAuthenticated: true,
        hasUIAccess: true,
        user,
        permissions
      })
    } catch (error) {
      console.warn('AuthContext - Not authenticated or status check failed:', error)
      setAuthState({
        isAuthenticated: false,
        hasUIAccess: false,
        user: null,
        permissions: null
      })
    }
  }

  const logout = async () => {
    try {
      await fetch(`${SERVER_URL}/platform/authorization/invalidate`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      })
    } catch (e) {
      console.warn('Logout invalidate failed (continuing):', e)
    }
    setAuthState({
      isAuthenticated: false,
      hasUIAccess: false,
      user: null,
      permissions: null
    })
    router.push('/login')
  }

  const canAccessPagePermission = (permission: string) => {
    return !!(authState.isAuthenticated && authState.permissions && authState.permissions[permission])
  }

  useEffect(() => {
    // Initial auth check with a small delay to ensure cookies are set after login
    const timer = setTimeout(() => {
      console.log('AuthContext - Initial auth check')
      checkAuth()
    }, 200)
    
    // Check auth every minute
    const interval = setInterval(() => {
      console.log('AuthContext - Periodic auth check')
      checkAuth()
    }, 60000)
    
    return () => {
      clearTimeout(timer)
      clearInterval(interval)
    }
  }, [])

  const value: AuthContextType = {
    isAuthenticated: authState.isAuthenticated,
    hasUIAccess: authState.hasUIAccess,
    user: authState.user,
    permissions: authState.permissions,
    canAccessPage: canAccessPagePermission,
    logout,
    checkAuth
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
} 
