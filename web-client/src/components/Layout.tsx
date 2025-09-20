'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

interface LayoutProps {
  children: React.ReactNode
}

interface MenuItem {
  label: string
  href: string
  icon: string
  permission?: string
}

const menuItems: MenuItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { label: 'Users', href: '/users', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z', permission: 'manage_users' },
  { label: 'APIs', href: '/apis', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10', permission: 'manage_apis' },
  { label: 'Protos', href: '/protos', icon: 'M12 8v8m-4-4h8M5 3a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V8.414A2 2 0 0019.586 7L15 2.414A2 2 0 0013.586 2H5z', permission: 'manage_apis' },
  { label: 'Groups', href: '/groups', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z', permission: 'manage_groups' },
  { label: 'Roles', href: '/roles', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', permission: 'manage_roles' },
  { label: 'Routings', href: '/routings', icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4', permission: 'manage_routings' },
  { label: 'Logging', href: '/logging', icon: 'M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2', permission: 'view_logs' },
  { label: 'Monitor', href: '/monitor', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', permission: 'manage_gateway' },
  { label: 'Demo Seed', href: '/demo', icon: 'M12 4v16m8-8H4', permission: 'manage_gateway' },
  { label: 'Tokens', href: '/tokens', icon: 'M12 8c-1.657 0-3 1.343-3 3 0 2.239 3 5 3 5s3-2.761 3-5c0-1.657-1.343-3-3-3z M12 13a2 2 0 110-4 2 2 0 010 4z', permission: 'manage_tokens' },
  { label: 'Token Definitions', href: '/token-defs', icon: 'M5 13l4 4L19 7', permission: 'manage_tokens' },
  { label: 'Subscriptions', href: '/subscriptions', icon: 'M3 5h12M9 3v2m-6 4h12M9 9v2m-6 4h12m-6 0v2', permission: 'manage_subscriptions' },
  { label: 'Authorizations', href: '/authorizations', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', permission: 'manage_subscriptions' },
  { label: 'Auth Control', href: '/auth-admin', icon: 'M5 13l4 4L19 7', permission: 'manage_auth' },
  { label: 'Security', href: '/security', icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z', permission: 'manage_security' },
  { label: 'Settings', href: '/settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' }
]

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [theme, setTheme] = useState('light')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()
  const { isAuthenticated, hasUIAccess, user, permissions, logout } = useAuth()
  const router = useRouter()

  // Redirect to login if not authenticated (except for login page)
  useEffect(() => {
    if (pathname !== '/login' && (!isAuthenticated || !hasUIAccess)) {
      console.log('Layout - Redirecting to login:', { pathname, isAuthenticated, hasUIAccess })
      router.push('/login')
    }
  }, [pathname, isAuthenticated, hasUIAccess, router])

  // Filter menu items based on user permissions
  const filteredMenuItems = menuItems.filter(item => {
    if (!item.permission) return true
    return permissions?.[item.permission] || false
  })

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    setTheme(savedTheme)
    document.documentElement.classList.toggle('dark', savedTheme === 'dark')
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
  }

  const handleLogout = () => {
    localStorage.clear()
    sessionStorage.clear()
    // HttpOnly cookie; server-side invalidate via endpoint if needed
    document.cookie = 'access_token_cookie=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
    window.location.href = '/login'
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'translate-x-0' : ''}`}>
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Doorman</h1>
          </div>
          
          {/* Menu Items */}
          <div className="flex-1 p-3 overflow-y-auto no-scrollbar">
            <nav className="space-y-1">
              {filteredMenuItems.map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                        : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white'
                    }`}
                  >
                    <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                    </svg>
                    {item.label}
                  </Link>
                )
              })}
            </nav>
          </div>
          
          {/* Bottom Actions */}
          <div className="p-3 border-t border-gray-200 dark:border-gray-700 space-y-1.5">
            {/* Dark mode toggle */}
            <button
              onClick={toggleTheme}
              className="flex items-center w-full px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-700 rounded-md transition-colors"
              aria-label="Toggle dark mode"
            >
              {theme === 'light' ? (
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              ) : (
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              )}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>
            
            {user && (
              <button
                onClick={logout}
                className="flex items-center w-full px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-700 rounded-md transition-colors"
              >
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Logout
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <main className="main-content">
        <div className="px-4 pb-4 lg:px-6 lg:pb-6 pt-5 lg:pt-4">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(true)}
            className={`lg:hidden fixed top-4 left-4 z-50 p-2 rounded-md bg-white dark:bg-gray-800 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 shadow-lg transition-opacity duration-200 ${sidebarOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          {children}
        </div>
      </main>
    </div>
  )
}

export default Layout 
