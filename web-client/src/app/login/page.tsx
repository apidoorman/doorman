'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { SERVER_URL } from '@/utils/config'
import { postJson, getJson } from '@/utils/api'

const LoginPage = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [theme, setTheme] = useState('light')
  const router = useRouter()
  const { checkAuth, isAuthenticated, hasUIAccess } = useAuth()

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    setTheme(savedTheme)
    document.documentElement.classList.toggle('dark', savedTheme === 'dark')
  }, [])

  useEffect(() => {
    if (isAuthenticated && hasUIAccess) {
      router.push('/dashboard')
    } else if (isAuthenticated && !hasUIAccess) {
      // Authenticated but not allowed to use UI
      setErrorMessage('Your account does not have UI access. Contact an administrator.')
      try { void postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch {}
      try {
        localStorage.clear(); sessionStorage.clear()
        // Attempt to clear non-HttpOnly cookie (best-effort)
        document.cookie = 'access_token_cookie=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
      } catch {}
    }
  }, [isAuthenticated, hasUIAccess, router])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMessage('')

    try {
      try {
        await postJson(`${SERVER_URL}/platform/authorization`, { email, password })
      } catch (e:any) {
        setErrorMessage(e?.message || 'Invalid email or password')
        setIsLoading(false)
        return
      }
      try {
        const meData: any = await getJson(`${SERVER_URL}/platform/user/me`)
        const isSuperAdmin = meData && (meData.username === 'admin' || meData.role === 'admin')
        const allowUi = !!(meData && (isSuperAdmin || meData.ui_access === true))
        if (!allowUi) {
          setErrorMessage('Your account does not have UI access. Contact an administrator.')
          try { await postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch {}
          setIsLoading(false)
          return
        }
      } catch (e: any) {
        // If we cannot fetch account details, surface a clearer error
        setErrorMessage(e?.message || 'Unable to verify account access. Please try again.')
        try { await postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch {}
        setIsLoading(false)
        return
      }
      await checkAuth()
      router.push('/dashboard')
    } catch (error) {
      console.error('Login error:', error)
      setErrorMessage('Network error. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg text-gray-900 dark:text-white flex items-center justify-center p-6">
      <button
        onClick={toggleTheme}
        className="absolute top-6 right-6 rounded-sm p-2 text-gray-500 hover:bg-gray-100 dark:text-white/60 dark:hover:bg-white/5 transition-colors"
        aria-label="Toggle theme"
      >
        {theme === 'light' ? (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        ) : (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        )}
      </button>

      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-white/[0.08] rounded-lg p-8 shadow-xl">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 w-12 h-12 bg-primary-600 dark:bg-[#e5e5e5] rounded flex items-center justify-center">
              <span className="text-white dark:text-[#1a1a1a] font-semibold">D</span>
            </div>
            <h1 className="text-[22px] font-medium text-gray-900 dark:text-white/90 mb-1">Welcome to Doorman</h1>
            <p className="text-gray-600 dark:text-white/40 text-[13px]">Sign in to manage your API gateway</p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block mb-2 text-[12px] text-gray-600 dark:text-white/60 font-medium">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@company.com"
                className="input"
                disabled={isLoading}
              />
            </div>

            <div className="mb-5">
              <label className="block mb-2 text-[12px] text-gray-600 dark:text-white/60 font-medium">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="Enter your password"
                className="input"
                disabled={isLoading}
              />
            </div>

            {errorMessage && (
              <div className="mb-4 text-[13px] px-3 py-2 rounded-sm border border-error-500/40 bg-error-50 dark:bg-error-500/10 text-error-700 dark:text-error-300">
                {errorMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className={`w-full px-4 py-2.5 rounded-sm text-[14px] font-medium transition border ${isLoading ? 'bg-gray-200 dark:bg-white/20 text-gray-600 dark:text-white/60 border-gray-300 dark:border-white/10 cursor-not-allowed' : 'bg-primary-600 dark:bg-[#e5e5e5] text-white dark:text-[#1a1a1a] hover:bg-primary-700 dark:hover:bg-white border-transparent'}`}
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          {/* Footer */}
          <div className="text-center mt-6 pt-6 border-t border-gray-200 dark:border-white/[0.08]">
            <p className="text-[11px] text-gray-500 dark:text-white/40">
              By signing in, you agree to our <a href="/terms" className="text-gray-700 dark:text-white/60 hover:text-gray-900 dark:hover:text-white/80">Terms</a> and <a href="/privacy" className="text-gray-700 dark:text-white/60 hover:text-gray-900 dark:hover:text-white/80">Privacy Policy</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
