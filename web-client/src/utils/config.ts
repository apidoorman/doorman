const fromGlobal = typeof window !== 'undefined' ? (window as any).__SERVER_URL : undefined
const fromStorage = typeof window !== 'undefined' ? window.localStorage.getItem('SERVER_URL') : null
const fromEnv = process.env.NEXT_PUBLIC_SERVER_URL || process.env.NEXT_PUBLIC_API_URL
export const SERVER_URL = (fromGlobal || fromStorage || fromEnv) as string
if (typeof window !== 'undefined') {
  const DEBUG = process.env.NODE_ENV !== 'production'
  if (DEBUG) console.log('[Config] SERVER_URL =', SERVER_URL)
}
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
