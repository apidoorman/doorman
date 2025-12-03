'use client'

import React, { useState, useEffect } from 'react'
import Layout from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { getJson, postJson, delJson } from '@/utils/api'

interface IPInfo {
  ip: string
  is_whitelisted: boolean
  is_blacklisted: boolean
  reputation_score: number
  request_count: number
  last_seen?: string
  country_code?: string
}

interface GeoDistribution {
  country_code: string
  request_count: number
}

export default function IPRateLimitsPage() {
  const [topIPs, setTopIPs] = useState<[string, number][]>([])
  const [geoDistribution, setGeoDistribution] = useState<GeoDistribution[]>([])
  const [blockedCountries, setBlockedCountries] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [searchIP, setSearchIP] = useState('')
  const [ipInfo, setIPInfo] = useState<IPInfo | null>(null)
  const [newCountryBlock, setNewCountryBlock] = useState('')

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      
      // Fetch top IPs
      const ipsData = await getJson('/platform/ip/top')
      setTopIPs(ipsData.top_ips || [])
      
      // Fetch geo distribution
      const geoData = await getJson('/platform/geo/distribution')
      setGeoDistribution(geoData.distribution || [])
      
      // Fetch blocked countries
      const blockedData = await getJson('/platform/geo/blocked')
      setBlockedCountries(blockedData.blocked_countries || [])
      
      setError(null)
    } catch (err) {
      console.error('Failed to fetch IP data:', err)
      setError('Failed to load IP analytics')
    } finally {
      setLoading(false)
    }
  }

  const handleSearchIP = async () => {
    if (!searchIP.trim()) return

    try {
      const data = await getJson(`/platform/ip/info/${searchIP}`)
      setIPInfo(data)
    } catch (err: any) {
      alert(err.message || 'Failed to lookup IP')
    }
  }

  const handleWhitelistIP = async (ip: string) => {
    try {
      await postJson('/platform/ip/whitelist', { ip })
      alert(`Added ${ip} to whitelist`)
      if (ipInfo?.ip === ip) {
        setIPInfo({ ...ipInfo, is_whitelisted: true })
      }
    } catch (err: any) {
      alert(err.message || 'Failed to whitelist IP')
    }
  }

  const handleBlacklistIP = async (ip: string) => {
    try {
      await postJson('/platform/ip/blacklist', { ip })
      alert(`Added ${ip} to blacklist`)
      if (ipInfo?.ip === ip) {
        setIPInfo({ ...ipInfo, is_blacklisted: true })
      }
    } catch (err: any) {
      alert(err.message || 'Failed to blacklist IP')
    }
  }

  const handleRemoveFromWhitelist = async (ip: string) => {
    try {
      await delJson(`/platform/ip/whitelist/${ip}`)
      alert(`Removed ${ip} from whitelist`)
      if (ipInfo?.ip === ip) {
        setIPInfo({ ...ipInfo, is_whitelisted: false })
      }
    } catch (err: any) {
      alert(err.message || 'Failed to remove from whitelist')
    }
  }

  const handleRemoveFromBlacklist = async (ip: string) => {
    try {
      await delJson(`/platform/ip/blacklist/${ip}`)
      alert(`Removed ${ip} from blacklist`)
      if (ipInfo?.ip === ip) {
        setIPInfo({ ...ipInfo, is_blacklisted: false })
      }
    } catch (err: any) {
      alert(err.message || 'Failed to remove from blacklist')
    }
  }

  const handleBlockCountry = async () => {
    if (!newCountryBlock.trim()) return

    try {
      await postJson('/platform/geo/block', { country_code: newCountryBlock.toUpperCase() })
      await fetchData()
      setNewCountryBlock('')
      alert(`Blocked country: ${newCountryBlock.toUpperCase()}`)
    } catch (err: any) {
      alert(err.message || 'Failed to block country')
    }
  }

  const handleUnblockCountry = async (countryCode: string) => {
    try {
      await delJson(`/platform/geo/block/${countryCode}`)
      await fetchData()
      alert(`Unblocked country: ${countryCode}`)
    } catch (err: any) {
      alert(err.message || 'Failed to unblock country')
    }
  }

  const getReputationColor = (score: number) => {
    if (score >= 80) return 'text-success-600'
    if (score >= 50) return 'text-warning-600'
    return 'text-error-600'
  }

  const getReputationBadge = (score: number) => {
    if (score >= 80) return <span className="badge badge-success">Good</span>
    if (score >= 50) return <span className="badge badge-warning">Suspicious</span>
    return <span className="badge badge-error">Bad</span>
  }

  return (
    <ProtectedRoute requiredPermission="manage_rate_limits">
      <Layout>
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              IP & Geographic Rate Limiting
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Monitor and manage IP-based rate limits and geographic restrictions
            </p>
          </div>

          {/* IP Lookup */}
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              IP Lookup
            </h2>
            <div className="flex gap-3">
              <input
                type="text"
                value={searchIP}
                onChange={(e) => setSearchIP(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearchIP()}
                placeholder="Enter IP address (e.g., 192.168.1.1)"
                className="input flex-1"
              />
              <button onClick={handleSearchIP} className="btn btn-primary">
                Lookup
              </button>
            </div>

            {ipInfo && (
              <div className="mt-4 p-4 rounded-lg bg-gray-50 dark:bg-gray-800">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">IP Address</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {ipInfo.ip}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Reputation</p>
                    <p className={`text-lg font-semibold ${getReputationColor(ipInfo.reputation_score)}`}>
                      {ipInfo.reputation_score}/100 {getReputationBadge(ipInfo.reputation_score)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Request Count (24h)</p>
                    <p className="text-lg font-semibold text-gray-900 dark:text-white">
                      {ipInfo.request_count.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
                    <div className="flex gap-2 mt-1">
                      {ipInfo.is_whitelisted && <span className="badge badge-success">Whitelisted</span>}
                      {ipInfo.is_blacklisted && <span className="badge badge-error">Blacklisted</span>}
                      {!ipInfo.is_whitelisted && !ipInfo.is_blacklisted && (
                        <span className="badge badge-neutral">Normal</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex gap-2 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  {!ipInfo.is_whitelisted ? (
                    <button
                      onClick={() => handleWhitelistIP(ipInfo.ip)}
                      className="btn btn-sm btn-outline"
                    >
                      Add to Whitelist
                    </button>
                  ) : (
                    <button
                      onClick={() => handleRemoveFromWhitelist(ipInfo.ip)}
                      className="btn btn-sm btn-outline"
                    >
                      Remove from Whitelist
                    </button>
                  )}
                  
                  {!ipInfo.is_blacklisted ? (
                    <button
                      onClick={() => handleBlacklistIP(ipInfo.ip)}
                      className="btn btn-sm btn-outline text-error-600"
                    >
                      Add to Blacklist
                    </button>
                  ) : (
                    <button
                      onClick={() => handleRemoveFromBlacklist(ipInfo.ip)}
                      className="btn btn-sm btn-outline"
                    >
                      Remove from Blacklist
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top IPs */}
            <div className="card p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Top IPs by Request Volume
              </h2>
              {loading ? (
                <p className="text-gray-600 dark:text-gray-400">Loading...</p>
              ) : topIPs.length > 0 ? (
                <div className="space-y-2">
                  {topIPs.map(([ip, count], idx) => (
                    <div
                      key={ip}
                      className="flex items-center justify-between p-3 rounded bg-gray-50 dark:bg-gray-800"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                          #{idx + 1}
                        </span>
                        <span className="font-mono text-sm text-gray-900 dark:text-white">
                          {ip}
                        </span>
                      </div>
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {count.toLocaleString()} requests
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-600 dark:text-gray-400">No data available</p>
              )}
            </div>

            {/* Geographic Distribution */}
            <div className="card p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Geographic Distribution
              </h2>
              {loading ? (
                <p className="text-gray-600 dark:text-gray-400">Loading...</p>
              ) : geoDistribution.length > 0 ? (
                <div className="space-y-2">
                  {geoDistribution.slice(0, 10).map((item) => (
                    <div
                      key={item.country_code}
                      className="flex items-center justify-between p-3 rounded bg-gray-50 dark:bg-gray-800"
                    >
                      <span className="font-medium text-gray-900 dark:text-white">
                        {item.country_code}
                      </span>
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {item.request_count.toLocaleString()} requests
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-600 dark:text-gray-400">No data available</p>
              )}
            </div>
          </div>

          {/* Blocked Countries */}
          <div className="card p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Blocked Countries
            </h2>
            
            <div className="flex gap-3 mb-4">
              <input
                type="text"
                value={newCountryBlock}
                onChange={(e) => setNewCountryBlock(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleBlockCountry()}
                placeholder="Country code (e.g., CN, RU)"
                className="input flex-1"
                maxLength={2}
              />
              <button onClick={handleBlockCountry} className="btn btn-primary">
                Block Country
              </button>
            </div>

            {blockedCountries.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {blockedCountries.map((code) => (
                  <div
                    key={code}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded bg-error-100 dark:bg-error-900/20"
                  >
                    <span className="font-medium text-error-800 dark:text-error-300">
                      {code}
                    </span>
                    <button
                      onClick={() => handleUnblockCountry(code)}
                      className="text-error-600 hover:text-error-700"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-600 dark:text-gray-400">No countries blocked</p>
            )}
          </div>
        </div>
      </Layout>
    </ProtectedRoute>
  )
}
