'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './users.css';

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  lastLogin: string;
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

const UsersPage = () => {
  const [theme, setTheme] = useState('light');
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('username');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/users`);
      if (!response.ok) {
        throw new Error('Failed to load users');
      }
      const data = await response.json();
      setUsers(data);
    } catch (err) {
      setError('Failed to load users. Please try again later.');
      setUsers([]);
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
    const sortedUsers = [...users].sort((a, b) => {
      if (sortField === 'username') {
        return a.username.localeCompare(b.username);
      } else if (sortField === 'role') {
        return a.role.localeCompare(b.role);
      } else if (sortField === 'status') {
        return a.status.localeCompare(b.status);
      }
      return 0;
    });
    setUsers(sortedUsers);
  };

  return (
    <>
      <div className="users-topbar">
      Doorman
      </div>
      <div className="users-root">
        <aside className="users-sidebar">
          <div className="users-sidebar-title">Menu</div>
          <ul className="users-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`users-sidebar-item${idx === 3 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`users-sidebar-item${idx === 3 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="users-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="users-main">
          <div className="users-header-row">
            <h1 className="users-title">Users</h1>
            <button className="refresh-button" onClick={fetchUsers}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="users-controls">
            <form className="users-search-box" onSubmit={handleSearch}>
              <input
                type="text"
                className="users-search-input"
                placeholder="Search users..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button type="submit" className="users-search-btn">Search</button>
              <button type="button" className="users-add-btn">Add User</button>
            </form>
            <div className="users-sort-group">
              <button 
                className={`users-sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => handleSort('name')}
              >
                Name
              </button>
              <button 
                className={`users-sort-btn ${sortBy === 'role' ? 'active' : ''}`}
                onClick={() => handleSort('role')}
              >
                Role
              </button>
              <button 
                className={`users-sort-btn ${sortBy === 'status' ? 'active' : ''}`}
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
              <p>Loading users...</p>
            </div>
          ) : (
            <div className="users-table-panel">
              <table className="users-table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Last Login</th>
                    <th>Created At</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.username}</td>
                      <td>{user.email}</td>
                      <td>{user.role}</td>
                      <td>{user.status}</td>
                      <td>{new Date(user.lastLogin).toLocaleDateString()}</td>
                      <td>{new Date(user.createdAt).toLocaleDateString()}</td>
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

export default UsersPage;