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
import { postJson } from '@/utils/api'
import { SERVER_URL } from '@/utils/config'

const DEBUG = process.env.NODE_ENV !== 'production'

interface AuthContextType {
  isAuthenticated: boolean
  hasUIAccess: boolean
  user: { username: string; role: string } | null
  permissions: any
  canAccessPage: (permission: string) => boolean
  logout: () => void
  checkAuth: () => void
  refreshAuth: () => Promise<void>
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
    if (DEBUG) console.log('=== AUTH CONTEXT DEBUG ===')
    try {
      await fetchJson(`${SERVER_URL}/platform/authorization/status`)

      let user = null as any
      let permissions: any = null
      try {
        user = await fetchJson(`${SERVER_URL}/platform/user/me`)
        if (user?.role) {
          try {
            const role = await fetchJson(`${SERVER_URL}/platform/role/${encodeURIComponent(user.role)}`)
            permissions = role || null
          } catch {}
        }
      } catch {}

      setAuthState({
        isAuthenticated: true,
        hasUIAccess: !!(user && user.ui_access === true),
        user,
        permissions
      })
    } catch (error) {
      if (DEBUG) console.warn('AuthContext - Not authenticated or status check failed:', error)
      setAuthState({
        isAuthenticated: false,
        hasUIAccess: false,
        user: null,
        permissions: null
      })
    }
  }

  const refreshAuth = async () => {
    try {
      await postJson(`${SERVER_URL}/platform/authorization/refresh`, {})
      await checkAuth()
    } catch (e) {
      if (DEBUG) console.warn('AuthContext - Token refresh failed or not applicable:', e)
    }
  }

  const logout = async () => {
    try {
      await postJson(`${SERVER_URL}/platform/authorization/invalidate`, {})
    } catch (e) {
      if (DEBUG) console.warn('Logout invalidate failed (continuing):', e)
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
    const timer = setTimeout(() => {
      if (DEBUG) console.log('AuthContext - Initial auth check')
      checkAuth()
    }, 200)

    const interval = setInterval(() => {
      if (DEBUG) console.log('AuthContext - Periodic auth check')
      checkAuth()
    }, 60000)

    const refreshInterval = setInterval(() => {
      if (authState.isAuthenticated) {
        if (DEBUG) console.log('AuthContext - Proactive token refresh')
        refreshAuth()
      }
    }, 10 * 60 * 1000)

    return () => {
      clearTimeout(timer)
      clearInterval(interval)
      clearInterval(refreshInterval)
    }
  }, [])

  const value: AuthContextType = {
    isAuthenticated: authState.isAuthenticated,
    hasUIAccess: authState.hasUIAccess,
    user: authState.user,
    permissions: authState.permissions,
    canAccessPage: canAccessPagePermission,
    logout,
    checkAuth,
    refreshAuth
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
