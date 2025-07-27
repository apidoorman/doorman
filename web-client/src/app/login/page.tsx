'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const LoginPage = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [theme, setTheme] = useState('light')
  const router = useRouter()

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    setTheme(savedTheme)
    document.documentElement.classList.toggle('dark', savedTheme === 'dark')
  }, [])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrorMessage('')

    try {
      const authResponse = await fetch(`http://localhost:3002/platform/authorization`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ email, password }),
      })

      if (authResponse.ok) {
        const data = await authResponse.json()
        if (data.access_token) {
          document.cookie = `access_token_cookie=${data.access_token}; path=/; domain=localhost`
          router.push('/dashboard')
        } else {
          setErrorMessage('Login successful but no access token received')
        }
      } else {
        const errorData = await authResponse.json()
        setErrorMessage(errorData.detail || 'Invalid email or password')
      }
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-indigo-100 dark:from-dark-bg dark:via-gray-900 dark:to-gray-800 flex items-center justify-center p-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-gradient-to-br from-primary-400/20 to-primary-600/20 blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-gradient-to-tr from-purple-400/20 to-purple-600/20 blur-3xl"></div>
      </div>

      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        className="absolute top-6 right-6 rounded-lg p-2 text-gray-500 hover:bg-white/50 dark:text-gray-400 dark:hover:bg-dark-surface/50 transition-colors"
        aria-label="Toggle theme"
      >
        {theme === 'light' ? (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        ) : (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        )}
      </button>

      <div className="relative w-full max-w-md">
        {/* Logo and title */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 h-16 w-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg">
            <span className="text-white font-bold text-2xl">D</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Welcome back
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Sign in to your Doorman account
          </p>
        </div>

        {/* Login form */}
        <div className="card animate-fade-in">
          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Email address
              </label>
              <input
                id="email"
                type="email"
                required
                className="input"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                className="input"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
            </div>

            {errorMessage && (
              <div className="rounded-lg bg-error-50 border border-error-200 p-4 dark:bg-error-900/20 dark:border-error-800">
                <div className="flex">
                  <svg className="h-5 w-5 text-error-400 dark:text-error-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="ml-3">
                    <p className="text-sm text-error-700 dark:text-error-300">{errorMessage}</p>
                  </div>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary w-full py-3 text-base font-medium"
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="spinner mr-2"></div>
                  Signing in...
                </div>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              By signing in, you agree to our{' '}
              <a href="/terms" className="text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 font-medium">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="/privacy" className="text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 font-medium">
                Privacy Policy
              </a>
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Need help?{' '}
            <a href="/support" className="text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 font-medium">
              Contact support
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage