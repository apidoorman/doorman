'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './routings.css';

interface Routing {
  id: string;
  name: string;
  active: boolean;
  host: string;
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
  { label: 'Logs', href: '/logging' },
  { label: 'Security' },
  { label: 'Settings', href: '/settings' },
];

const handleLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  setTimeout(() => {
    window.location.replace('/');
  }, 50);
};

const RoutingsPage = () => {
  const [theme, setTheme] = useState('light');
  const [routings, setRoutings] = useState<Routing[]>([]);
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
    fetchRoutings();
  }, []);

  const fetchRoutings = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/routings`);
      if (!response.ok) {
        throw new Error('Failed to load routings');
      }
      const data = await response.json();
      setRoutings(data);
    } catch (err) {
      setError('Failed to load routings. Please try again later.');
      setRoutings([]);
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
    const sortedRoutings = [...routings].sort((a, b) => {
      if (sortField === 'name') {
        return a.name.localeCompare(b.name);
      } else if (sortField === 'host') {
        return a.host.localeCompare(b.host);
      } else if (sortField === 'active') {
        return (a.active === b.active) ? 0 : a.active ? -1 : 1;
      }
      return 0;
    });
    setRoutings(sortedRoutings);
  };

  return (
    <>
      <div className="routings-topbar">
      Doorman
      </div>
      <div className="routings-root">
        <aside className="routings-sidebar">
          <div className="routings-sidebar-title">Menu</div>
          <ul className="routings-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`routings-sidebar-item${idx === 2 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`routings-sidebar-item${idx === 2 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="routings-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="routings-main">
          <div className="routings-header-row">
            <h1 className="routings-title">Routings</h1>
            <button className="refresh-button" onClick={fetchRoutings}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="routings-controls">
            <form className="routings-search-box" onSubmit={handleSearch}>
              <input
                type="text"
                className="routings-search-input"
                placeholder="Search routings..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button type="submit" className="routings-search-btn">Search</button>
              <button type="button" className="routings-add-btn">Add Routing</button>
            </form>
            <div className="routings-sort-group">
              <button 
                className={`routings-sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => handleSort('name')}
              >
                Name
              </button>
              <button 
                className={`routings-sort-btn ${sortBy === 'host' ? 'active' : ''}`}
                onClick={() => handleSort('host')}
              >
                Host
              </button>
              <button 
                className={`routings-sort-btn ${sortBy === 'active' ? 'active' : ''}`}
                onClick={() => handleSort('active')}
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
              <p>Loading routings...</p>
            </div>
          ) : (
            <div className="routings-table-panel">
              <table className="routings-table">
                <thead>
                  <tr>
                    <th>Id</th>
                    <th>Name</th>
                    <th>Active</th>
                    <th>Host</th>
                    <th>Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {routings.map((routing) => (
                    <tr key={routing.id}>
                      <td>{routing.id}</td>
                      <td><b>{routing.name}</b></td>
                      <td><span className="routings-active-badge">{routing.active ? 'True' : 'False'}</span></td>
                      <td>{routing.host}</td>
                      <td>{new Date(routing.lastUpdated).toLocaleDateString()}</td>
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

export default RoutingsPage;
