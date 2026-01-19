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
  // Common root-level static assets
  '/favicon.ico',
  '/favicon.png',
  '/favicon-16x16.png',
  '/favicon-32x32.png',
  '/favicon.svg',
  '/apple-touch-icon.png',
  '/android-chrome-192x192.png',
  '/android-chrome-512x512.png',
  '/safari-pinned-tab.svg',
  '/icon.png',
]

function isStaticAsset(pathname: string): boolean {
  const lower = pathname.toLowerCase()
  return [
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.svg',
    '.ico',
    '.txt',
    '.json',
    '.css',
    '.js',
    '.map',
    '.xml',
  ].some(ext => lower.endsWith(ext))
}

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATH_PREFIXES.some(p => pathname === p || pathname.startsWith(p + '/'))
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl
  if (isPublicPath(pathname) || isStaticAsset(pathname)) {
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
