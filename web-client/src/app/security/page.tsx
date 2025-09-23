'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './security.css';

interface ApiKey {
  id: string;
  name: string;
  key: string;
  created: string;
  lastUsed: string;
  status: 'active' | 'revoked';
}

interface RateLimit {
  id: string;
  path: string;
  limit: number;
  window: string;
  status: 'active' | 'disabled';
}

interface IpWhitelist {
  id: string;
  ip: string;
  description: string;
  created: string;
  status: 'active' | 'disabled';
}

interface SecurityPolicy {
  id: string;
  name: string;
  type: 'jwt' | 'oauth2' | 'api-key' | 'ip-whitelist';
  status: 'active' | 'disabled';
  createdAt: string;
}

const menuItems = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'APIs', href: '/apis' },
  { label: 'Routings', href: '/routings' },
  { label: 'Users', href: '/users' },
  { label: 'Groups', href: '/groups' },
  { label: 'Roles', href: '/roles' },
  { label: 'Monitor', href: '/monitor' },
  { label: 'Logs', href: '/logging' },
  { label: 'Security', href: '/security' },
  { label: 'Settings', href: '/settings' },
];

const handleLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  setTimeout(() => {
    window.location.replace('/');
  }, 50);
};

const SecurityPage = () => {
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('api-keys');
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [rateLimits, setRateLimits] = useState<RateLimit[]>([]);
  const [ipWhitelist, setIpWhitelist] = useState<IpWhitelist[]>([]);
  const [securityPolicies, setSecurityPolicies] = useState<SecurityPolicy[]>([]);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
    fetchSecurityData();
  }, []);

  const fetchSecurityData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [keysRes, limitsRes, whitelistRes, policiesRes] = await Promise.all([
        fetch('/api/security/keys'),
        fetch('/api/security/rate-limits'),
        fetch('/api/security/ip-whitelist'),
        fetch('/api/security/policies')
      ]);

      if (!keysRes.ok || !limitsRes.ok || !whitelistRes.ok || !policiesRes.ok) {
        throw new Error('Failed to load security data');
      }

      const [keys, limits, whitelist, policies] = await Promise.all([
        keysRes.json(),
        limitsRes.json(),
        whitelistRes.json(),
        policiesRes.json()
      ]);

      setApiKeys(keys);
      setRateLimits(limits);
      setIpWhitelist(whitelist);
      setSecurityPolicies(policies);
    } catch (err) {
      setError('Failed to load security data. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateApiKey = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/security/keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: 'New API Key' }),
      });

      if (!response.ok) {
        throw new Error('Failed to create API key');
      }

      const newKey = await response.json();
      setApiKeys(prev => [...prev, newKey]);
      setSuccess('API key created successfully');
    } catch (err) {
      setError('Failed to create API key. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeApiKey = async (keyId: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/security/keys/${keyId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to revoke API key');
      }

      setApiKeys(prev => prev.map(key => 
        key.id === keyId ? { ...key, status: 'revoked' } : key
      ));
      setSuccess('API key revoked successfully');
    } catch (err) {
      setError('Failed to revoke API key. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddRateLimit = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/security/rate-limits', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          path: '/api/*',
          limit: 100,
          window: '1m',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to add rate limit');
      }

      const newLimit = await response.json();
      setRateLimits(prev => [...prev, newLimit]);
      setSuccess('Rate limit added successfully');
    } catch (err) {
      setError('Failed to add rate limit. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddIpWhitelist = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/security/ip-whitelist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ip: '192.168.1.1',
          description: 'New IP Address',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to add IP to whitelist');
      }

      const newIp = await response.json();
      setIpWhitelist(prev => [...prev, newIp]);
      setSuccess('IP added to whitelist successfully');
    } catch (err) {
      setError('Failed to add IP to whitelist. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSecurityPolicy = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/security/policies', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: 'New Security Policy',
          type: 'api-key',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create security policy');
      }

      const newPolicy = await response.json();
      setSecurityPolicies(prev => [...prev, newPolicy]);
      setSuccess('Security policy created successfully');
    } catch (err) {
      setError('Failed to create security policy. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="security-topbar">
      Doorman
      </div>
      <div className="security-root">
        <aside className="security-sidebar">
          <div className="security-sidebar-title">Menu</div>
          <ul className="security-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`security-sidebar-item${idx === 8 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`security-sidebar-item${idx === 8 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="security-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="security-main">
          <div className="security-header-row">
            <h1 className="security-title">Security</h1>
            <button className="refresh-button" onClick={fetchSecurityData}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          {success && (
            <div className="success-container">
              <div className="success-message">
                {success}
              </div>
            </div>
          )}

          {loading ? (
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading security data...</p>
            </div>
          ) : (
            <div className="security-content">
              <div className="security-tabs">
                <button
                  className={`security-tab ${activeTab === 'api-keys' ? 'active' : ''}`}
                  onClick={() => setActiveTab('api-keys')}
                >
                  API Keys
                </button>
                <button
                  className={`security-tab ${activeTab === 'rate-limits' ? 'active' : ''}`}
                  onClick={() => setActiveTab('rate-limits')}
                >
                  Gateway Rate Limits
                </button>
                <button
                  className={`security-tab ${activeTab === 'ip-whitelist' ? 'active' : ''}`}
                  onClick={() => setActiveTab('ip-whitelist')}
                >
                  IP Control
                </button>
              </div>

              <div className="security-panel">
                {activeTab === 'api-keys' && (
                  <div className="security-section">
                    <div className="security-section-header">
                      <h2>API Keys</h2>
                      <button className="security-add-btn" onClick={handleCreateApiKey}>
                        Create New Key
                      </button>
                    </div>
                    <div className="security-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Key</th>
                            <th>Created</th>
                            <th>Last Used</th>
                            <th>Status</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {apiKeys.map(key => (
                            <tr key={key.id}>
                              <td>{key.name}</td>
                              <td>{key.key}</td>
                              <td>{new Date(key.created).toLocaleDateString()}</td>
                              <td>{key.lastUsed ? new Date(key.lastUsed).toLocaleDateString() : 'Never'}</td>
                              <td>
                                <span className={`status-badge ${key.status}`}>
                                  {key.status}
                                </span>
                              </td>
                              <td>
                                <button
                                  className="security-revoke-btn"
                                  onClick={() => handleRevokeApiKey(key.id)}
                                  disabled={key.status === 'revoked'}
                                >
                                  Revoke
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeTab === 'rate-limits' && (
                  <div className="security-section">
                    <div className="security-section-header">
                      <h2>Rate Limits</h2>
                      <button className="security-add-btn" onClick={handleAddRateLimit}>
                        Add Rate Limit
                      </button>
                    </div>
                    <div className="security-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Path</th>
                            <th>Limit</th>
                            <th>Window</th>
                            <th>Status</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rateLimits.map(limit => (
                            <tr key={limit.id}>
                              <td>{limit.path}</td>
                              <td>{limit.limit}</td>
                              <td>{limit.window}</td>
                              <td>
                                <span className={`status-badge ${limit.status}`}>
                                  {limit.status}
                                </span>
                              </td>
                              <td>
                                <button className="security-edit-btn">Edit</button>
                                <button className="security-delete-btn">Delete</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeTab === 'ip-whitelist' && (
                  <div className="security-section">
                    <div className="security-section-header">
                      <h2>IP Whitelist</h2>
                      <button className="security-add-btn" onClick={handleAddIpWhitelist}>
                        Add IP Address
                      </button>
                    </div>
                    <div className="security-table">
                      <table>
                        <thead>
                          <tr>
                            <th>IP Address</th>
                            <th>Description</th>
                            <th>Created</th>
                            <th>Status</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ipWhitelist.map(ip => (
                            <tr key={ip.id}>
                              <td>{ip.ip}</td>
                              <td>{ip.description}</td>
                              <td>{new Date(ip.created).toLocaleDateString()}</td>
                              <td>
                                <span className={`status-badge ${ip.status}`}>
                                  {ip.status}
                                </span>
                              </td>
                              <td>
                                <button className="security-edit-btn">Edit</button>
                                <button className="security-delete-btn">Delete</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default SecurityPage;