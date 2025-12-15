// Gateway URL from environment - required for API calls
// Set NEXT_PUBLIC_GATEWAY_URL in .env.local (dev) or at build time (prod)
const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || ''

const getApiUrl = (): string => {
  // 1. Use gateway URL from env if set
  if (GATEWAY_URL) {
    return GATEWAY_URL
  }
  
  // 2. Check localStorage override (user can manually set for custom setups)
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem('API_URL')
    if (stored) return stored
  }
  
  // 3. Fallback to same origin (for reverse proxy setups)
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  
  // 4. SSR fallback
  return ''
}

// Debug: log what env var was read
if (typeof window !== 'undefined' && process.env.NODE_ENV !== 'production') {
  console.log('[Config] NEXT_PUBLIC_GATEWAY_URL =', GATEWAY_URL || '(not set)')
}

export const SERVER_URL = getApiUrl()
export const WEB_URL = typeof window !== 'undefined' ? window.location.origin : ''

if (typeof window !== 'undefined') {
  const DEBUG = process.env.NODE_ENV !== 'production'
  if (DEBUG) console.log('[Config] SERVER_URL =', SERVER_URL)
}
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
