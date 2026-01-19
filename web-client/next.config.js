/** @type {import('next').NextConfig} */
const isDemo = process.env.DEMO_MODE === 'true'

const nextConfig = {
  // Keep production builds resilient (regular and demo)
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  async rewrites() {
    if (!isDemo) return []
    // Demo: proxy API to backend on 3001, keep browser same-origin (3000)
    const target = process.env.GATEWAY_INTERNAL_URL || 'http://localhost:3001'
    return [
      { source: '/platform/:path*', destination: `${target}/platform/:path*` },
      { source: '/api/:path*', destination: `${target}/api/:path*` },
    ]
  },
}

module.exports = nextConfig
