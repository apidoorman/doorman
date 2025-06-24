'use client'

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import '../apis.css';
import './add-api.css';

interface CreateApiData {
  api_name: string;
  api_version: string;
  api_description: string;
  api_allowed_roles: string[];
  api_allowed_groups: string[];
  api_servers: string[];
  api_type: string;
  api_allowed_retry_count: number;
  api_authorization_field_swap?: string;
  api_allowed_headers?: string[];
  api_tokens_enabled: boolean;
  api_token_group?: string;
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

const AddApiPage = () => {
  const router = useRouter();
  const [formData, setFormData] = useState<CreateApiData>({
    api_name: '',
    api_version: '',
    api_description: '',
    api_allowed_roles: [],
    api_allowed_groups: [],
    api_servers: [],
    api_type: 'REST',
    api_allowed_retry_count: 0,
    api_tokens_enabled: false
  });
  const [newRole, setNewRole] = useState('');
  const [newGroup, setNewGroup] = useState('');
  const [newServer, setNewServer] = useState('');
  const [newHeader, setNewHeader] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (field: keyof CreateApiData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addRole = () => {
    if (newRole.trim()) {
      setFormData(prev => ({ ...prev, api_allowed_roles: [...prev.api_allowed_roles, newRole.trim()] }));
      setNewRole('');
    }
  };

  const removeRole = (index: number) => {
    setFormData(prev => ({ ...prev, api_allowed_roles: prev.api_allowed_roles.filter((_, i) => i !== index) }));
  };

  const addGroup = () => {
    if (newGroup.trim()) {
      setFormData(prev => ({ ...prev, api_allowed_groups: [...prev.api_allowed_groups, newGroup.trim()] }));
      setNewGroup('');
    }
  };

  const removeGroup = (index: number) => {
    setFormData(prev => ({ ...prev, api_allowed_groups: prev.api_allowed_groups.filter((_, i) => i !== index) }));
  };

  const addServer = () => {
    if (newServer.trim()) {
      setFormData(prev => ({ ...prev, api_servers: [...prev.api_servers, newServer.trim()] }));
      setNewServer('');
    }
  };

  const removeServer = (index: number) => {
    setFormData(prev => ({ ...prev, api_servers: prev.api_servers.filter((_, i) => i !== index) }));
  };

  const addHeader = () => {
    if (newHeader.trim()) {
      setFormData(prev => ({ 
        ...prev, 
        api_allowed_headers: [...(prev.api_allowed_headers || []), newHeader.trim()] 
      }));
      setNewHeader('');
    }
  };

  const removeHeader = (index: number) => {
    setFormData(prev => ({ 
      ...prev, 
      api_allowed_headers: prev.api_allowed_headers?.filter((_, i) => i !== index) || [] 
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.api_name || !formData.api_version || !formData.api_description) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:3002/platform/api/', {
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
        throw new Error(errorData.error_message || 'Failed to create API');
      }

      // Redirect to APIs list after successful creation
      router.push('/apis');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create API');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    router.back();
  };

  return (
    <>
      <div className="apis-topbar">
        Doorman
      </div>
      <div className="apis-root">
        <aside className="apis-sidebar">
          <div className="apis-sidebar-title">Menu</div>
          <ul className="apis-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`apis-sidebar-item${idx === 1 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`apis-sidebar-item${idx === 1 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="apis-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="apis-main">
          <div className="apis-header-row">
            <div className="add-api-header">
              <button className="back-button" onClick={handleBack}>
                <span className="back-arrow">←</span>
                Back to APIs
              </button>
              <h1 className="apis-title">Add New API</h1>
            </div>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="add-api-content">
            <form onSubmit={handleSubmit} className="add-api-form">
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">API Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.api_name}
                      onChange={(e) => handleInputChange('api_name', e.target.value)}
                      placeholder="Enter API name"
                      minLength={1}
                      maxLength={25}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">API Version *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.api_version}
                      onChange={(e) => handleInputChange('api_version', e.target.value)}
                      placeholder="Enter API version"
                      minLength={1}
                      maxLength={8}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">API Type</label>
                    <select
                      className="form-select"
                      value={formData.api_type}
                      onChange={(e) => handleInputChange('api_type', e.target.value)}
                    >
                      <option value="REST">REST</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Retry Count</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.api_allowed_retry_count}
                      onChange={(e) => handleInputChange('api_allowed_retry_count', parseInt(e.target.value) || 0)}
                      min="0"
                      placeholder="0"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Description *</label>
                  <textarea
                    className="form-textarea"
                    value={formData.api_description}
                    onChange={(e) => handleInputChange('api_description', e.target.value)}
                    placeholder="Enter API description"
                    minLength={1}
                    maxLength={127}
                    required
                    rows={3}
                  />
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Roles</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {formData.api_allowed_roles.map((role, index) => (
                      <span key={index} className="group-tag">
                        {role}
                        <button
                          type="button"
                          className="remove-group-btn"
                          onClick={() => removeRole(index)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="add-group">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter role name"
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addRole())}
                    />
                    <button type="button" className="add-button" onClick={addRole}>
                      Add Role
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Groups</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {formData.api_allowed_groups.map((group, index) => (
                      <span key={index} className="group-tag">
                        {group}
                        <button
                          type="button"
                          className="remove-group-btn"
                          onClick={() => removeGroup(index)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="add-group">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter group name"
                      value={newGroup}
                      onChange={(e) => setNewGroup(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addGroup())}
                    />
                    <button type="button" className="add-button" onClick={addGroup}>
                      Add Group
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Backend Servers</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {formData.api_servers.map((server, index) => (
                      <span key={index} className="group-tag">
                        {server}
                        <button
                          type="button"
                          className="remove-group-btn"
                          onClick={() => removeServer(index)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="add-group">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter server URL (e.g., http://localhost:8080)"
                      value={newServer}
                      onChange={(e) => setNewServer(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addServer())}
                    />
                    <button type="button" className="add-button" onClick={addServer}>
                      Add Server
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Authorization & Headers</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Authorization Field Swap</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.api_authorization_field_swap || ''}
                      onChange={(e) => handleInputChange('api_authorization_field_swap', e.target.value)}
                      placeholder="e.g., backend-auth-header"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Token Group</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.api_token_group || ''}
                      onChange={(e) => handleInputChange('api_token_group', e.target.value)}
                      placeholder="e.g., ai-group-1"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tokens Enabled</label>
                    <select
                      className="form-select"
                      value={formData.api_tokens_enabled ? 'true' : 'false'}
                      onChange={(e) => handleInputChange('api_tokens_enabled', e.target.value === 'true')}
                    >
                      <option value="false">Disabled</option>
                      <option value="true">Enabled</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Headers</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {(formData.api_allowed_headers || []).map((header, index) => (
                      <span key={index} className="group-tag">
                        {header}
                        <button
                          type="button"
                          className="remove-group-btn"
                          onClick={() => removeHeader(index)}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="add-group">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter header name (e.g., Content-Type)"
                      value={newHeader}
                      onChange={(e) => setNewHeader(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addHeader())}
                    />
                    <button type="button" className="add-button" onClick={addHeader}>
                      Add Header
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-actions">
                <button type="button" className="cancel-button" onClick={handleBack}>
                  Cancel
                </button>
                <button type="submit" className="save-button" disabled={loading}>
                  {loading ? 'Creating API...' : 'Create API'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </>
  );
};

export default AddApiPage; 