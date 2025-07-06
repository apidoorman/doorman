'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import './roles.css';

interface Role {
  role_name: string;
  role_description: string;
  manage_users?: boolean;
  manage_apis?: boolean;
  manage_endpoints?: boolean;
  manage_groups?: boolean;
  manage_roles?: boolean;
  manage_routings?: boolean;
  manage_gateway?: boolean;
  manage_subscriptions?: boolean;
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

const RolesPage = () => {
  const router = useRouter();
  const [theme, setTheme] = useState('light');
  const [roles, setRoles] = useState<Role[]>([]);
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('role_name');

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
      const response = await fetch(`http://localhost:3002/platform/role/all?page=1&page_size=10`, {
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
      
      setAllRoles(data.roles);
      setRoles(data.roles);
    } catch (err) {
      setError('Failed to load roles. Please try again later.');
      setRoles([]);
      setAllRoles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) {
      setRoles(allRoles);
      return;
    }
    
    const filteredRoles = allRoles.filter(role => 
      role.role_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      role.role_description?.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setRoles(filteredRoles);
  };

  const handleSort = (sortField: string) => {
    setSortBy(sortField);
    const sortedRoles = [...roles].sort((a, b) => {
      if (sortField === 'role_name') {
        return a.role_name.localeCompare(b.role_name);
      } else if (sortField === 'permissions') {
        const aPerms = Object.values(a).filter(val => typeof val === 'boolean' && val).length;
        const bPerms = Object.values(b).filter(val => typeof val === 'boolean' && val).length;
        return bPerms - aPerms;
      }
      return 0;
    });
    setRoles(sortedRoles);
  };

  const handleRoleClick = (role: Role) => {
    // Store role data in sessionStorage for the detail page
    sessionStorage.setItem('selectedRole', JSON.stringify(role));
    router.push(`/roles/${role.role_name}`);
  };

  const getPermissionCount = (role: Role) => {
    return Object.values(role).filter(val => typeof val === 'boolean' && val).length;
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
              <Link href="/roles/add" className="roles-add-btn" style={{ textDecoration: 'none', display: 'inline-block' }}>
                Add Role
              </Link>
            </form>
            <div className="roles-sort-group">
              <button 
                className={`roles-sort-btn ${sortBy === 'role_name' ? 'active' : ''}`}
                onClick={() => handleSort('role_name')}
              >
                Name
              </button>
              <button 
                className={`roles-sort-btn ${sortBy === 'permissions' ? 'active' : ''}`}
                onClick={() => handleSort('permissions')}
              >
                Permissions
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
                    <th>Permissions</th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map((role) => (
                    <tr 
                      key={role.role_name} 
                      onClick={() => handleRoleClick(role)}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = ''}
                    >
                      <td><b>{role.role_name}</b></td>
                      <td>{role.role_description || 'No description'}</td>
                      <td>
                        <span className="roles-permissions-badge">
                          {getPermissionCount(role)} permission{getPermissionCount(role) !== 1 ? 's' : ''}
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

export default RolesPage;