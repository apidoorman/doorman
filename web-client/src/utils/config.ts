// Backend API base URL. Override via NEXT_PUBLIC_SERVER_URL in your env.
export const SERVER_URL = process.env.NEXT_PUBLIC_SERVER_URL || 'http://localhost:5001'
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
