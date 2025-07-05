'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import './routings.css';

interface Routing {
  routing_name: string;
  routing_servers: string[];
  routing_description: string;
  client_key: string;
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
  const router = useRouter();
  const [theme, setTheme] = useState('light');
  const [routings, setRoutings] = useState<Routing[]>([]);
  const [allRoutings, setAllRoutings] = useState<Routing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('routing_name');

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
      const response = await fetch(`http://localhost:3002/platform/routing/all?page=1&page_size=10`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to load routings');
      }
      const data = await response.json();
      const routingList = Array.isArray(data) ? data : (data.routings || data.response?.routings || []);
      setAllRoutings(routingList);
      setRoutings(routingList);
    } catch (err) {
      setError('Failed to load routings. Please try again later.');
      setRoutings([]);
      setAllRoutings([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) {
      setRoutings(allRoutings);
      return;
    }
    
    const filteredRoutings = allRoutings.filter(routing => 
      routing.routing_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      routing.routing_description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      routing.client_key.toLowerCase().includes(searchTerm.toLowerCase()) ||
      routing.routing_servers.some(server => server.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setRoutings(filteredRoutings);
  };

  const handleSort = (sortField: string) => {
    setSortBy(sortField);
    const sortedRoutings = [...routings].sort((a, b) => {
      if (sortField === 'routing_name') {
        return a.routing_name.localeCompare(b.routing_name);
      } else if (sortField === 'client_key') {
        return a.client_key.localeCompare(b.client_key);
      } else if (sortField === 'servers') {
        return a.routing_servers.length - b.routing_servers.length;
      }
      return 0;
    });
    setRoutings(sortedRoutings);
  };

  const handleRoutingClick = (routing: Routing) => {
    // Store routing data in sessionStorage for the detail page
    sessionStorage.setItem('selectedRouting', JSON.stringify(routing));
    router.push(`/routings/${routing.client_key}`);
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
              <Link href="/routings/add" className="routings-add-btn" style={{ textDecoration: 'none', display: 'inline-block' }}>
                Add Routing
              </Link>
            </form>
            <div className="routings-sort-group">
              <button 
                className={`routings-sort-btn ${sortBy === 'routing_name' ? 'active' : ''}`}
                onClick={() => handleSort('routing_name')}
              >
                Name
              </button>
              <button 
                className={`routings-sort-btn ${sortBy === 'client_key' ? 'active' : ''}`}
                onClick={() => handleSort('client_key')}
              >
                Key
              </button>
              <button 
                className={`routings-sort-btn ${sortBy === 'servers' ? 'active' : ''}`}
                onClick={() => handleSort('servers')}
              >
                Servers
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
                    <th>Name</th>
                    <th>Client Key</th>
                    <th>Description</th>
                    <th>Servers</th>
                  </tr>
                </thead>
                <tbody>
                  {routings.map((routing) => (
                    <tr 
                      key={routing.client_key} 
                      onClick={() => handleRoutingClick(routing)}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = ''}
                    >
                      <td>{routing.routing_name}</td>
                      <td>{routing.client_key}</td>
                      <td>{routing.routing_description || 'No description'}</td>
                      <td>
                        <span className="routings-servers-badge">
                          {routing.routing_servers.length} server{routing.routing_servers.length !== 1 ? 's' : ''}
                        </span>
                      </td>
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
