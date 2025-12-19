import { NextRequest, NextResponse } from 'next/server'

// Minimal auth guard for app routes. If the access token cookie is missing,
// redirect to login. Public paths bypass this guard. Detailed permission checks
// still happen client-side (AuthContext) and on the backend.

const PUBLIC_PATH_PREFIXES = [
  '/login',
  '/403',
  '/public',
  '/_next',
  '/api',
  '/favicon.ico',
]

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATH_PREFIXES.some(p => pathname === p || pathname.startsWith(p + '/'))
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl
  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  const token = req.cookies.get('access_token_cookie')?.value
  if (!token) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    // Optionally carry the original path so the client can navigate back after login
    url.search = search ? `?next=${encodeURIComponent(pathname + search)}` : `?next=${encodeURIComponent(pathname)}`
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static).*)'],
}
