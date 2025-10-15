/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  eslint: {
    // Allow production builds to succeed even if there are ESLint errors.
    ignoreDuringBuilds: true,
  },
  images: {
    // Allow remote image hosts via env: NEXT_IMAGE_DOMAINS=cdn.example.com,images.example.org
    remotePatterns: buildRemotePatterns(),
    // Prevent script execution / content injection on the image optimization response
    contentSecurityPolicy: "script-src 'none'; frame-ancestors 'none'; sandbox;",
    dangerouslyAllowSVG: false,
    // Allow opt-out to disable optimizer entirely when desired
    unoptimized: (process.env.NEXT_IMAGE_UNOPTIMIZED || '').toLowerCase() === 'true',
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'Permissions-Policy', value: 'geolocation=(), microphone=(), camera=()' },
        ],
      },
    ]
  },
}

function buildRemotePatterns() {
  const env = process.env.NEXT_IMAGE_DOMAINS || ''
  const hosts = env.split(',').map(s => s.trim()).filter(Boolean)
  return hosts.map(hostname => ({ protocol: 'https', hostname }))
}

export default nextConfig

