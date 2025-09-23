'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { 
  isAuthenticated, 
  canAccessUI, 
  canAccessPage, 
  getCurrentUser, 
  getUserPermissions,
  getTokenFromCookie,
  isTokenValid,
  hasUIAccess,
  isUserActive
} from '@/utils/auth'

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

  const checkAuth = () => {
    const token = getTokenFromCookie()
    console.log('=== AUTH CONTEXT DEBUG ===')
    console.log('AuthContext checkAuth - token found:', !!token)
    console.log('AuthContext checkAuth - token value:', token ? token.substring(0, 20) + '...' : 'None')
    console.log('AuthContext checkAuth - all cookies:', document.cookie)
    
    if (!token) {
      console.log('AuthContext - No token found, setting unauthenticated state')
      setAuthState({
        isAuthenticated: false,
        hasUIAccess: false,
        user: null,
        permissions: null
      })
      return
    }

    const tokenValid = isTokenValid(token)
    const uiAccess = hasUIAccess(token)
    const user = getCurrentUser(token)
    const permissions = getUserPermissions(token)

    console.log('AuthContext - Token validation results:', {
      tokenValid,
      uiAccess,
      user: user?.username,
      hasPermissions: !!permissions,
      permissions: permissions
    })

    console.log('AuthContext - Setting auth state:', {
      isAuthenticated: tokenValid,
      hasUIAccess: tokenValid && uiAccess,
      user,
      permissions
    })

    setAuthState({
      isAuthenticated: tokenValid,
      hasUIAccess: tokenValid && uiAccess,
      user,
      permissions
    })

    // If authenticated but no UI access, redirect to login
    if (tokenValid && !uiAccess) {
      console.log('AuthContext - User authenticated but no UI access, logging out')
      logout()
    }
  }

  const logout = () => {
    document.cookie = 'access_token_cookie=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
    setAuthState({
      isAuthenticated: false,
      hasUIAccess: false,
      user: null,
      permissions: null
    })
    router.push('/login')
  }

  const canAccessPagePermission = (permission: string) => {
    const token = getTokenFromCookie()
    return token ? canAccessPage(permission as any) : false
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