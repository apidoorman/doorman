import { NextRequest, NextResponse } from 'next/server'

// Safe, no-op middleware template with helper guards for future use.
// This does not alter responses by default. It provides utilities to validate
// any redirect targets or proxy URLs if you introduce them later.

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
  // Intentionally do nothing; acts as a safe scaffold.
  // Example usage if adding redirect support:
  // const to = req.nextUrl.searchParams.get('to')
  // if (to) {
  //   try {
  //     const url = new URL(to)
  //     if (url.protocol !== 'https:' || isPrivateHost(url.hostname) || (!isAllowedHost(url.hostname) && url.hostname !== req.nextUrl.hostname)) {
  //       return NextResponse.next()
  //     }
  //     return NextResponse.redirect(url)
  //   } catch {}
  // }
  return NextResponse.next()
}

export const config = {
  // Run on all routes; Next automatically excludes static assets under .next/static
  matcher: ['/((?!_next/static).*)'],
}

