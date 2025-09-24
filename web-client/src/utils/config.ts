// Backend API base URL. Resolved in this order:
// 1) window.__SERVER_URL (set at runtime if you want a quick override)
// 2) localStorage.SERVER_URL (dev convenience)
// 3) NEXT_PUBLIC_SERVER_URL (build-time env)
// 4) default: http://localhost:3002
const fromGlobal = typeof window !== 'undefined' ? (window as any).__SERVER_URL : undefined
const fromStorage = typeof window !== 'undefined' ? window.localStorage.getItem('SERVER_URL') : null
export const SERVER_URL = (fromGlobal || fromStorage || process.env.NEXT_PUBLIC_SERVER_URL) as string
// Helpful in dev: log the resolved base URL once in the browser
if (typeof window !== 'undefined' && process.env.NODE_ENV !== 'production') {
  // eslint-disable-next-line no-console
  console.log('[Config] SERVER_URL =', SERVER_URL)
}
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
