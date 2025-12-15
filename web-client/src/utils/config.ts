// Gateway URL from environment - required for API calls
// Set NEXT_PUBLIC_GATEWAY_URL in root .env file (loaded via dotenv-cli for dev, build arg for Docker)
const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || ''

const getApiUrl = (): string => {
  // 1. Use gateway URL from env if set
  if (GATEWAY_URL) {
    console.log('[CONFIG] Using GATEWAY_URL from env:', GATEWAY_URL)
    return GATEWAY_URL
  }
  
  // 2. Check localStorage override (user can manually set for custom setups)
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem('API_URL')
    if (stored) {
      console.log('[CONFIG] Found localStorage API_URL:', stored)
      // If current page is HTTPS, ensure API URL is also HTTPS
      if (window.location.protocol === 'https:' && stored.startsWith('http://')) {
        const httpsUrl = stored.replace('http://', 'https://')
        console.log('[CONFIG] Upgrading to HTTPS:', httpsUrl)
        window.localStorage.setItem('API_URL', httpsUrl)
        return httpsUrl
      }
      return stored
    }
  }
  
  // 3. Fallback to same origin (for reverse proxy setups)
  if (typeof window !== 'undefined') {
    console.log('[CONFIG] Using window.location.origin:', window.location.origin)
    return window.location.origin
  }
  
  // 4. SSR fallback
  console.log('[CONFIG] SSR fallback - empty string')
  return ''
}

export const SERVER_URL = getApiUrl()
export const WEB_URL = typeof window !== 'undefined' ? window.location.origin : ''
export const PROTECTED_USERS = (process.env.NEXT_PUBLIC_PROTECTED_USERS || '')
  .split(',')
  .map(u => u.trim().toLowerCase())
  .filter(Boolean)
