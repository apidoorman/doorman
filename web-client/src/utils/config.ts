// Runtime URL detection - domain agnostic
const getApiUrl = (): string => {
  // 1. Check localStorage override (user can manually set for custom setups)
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem('API_URL')
    if (stored) return stored
  }
  
  // 2. Use same origin as the web client (works for reverse proxy)
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  
  // 3. SSR fallback
  return 'http://localhost:3001'
}

export const SERVER_URL = getApiUrl()
export const WEB_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'

if (typeof window !== 'undefined') {
  const DEBUG = process.env.NODE_ENV !== 'production'
  if (DEBUG) console.log('[Config] SERVER_URL =', SERVER_URL)
}
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
