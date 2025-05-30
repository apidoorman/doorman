'use client'

import React, { useState, useEffect, Key, ReactNode } from 'react';
import Link from 'next/link';
import './apis.css';

interface API {
  api_version: ReactNode;
  api_type: ReactNode;
  api_description: ReactNode;
  api_path: ReactNode;
  api_id: Key | null | undefined;
  api_name: ReactNode;
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
      const response = await fetch(`http://localhost:3002/platform/api/all`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to load APIs');
      }
      const data = await response.json();
      const apiList = Array.isArray(data) ? data : (data.apis || data.response?.apis || []);
      setApis(apiList);
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
      if (sortField === 'api_name') {
        return (a.api_name as string).localeCompare(b.api_name as string);
      } else if (sortField === 'api_version') {
        return (a.api_version as string).localeCompare(b.api_version as string);
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
            {menuItems.map((item) => (
              item.href ? (
                <li key={`menu-${item.label}`} className={`apis-sidebar-item${item.label === 'APIs' ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={`menu-${item.label}`} className={`apis-sidebar-item${item.label === 'APIs' ? ' active' : ''}`}>{item.label}</li>
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
                key="sort-name"
                className={`apis-sort-btn ${sortBy === 'api_name' ? 'active' : ''}`}
                onClick={() => handleSort('api_name')}
              >
                Name
              </button>
              <button 
                key="sort-version"
                className={`apis-sort-btn ${sortBy === 'api_version' ? 'active' : ''}`}
                onClick={() => handleSort('api_version')}
              >
                Version
              </button>
              <button 
                key="sort-type"
                className={`apis-sort-btn ${sortBy === 'api_type' ? 'active' : ''}`}
                onClick={() => handleSort('api_type')}
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
                    <th>Path</th>
                    <th>Description</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {apis.map((api, index) => (
                    <tr key={api.api_id || `${api.api_name}-${api.api_version}-${index}`}>
                      <td>{api.api_name}</td>
                      <td>
                        <span className="apis-version-badge">{api.api_version}</span>
                      </td>
                      <td>{api.api_path}</td>
                      <td>{api.api_description}</td>
                      <td>{api.api_type}</td>
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
