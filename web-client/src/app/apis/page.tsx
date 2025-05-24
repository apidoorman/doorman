'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './apis.css';

interface API {
  id: string;
  name: string;
  version: string;
  description: string;
  status: string;
  endpoints: number;
  lastUpdated: string;
}

const menuItems = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'APIs', href: '/apis' },
  { label: 'Routings', href: '/routings' },
  { label: 'Users', href: '/users' },
  { label: 'Groups', href: '/groups' },
  { label: 'Roles', href: '/roles' },
  { label: 'Monitor', href: '/monitor' },
  { label: 'Logs', href: '/logs' },
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

const APIsPage = () => {
  const [theme, setTheme] = useState('light');
  const [apis, setApis] = useState<API[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('name');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchApis();
  }, []);

  const fetchApis = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/apis`);
      if (!response.ok) {
        throw new Error('Failed to load APIs');
      }
      const data = await response.json();
      setApis(data);
    } catch (err) {
      setError('Failed to load APIs. Please try again later.');
      setApis([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // Implement search functionality
  };

  const handleSort = (sortField: string) => {
    setSortBy(sortField);
    const sortedApis = [...apis].sort((a, b) => {
      if (sortField === 'name') {
        return a.name.localeCompare(b.name);
      } else if (sortField === 'version') {
        return a.version.localeCompare(b.version);
      } else if (sortField === 'status') {
        return a.status.localeCompare(b.status);
      }
      return 0;
    });
    setApis(sortedApis);
  };

  return (
    <>
      <div className="apis-topbar">
      Doorman
        <button 
          className="apis-refresh-btn"
          onClick={fetchApis}
          aria-label="Refresh APIs"
        >
          <span className="refresh-icon"></span>
        </button>
      </div>
      <div className="apis-root">
        <aside className="apis-sidebar">
          <div className="apis-sidebar-title">Menu</div>
          <ul className="apis-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`apis-sidebar-item${idx === 1 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`apis-sidebar-item${idx === 1 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="apis-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="apis-main">
          <div className="apis-header-row">
            <h1 className="apis-title">APIs</h1>
            <button className="refresh-button" onClick={fetchApis}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="apis-controls">
            <form className="apis-search-box" onSubmit={handleSearch}>
              <input
                type="text"
                className="apis-search-input"
                placeholder="Search APIs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button type="submit" className="apis-search-btn">Search</button>
              <button type="button" className="apis-add-btn">Add API</button>
            </form>
            <div className="apis-sort-group">
              <button 
                className={`apis-sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => handleSort('name')}
              >
                Name
              </button>
              <button 
                className={`apis-sort-btn ${sortBy === 'version' ? 'active' : ''}`}
                onClick={() => handleSort('version')}
              >
                Version
              </button>
              <button 
                className={`apis-sort-btn ${sortBy === 'status' ? 'active' : ''}`}
                onClick={() => handleSort('status')}
              >
                Status
              </button>
            </div>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          {loading ? (
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading APIs...</p>
            </div>
          ) : (
            <div className="apis-table-panel">
              <table className="apis-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Description</th>
                    <th>Status</th>
                    <th>Endpoints</th>
                    <th>Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {apis.map((api) => (
                    <tr key={api.id}>
                      <td>{api.name}</td>
                      <td>
                        <span className="apis-version-badge">{api.version}</span>
                      </td>
                      <td>{api.description}</td>
                      <td>{api.status}</td>
                      <td>{api.endpoints}</td>
                      <td>{new Date(api.lastUpdated).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default APIsPage;
