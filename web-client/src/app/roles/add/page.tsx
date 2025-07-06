'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import '../roles.css';

interface CreateRoleData {
  role_name: string;
  role_description: string;
  manage_users: boolean;
  manage_apis: boolean;
  manage_endpoints: boolean;
  manage_groups: boolean;
  manage_roles: boolean;
  manage_routings: boolean;
  manage_gateway: boolean;
  manage_subscriptions: boolean;
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

const AddRolePage = () => {
  const router = useRouter();
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<CreateRoleData>({
    role_name: '',
    role_description: '',
    manage_users: false,
    manage_apis: false,
    manage_endpoints: false,
    manage_groups: false,
    manage_roles: false,
    manage_routings: false,
    manage_gateway: false,
    manage_subscriptions: false
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const handleInputChange = (field: keyof CreateRoleData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.role_name.trim()) {
      setError('Role name is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:3002/platform/role', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error_message || 'Failed to create role');
      }

      // Redirect back to roles list after successful creation
      router.push('/roles');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      setLoading(false);
    }
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
            <Link href="/roles" className="back-button" style={{ textDecoration: 'none', display: 'inline-block' }}>
              <span className="back-arrow">←</span>
              Back to Roles
            </Link>
            <h1 className="roles-title">Add Role</h1>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="add-role-form">
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-group">
                  <label className="form-label">Role Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.role_name}
                    onChange={(e) => handleInputChange('role_name', e.target.value)}
                    placeholder="Enter role name"
                    maxLength={50}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-input"
                    value={formData.role_description}
                    onChange={(e) => handleInputChange('role_description', e.target.value)}
                    placeholder="Enter role description"
                    maxLength={255}
                    rows={3}
                  />
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Permissions</h2>
                <div className="permissions-grid">
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_users}
                        onChange={(e) => handleInputChange('manage_users', e.target.checked)}
                      />
                      <span className="permission-text">Manage Users</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_apis}
                        onChange={(e) => handleInputChange('manage_apis', e.target.checked)}
                      />
                      <span className="permission-text">Manage APIs</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_endpoints}
                        onChange={(e) => handleInputChange('manage_endpoints', e.target.checked)}
                      />
                      <span className="permission-text">Manage Endpoints</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_groups}
                        onChange={(e) => handleInputChange('manage_groups', e.target.checked)}
                      />
                      <span className="permission-text">Manage Groups</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_roles}
                        onChange={(e) => handleInputChange('manage_roles', e.target.checked)}
                      />
                      <span className="permission-text">Manage Roles</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_routings}
                        onChange={(e) => handleInputChange('manage_routings', e.target.checked)}
                      />
                      <span className="permission-text">Manage Routings</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_gateway}
                        onChange={(e) => handleInputChange('manage_gateway', e.target.checked)}
                      />
                      <span className="permission-text">Manage Gateway</span>
                    </label>
                  </div>
                  <div className="permission-item">
                    <label className="permission-label">
                      <input
                        type="checkbox"
                        checked={formData.manage_subscriptions}
                        onChange={(e) => handleInputChange('manage_subscriptions', e.target.checked)}
                      />
                      <span className="permission-text">Manage Subscriptions</span>
                    </label>
                  </div>
                </div>
              </div>

              <div className="form-actions">
                <Link href="/roles" className="cancel-button" style={{ textDecoration: 'none', display: 'inline-block' }}>
                  Cancel
                </Link>
                <button
                  type="submit"
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Creating...' : 'Create Role'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </>
  );
};

export default AddRolePage; 