'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import './groups.css';

interface Group {
  group_name: string;
  group_description: string;
  api_access?: string[];
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

const GroupsPage = () => {
  const router = useRouter();
  const [theme, setTheme] = useState('light');
  const [groups, setGroups] = useState<Group[]>([]);
  const [allGroups, setAllGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('group_name');

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
      const response = await fetch(`http://localhost:3002/platform/group/all?page=1&page_size=10`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to load groups');
      }
      const data = await response.json();
      setAllGroups(data.groups);
      setGroups(data.groups);
    } catch (err) {
      setError('Failed to load groups. Please try again later.');
      setGroups([]);
      setAllGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) {
      setGroups(allGroups);
      return;
    }
    
    const filteredGroups = allGroups.filter(group => 
      group.group_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.group_description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.api_access?.some(api => api.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setGroups(filteredGroups);
  };

  const handleSort = (sortField: string) => {
    setSortBy(sortField);
    const sortedGroups = [...groups].sort((a, b) => {
      if (sortField === 'group_name') {
        return a.group_name.localeCompare(b.group_name);
      } else if (sortField === 'api_access') {
        return (a.api_access?.length || 0) - (b.api_access?.length || 0);
      }
      return 0;
    });
    setGroups(sortedGroups);
  };

  const handleGroupClick = (group: Group) => {
    // Store group data in sessionStorage for the detail page
    sessionStorage.setItem('selectedGroup', JSON.stringify(group));
    router.push(`/groups/${group.group_name}`);
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
              <Link href="/groups/add" className="groups-add-btn" style={{ textDecoration: 'none', display: 'inline-block' }}>
                Add Group
              </Link>
            </form>
            <div className="groups-sort-group">
              <button 
                className={`groups-sort-btn ${sortBy === 'group_name' ? 'active' : ''}`}
                onClick={() => handleSort('group_name')}
              >
                Name
              </button>
              <button 
                className={`groups-sort-btn ${sortBy === 'api_access' ? 'active' : ''}`}
                onClick={() => handleSort('api_access')}
              >
                API Access
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
                    <th>API Access</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <tr 
                      key={group.group_name} 
                      onClick={() => handleGroupClick(group)}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = ''}
                    >
                      <td><b>{group.group_name}</b></td>
                      <td>{group.group_description || 'No description'}</td>
                      <td>
                        <span className="groups-api-badge">
                          {group.api_access?.length || 0} API{(group.api_access?.length || 0) !== 1 ? 's' : ''}
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

export default GroupsPage;