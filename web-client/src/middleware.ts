import { NextRequest, NextResponse } from 'next/server'

const PRIVATE_NET_CIDRS = [
  /^localhost$/i,
  /^127(?:\.\d{1,3}){3}$/,
  /^::1$/,
  /^10\./,
  /^172\.(1[6-9]|2\d|3[0-1])\./,
  /^192\.168\./,
  /^169\.254\./,
]

function isPrivateHost(hostname: string): boolean {
  return PRIVATE_NET_CIDRS.some(re => re.test(hostname))
}

function isAllowedHost(hostname: string): boolean {
  const allow = (process.env.ALLOWED_REDIRECT_HOSTS || '')
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
  return allow.includes(hostname)
}

export function middleware(req: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static).*)'],
}
