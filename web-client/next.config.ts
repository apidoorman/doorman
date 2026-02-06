import type { NextConfig } from 'next'

const isDemo = process.env.DEMO_MODE === 'true'
const gatewayTarget = process.env.GATEWAY_INTERNAL_URL || 'http://localhost:3001'

const securityHeaders = [
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  {
    key: 'X-Frame-Options',
    value: 'DENY',
  },
  {
    key: 'Referrer-Policy',
    value: 'no-referrer',
  },
  {
    key: 'Permissions-Policy',
    value: 'geolocation=(), microphone=(), camera=()',
  },
]

function buildRemotePatterns() {
  const env = process.env.NEXT_IMAGE_DOMAINS || ''
  const hosts = env.split(',').map(s => s.trim()).filter(Boolean)
  return hosts.map(hostname => ({ protocol: 'https' as const, hostname }))
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // Harden Next/Image to mitigate known issues around the optimization route
  images: {
    // Allow remote image hosts via env: NEXT_IMAGE_DOMAINS=cdn.example.com,images.example.org
    remotePatterns: buildRemotePatterns(),
    // Prevent script execution / content injection on the image optimization response
    contentSecurityPolicy: "script-src 'none'; frame-ancestors 'none'; sandbox;",
    dangerouslyAllowSVG: false,
    // Allow opt-out to disable optimizer entirely when desired
    unoptimized: (process.env.NEXT_IMAGE_UNOPTIMIZED || '').toLowerCase() === 'true',
  },
  async redirects() {
    return [
      {
        source: '/favicon.ico',
        destination: '/favicon-32x32.png',
        permanent: true,
      },
    ]
  },
  async rewrites() {
    if (!isDemo) return []
    return [
      { source: '/platform/:path*', destination: `${gatewayTarget}/platform/:path*` },
      { source: '/api/:path*', destination: `${gatewayTarget}/api/:path*` },
    ]
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ]
  },
}

export default nextConfig
