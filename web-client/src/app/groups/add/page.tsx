'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import '../groups.css';

interface CreateGroupData {
  group_name: string;
  group_description: string;
  api_access: string[];
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

const AddGroupPage = () => {
  const router = useRouter();
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<CreateGroupData>({
    group_name: '',
    group_description: '',
    api_access: []
  });
  const [newApi, setNewApi] = useState('');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const handleInputChange = (field: keyof CreateGroupData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addApi = () => {
    if (newApi.trim() && !formData.api_access.includes(newApi.trim())) {
      setFormData(prev => ({
        ...prev,
        api_access: [...prev.api_access, newApi.trim()]
      }));
      setNewApi('');
    }
  };

  const removeApi = (index: number) => {
    setFormData(prev => ({
      ...prev,
      api_access: prev.api_access.filter((_, i) => i !== index)
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.group_name.trim()) {
      setError('Group name is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:3002/platform/group', {
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
        throw new Error(errorData.error_message || 'Failed to create group');
      }

      // Redirect back to groups list after successful creation
      router.push('/groups');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create group');
    } finally {
      setLoading(false);
    }
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
            <Link href="/groups" className="back-button" style={{ textDecoration: 'none', display: 'inline-block' }}>
              <span className="back-arrow">←</span>
              Back to Groups
            </Link>
            <h1 className="groups-title">Add Group</h1>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="add-group-form">
            <form onSubmit={handleSubmit}>
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-group">
                  <label className="form-label">Group Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.group_name}
                    onChange={(e) => handleInputChange('group_name', e.target.value)}
                    placeholder="Enter group name"
                    maxLength={50}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-input"
                    value={formData.group_description}
                    onChange={(e) => handleInputChange('group_description', e.target.value)}
                    placeholder="Enter group description"
                    maxLength={255}
                    rows={3}
                  />
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">API Access</h2>
                <div className="form-group">
                  <label className="form-label">APIs</label>
                  <div className="api-access-container">
                    <div className="api-access-list">
                      {formData.api_access.map((api, index) => (
                        <span key={index} className="api-access-tag">
                          {api}
                          <button
                            type="button"
                            className="remove-api-btn"
                            onClick={() => removeApi(index)}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="add-api">
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Enter API name"
                        value={newApi}
                        onChange={(e) => setNewApi(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addApi())}
                      />
                      <button
                        type="button"
                        className="add-button"
                        onClick={addApi}
                      >
                        Add API
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="form-actions">
                <Link href="/groups" className="cancel-button" style={{ textDecoration: 'none', display: 'inline-block' }}>
                  Cancel
                </Link>
                <button
                  type="submit"
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Creating...' : 'Create Group'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </>
  );
};

export default AddGroupPage; 