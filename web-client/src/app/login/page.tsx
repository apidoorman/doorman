'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { SERVER_URL } from '@/utils/config'
import { postJson, getJson } from '@/utils/api'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const { checkAuth, isAuthenticated, hasUIAccess } = useAuth()
  const nextPath = getSafeNextPath(searchParams.get('next'))

  useEffect(() => { document.documentElement.classList.remove('dark') }, [])
  useEffect(() => {
    if (isAuthenticated && hasUIAccess) router.push('/dashboard')
    else if (isAuthenticated) {
      setErrorMessage('Your account does not have UI access. Contact an administrator.')
      try { void postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch { }
      try { localStorage.clear(); sessionStorage.clear(); document.cookie = 'access_token_cookie=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/' } catch { }
    }
  }, [isAuthenticated, hasUIAccess, nextPath, router])

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault(); setIsLoading(true); setErrorMessage('')
    try {
      try { await postJson(`${SERVER_URL}/platform/authorization`, { email, password }) }
      catch (error: any) { setErrorMessage(error?.message || 'Invalid email or password'); return }
      try {
        const meData: any = await getJson(`${SERVER_URL}/platform/user/me`)
        const isSuperAdmin = meData && (meData.username === 'admin' || meData.role === 'admin')
        if (!(meData && (isSuperAdmin || meData.ui_access === true))) {
          setErrorMessage('Your account does not have UI access. Contact an administrator.')
          try { await postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch { }
          return
        }
      } catch (error: any) {
        setErrorMessage(error?.message || 'Unable to verify account access. Please try again.')
        try { await postJson(`${SERVER_URL}/platform/authorization/invalidate`, {}) } catch { }
        return
      }
      await checkAuth(); router.push('/dashboard')
    } catch (error) {
      console.error('Login error:', error); setErrorMessage('Network error. Please try again.')
    } finally { setIsLoading(false) }
  }

  return <main className="login-signal min-h-screen"><section className="login-signal__panel"><header className="login-signal__header"><a href="https://doorman.dev" className="login-signal__brand" aria-label="Doorman"><span className="login-signal__mark" aria-hidden="true"><img src="/doorman-mark.svg" alt="" /></span><span><strong>Doorman</strong><small>API + AI Gateway</small></span></a><p className="signal-kicker">Gateway access</p><h1>Sign in.</h1><p>Use your Doorman account to manage gateway configuration, traffic, and access control.</p></header><form onSubmit={handleLogin} className="login-signal__form"><div><label htmlFor="email">Email</label><input id="email" type="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" placeholder="you@company.com" className="input" disabled={isLoading} /></div><div><label htmlFor="password">Password</label><input id="password" type="password" value={password} onChange={event => setPassword(event.target.value)} required autoComplete="current-password" placeholder="Enter your password" className="input" disabled={isLoading} /></div>{errorMessage && <div className="login-signal__error">{errorMessage}</div>}<button type="submit" disabled={isLoading} className="signal-button signal-button--primary w-full">{isLoading ? 'Signing in…' : 'Sign in'}</button></form><footer>By signing in, you agree to our <a href="/terms">Terms</a> and <a href="/privacy">Privacy Policy</a>.</footer></section></main>
}
