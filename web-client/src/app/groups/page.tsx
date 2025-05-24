'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './groups.css';

interface Group {
  id: string;
  name: string;
  description: string;
  memberCount: number;
  createdBy: string;
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

const groups = [
  {
    name: 'c1-group',
    members: 5,
    role: 'Client',
    subscriptions: 12,
  },
];

const handleLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  setTimeout(() => {
    window.location.replace('/');
  }, 50);
};

const GroupsPage = () => {
  const [theme, setTheme] = useState('light');
  const [groups, setGroups] = useState<Group[]>([]);
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
    fetchGroups();
  }, []);

  const fetchGroups = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/groups`);
      if (!response.ok) {
        throw new Error('Failed to load groups');
      }
      const data = await response.json();
      setGroups(data);
    } catch (err) {
      setError('Failed to load groups. Please try again later.');
      setGroups([]);
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
    const sortedGroups = [...groups].sort((a, b) => {
      if (sortField === 'name') {
        return a.name.localeCompare(b.name);
      } else if (sortField === 'memberCount') {
        return b.memberCount - a.memberCount;
      } else if (sortField === 'createdAt') {
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      }
      return 0;
    });
    setGroups(sortedGroups);
  };

  return (
    <>
      <div className="groups-topbar">
      Doorman
      </div>
      <div className="groups-root">
        <aside className="groups-sidebar">
          <div className="groups-sidebar-title">Menu</div>
          <ul className="groups-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`groups-sidebar-item${idx === 4 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`groups-sidebar-item${idx === 4 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="groups-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="groups-main">
          <div className="groups-header-row">
            <h1 className="groups-title">Groups</h1>
            <button className="refresh-button" onClick={fetchGroups}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="groups-controls">
            <form className="groups-search-box" onSubmit={handleSearch}>
              <input
                type="text"
                className="groups-search-input"
                placeholder="Search groups..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <button type="submit" className="groups-search-btn">Search</button>
              <button type="button" className="groups-add-btn">Add Group</button>
            </form>
            <div className="groups-sort-group">
              <button 
                className={`groups-sort-btn ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => handleSort('name')}
              >
                Name
              </button>
              <button 
                className={`groups-sort-btn ${sortBy === 'members' ? 'active' : ''}`}
                onClick={() => handleSort('members')}
              >
                Members
              </button>
              <button 
                className={`groups-sort-btn ${sortBy === 'created' ? 'active' : ''}`}
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
              <p>Loading groups...</p>
            </div>
          ) : (
            <div className="groups-table-panel">
              <table className="groups-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Members</th>
                    <th>Created By</th>
                    <th>Created At</th>
                    <th>Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <tr key={group.id}>
                      <td>{group.name}</td>
                      <td>{group.description}</td>
                      <td>{group.memberCount}</td>
                      <td>{group.createdBy}</td>
                      <td>{new Date(group.createdAt).toLocaleDateString()}</td>
                      <td>{new Date(group.lastUpdated).toLocaleDateString()}</td>
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

export default GroupsPage;