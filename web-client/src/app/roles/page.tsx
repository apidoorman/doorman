'use client'

import React, { useState, useEffect, ReactNode } from 'react';
import Link from 'next/link';
import './roles.css';

interface Role {
  role_description: ReactNode;
  role_permissions: ReactNode;
  role_name: ReactNode;
  id: string;
  name: string;
  description: string;
  permissions: string[];
  userCount: number;
  createdAt: string;
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
  { label: 'Security', href: '/security' },
  { label: 'Settings', href: '/settings' },
];

const roles = [
  {
    name: 'Client',
    description: 'Client role',
    users: 3,
    permissions: 'Read, Write',
  },
];

const handleLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  setTimeout(() => {
    window.location.replace('/');
  }, 50);
};

const RolesPage = () => {
  const [theme, setTheme] = useState('light');
  const [roles, setRoles] = useState<Role[]>([]);
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
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`http://localhost:3002/platform/role/all`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to load roles');
      }
      const data = await response.json();
      const roleList = Array.isArray(data) ? data : (data.roles || data.response?.roles || []);
      setRoles(roleList);
    } catch (err) {
      setError('Failed to load roles. Please try again later.');
      setRoles([]);
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
    const sortedRoles = [...roles].sort((a, b) => {
      if (sortField === 'name') {
        return a.name.localeCompare(b.name);
      } else if (sortField === 'userCount') {
        return b.userCount - a.userCount;
      } else if (sortField === 'createdAt') {
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      }
      return 0;
    });
    setRoles(sortedRoles);
  };

  return (
    <>
      <div className="roles-topbar">
      Doorman
      </div>
      <div className="roles-root">
        <aside className="roles-sidebar">
          <div className="roles-sidebar-title">Menu</div>
          <ul className="roles-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`roles-sidebar-item${idx === 5 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`roles-sidebar-item${idx === 5 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="roles-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="roles-main">
          <div className="roles-header-row">
            <h1 className="roles-title">Roles</h1>
            <button className="refresh-button" onClick={fetchRoles}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="roles-controls">
            <form className="roles-search-box" onSubmit={handleSearch}>
              <input
                type="text"
                className="roles-search-input"
                placeholder="Search roles..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button type="submit" className="roles-search-btn">Search</button>
              <button type="button" className="roles-add-btn">Add Role</button>
            </form>
            <div className="roles-sort-group">
              <button 
                className={`roles-sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => handleSort('name')}
              >
                Name
              </button>
              <button 
                className={`roles-sort-btn ${sortBy === 'users' ? 'active' : ''}`}
                onClick={() => handleSort('users')}
              >
                Users
              </button>
              <button 
                className={`roles-sort-btn ${sortBy === 'created' ? 'active' : ''}`}
                onClick={() => handleSort('created')}
              >
                Created
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
              <p>Loading roles...</p>
            </div>
          ) : (
            <div className="roles-table-panel">
              <table className="roles-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map((role, index) => (
                    <tr key={`${role.id}-${index}`}>
                      <td>{role.role_name}</td>
                      <td>{role.role_description}</td>
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

export default RolesPage;