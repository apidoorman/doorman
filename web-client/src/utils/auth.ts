interface JWTPayload {
  sub: string
  role: string
  accesses: {
    ui_access: boolean
    manage_users: boolean
    manage_apis: boolean
    manage_endpoints: boolean
    manage_groups: boolean
    manage_roles: boolean
    manage_routings: boolean
    manage_gateway: boolean
    manage_subscriptions: boolean
    manage_security: boolean
  }
  exp: number
  jti: string
}

export function decodeJWT(token: string): JWTPayload | null {
  try {
    console.log('=== JWT DECODE ===')
    console.log('Attempting to decode token:', token.substring(0, 50) + '...')
    
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payload = JSON.parse(jsonPayload)
    
    console.log('JWT decode successful:', {
      sub: payload.sub,
      role: payload.role,
      ui_access: payload.accesses?.ui_access,
      accesses: payload.accesses,
      exp: payload.exp
    })
    
    return payload
  } catch (error) {
    console.error('Error decoding JWT:', error)
    return null
  }
}

export function getTokenFromCookie(): string | null {
  const cookies = document.cookie.split(';')
  const tokenCookie = cookies.find(cookie => cookie.trim().startsWith('access_token_cookie='))
  const token = tokenCookie ? tokenCookie.split('=')[1] : null
  
  // Debug logging
  if (typeof window !== 'undefined') {
    console.log('=== AUTH DEBUG ===')
    console.log('All cookies:', document.cookie)
    console.log('Cookie array:', cookies)
    console.log('Found token cookie:', tokenCookie)
    console.log('Token value:', token ? token.substring(0, 50) + '...' : 'None')
    console.log('Token length:', token ? token.length : 0)
  }
  
  return token
}

export function isTokenValid(token: string): boolean {
  console.log('=== TOKEN VALIDATION ===')
  console.log('Validating token:', token.substring(0, 50) + '...')
  
  const payload = decodeJWT(token)
  if (!payload) {
    console.log('Token decode failed')
    return false
  }
  
  const now = Math.floor(Date.now() / 1000)
  const isValid = payload.exp > now
  
  console.log('Token validation results:', {
    exp: payload.exp,
    now,
    isValid,
    ui_access: payload.accesses?.ui_access,
    accesses: payload.accesses,
    username: payload.sub,
    role: payload.role
  })
  
  return isValid
}

export function isUserActive(token: string): boolean {
  const payload = decodeJWT(token)
  return payload?.accesses?.ui_access === true
}

export function hasUIAccess(token: string): boolean {
  const payload = decodeJWT(token)
  const uiAccess = payload?.accesses?.ui_access === true
  
  console.log('=== UI ACCESS CHECK ===')
  console.log('Token payload:', payload)
  console.log('Accesses object:', payload?.accesses)
  console.log('UI access value:', payload?.accesses?.ui_access)
  console.log('UI access result:', uiAccess)
  
  return uiAccess
}

export function hasPermission(token: string, permission: keyof JWTPayload['accesses']): boolean {
  const payload = decodeJWT(token)
  const hasPerm = payload?.accesses?.[permission] === true
  
  console.log('=== PERMISSION CHECK ===')
  console.log('Checking permission:', permission)
  console.log('Accesses object:', payload?.accesses)
  console.log('Permission value:', payload?.accesses?.[permission])
  console.log('Permission result:', hasPerm)
  
  return hasPerm
}

export function getUserPermissions(token: string): JWTPayload['accesses'] | null {
  const payload = decodeJWT(token)
  return payload?.accesses || null
}

export function getCurrentUser(token: string): { username: string; role: string } | null {
  const payload = decodeJWT(token)
  if (!payload) return null
  
  return {
    username: payload.sub,
    role: payload.role
  }
}

export function isAuthenticated(): boolean {
  const token = getTokenFromCookie()
  return token ? isTokenValid(token) : false
}

export function canAccessUI(): boolean {
  const token = getTokenFromCookie()
  if (!token) return false
  
  return isTokenValid(token) && hasUIAccess(token)
}

export function canAccessPage(permission: keyof JWTPayload['accesses']): boolean {
  const token = getTokenFromCookie()
  if (!token) return false
  
  return isTokenValid(token) && hasUIAccess(token) && hasPermission(token, permission)
} 
