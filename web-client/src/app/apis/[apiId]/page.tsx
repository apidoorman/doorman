'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import './api-detail.css';

interface API {
  api_id: string;
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
  api_path?: string;
}

interface UpdateApiData {
  api_name?: string;
  api_version?: string;
  api_description?: string;
  api_allowed_roles?: string[];
  api_allowed_groups?: string[];
  api_servers?: string[];
  api_type?: string;
  api_allowed_retry_count?: number;
  api_authorization_field_swap?: string;
  api_allowed_headers?: string[];
  api_tokens_enabled?: boolean;
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

const ApiDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const apiId = params.apiId as string;
  const [api, setApi] = useState<API | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editData, setEditData] = useState<UpdateApiData>({});
  const [newRole, setNewRole] = useState('');
  const [newGroup, setNewGroup] = useState('');
  const [newServer, setNewServer] = useState('');
  const [newHeader, setNewHeader] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const apiData = sessionStorage.getItem('selectedApi');
    if (apiData) {
      try {
        const parsedApi = JSON.parse(apiData);
        setApi(parsedApi);
        setEditData({
          api_name: parsedApi.api_name,
          api_version: parsedApi.api_version,
          api_description: parsedApi.api_description,
          api_allowed_roles: [...(parsedApi.api_allowed_roles || [])],
          api_allowed_groups: [...(parsedApi.api_allowed_groups || [])],
          api_servers: [...(parsedApi.api_servers || [])],
          api_type: parsedApi.api_type,
          api_allowed_retry_count: parsedApi.api_allowed_retry_count,
          api_authorization_field_swap: parsedApi.api_authorization_field_swap,
          api_allowed_headers: [...(parsedApi.api_allowed_headers || [])],
          api_tokens_enabled: parsedApi.api_tokens_enabled,
          api_token_group: parsedApi.api_token_group
        });
        setLoading(false);
      } catch (err) {
        setError('Failed to load API data');
        setLoading(false);
      }
    } else {
      setError('No API data found');
      setLoading(false);
    }
  }, [apiId]);

  const handleBack = () => {
    router.back();
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError(null);
    // Reset edit data to original values
    if (api) {
      setEditData({
        api_name: api.api_name,
        api_version: api.api_version,
        api_description: api.api_description,
        api_allowed_roles: [...(api.api_allowed_roles || [])],
        api_allowed_groups: [...(api.api_allowed_groups || [])],
        api_servers: [...(api.api_servers || [])],
        api_type: api.api_type,
        api_allowed_retry_count: api.api_allowed_retry_count,
        api_authorization_field_swap: api.api_authorization_field_swap,
        api_allowed_headers: [...(api.api_allowed_headers || [])],
        api_tokens_enabled: api.api_tokens_enabled,
        api_token_group: api.api_token_group
      });
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      if (!api) {
        throw new Error('No API data available');
      }

      const response = await fetch(`http://localhost:3002/platform/api/${api.api_name}/${api.api_version}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        },
        body: JSON.stringify(editData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error_message || 'Failed to update API');
      }

      // Update the API data in sessionStorage and state
      if (api) {
        const updatedApi: API = {
          ...api,
          ...editData,
          api_name: editData.api_name || api.api_name,
          api_version: editData.api_version || api.api_version,
          api_description: editData.api_description || api.api_description,
          api_allowed_roles: editData.api_allowed_roles || api.api_allowed_roles,
          api_allowed_groups: editData.api_allowed_groups || api.api_allowed_groups,
          api_servers: editData.api_servers || api.api_servers,
          api_type: editData.api_type || api.api_type,
          api_allowed_retry_count: editData.api_allowed_retry_count ?? api.api_allowed_retry_count,
          api_authorization_field_swap: editData.api_authorization_field_swap,
          api_allowed_headers: editData.api_allowed_headers || api.api_allowed_headers,
          api_tokens_enabled: editData.api_tokens_enabled ?? api.api_tokens_enabled,
          api_token_group: editData.api_token_group
        };
        sessionStorage.setItem('selectedApi', JSON.stringify(updatedApi));
        setApi(updatedApi);
      }
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update API');
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: keyof UpdateApiData, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const addRole = () => {
    if (newRole.trim()) {
      setEditData(prev => ({ 
        ...prev, 
        api_allowed_roles: [...(prev.api_allowed_roles || []), newRole.trim()] 
      }));
      setNewRole('');
    }
  };

  const removeRole = (index: number) => {
    setEditData(prev => ({ 
      ...prev, 
      api_allowed_roles: prev.api_allowed_roles?.filter((_, i) => i !== index) || [] 
    }));
  };

  const addGroup = () => {
    if (newGroup.trim()) {
      setEditData(prev => ({ 
        ...prev, 
        api_allowed_groups: [...(prev.api_allowed_groups || []), newGroup.trim()] 
      }));
      setNewGroup('');
    }
  };

  const removeGroup = (index: number) => {
    setEditData(prev => ({ 
      ...prev, 
      api_allowed_groups: prev.api_allowed_groups?.filter((_, i) => i !== index) || [] 
    }));
  };

  const addServer = () => {
    if (newServer.trim()) {
      setEditData(prev => ({ 
        ...prev, 
        api_servers: [...(prev.api_servers || []), newServer.trim()] 
      }));
      setNewServer('');
    }
  };

  const removeServer = (index: number) => {
    setEditData(prev => ({ 
      ...prev, 
      api_servers: prev.api_servers?.filter((_, i) => i !== index) || [] 
    }));
  };

  const addHeader = () => {
    if (newHeader.trim()) {
      setEditData(prev => ({ 
        ...prev, 
        api_allowed_headers: [...(prev.api_allowed_headers || []), newHeader.trim()] 
      }));
      setNewHeader('');
    }
  };

  const removeHeader = (index: number) => {
    setEditData(prev => ({ 
      ...prev, 
      api_allowed_headers: prev.api_allowed_headers?.filter((_, i) => i !== index) || [] 
    }));
  };

  const handleDeleteClick = () => {
    setShowDeleteModal(true);
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setDeleteConfirmation('');
  };

  const handleDeleteConfirm = async () => {
    if (!api) {
      setError('No API data available');
      return;
    }

    if (deleteConfirmation !== api.api_name) {
      setError('Please enter the correct API name to confirm deletion');
      return;
    }

    try {
      setDeleting(true);
      setError(null);

      const response = await fetch(`http://localhost:3002/platform/api/${api.api_name}/${api.api_version}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error_message || 'Failed to delete API');
      }

      // Redirect to APIs list after successful deletion
      router.push('/apis');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete API');
    } finally {
      setDeleting(false);
      setShowDeleteModal(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner"></div>
        <p>Loading API...</p>
      </div>
    );
  }

  if (!api) {
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
            <div className="api-detail-header">
              <button className="back-button" onClick={handleBack}>
                <span className="back-arrow">←</span>
                Back to APIs
              </button>
              <h1 className="apis-title">API Details</h1>
            </div>

            {error && (
              <div className="error-container">
                <div className="error-message">
                  {error}
                </div>
              </div>
            )}
          </main>
        </div>
      </>
    );
  }

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
          <div className="api-detail-header">
            <button className="back-button" onClick={handleBack}>
              <span className="back-arrow">←</span>
              Back to APIs
            </button>
            <h1 className="apis-title">{api.api_name}</h1>
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit API
              </button>
            ) : (
              <div className="edit-actions">
                <button className="save-button" onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button className="cancel-button" onClick={handleCancel} disabled={saving}>
                  Cancel
                </button>
                <button className="delete-button" onClick={handleDeleteClick} disabled={saving}>
                  Delete API
                </button>
              </div>
            )}
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="api-detail-content">
            <div className="api-detail-form">
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">API Name</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="form-input"
                        value={editData.api_name || ''}
                        onChange={(e) => handleInputChange('api_name', e.target.value)}
                        placeholder="Enter API name"
                        minLength={1}
                        maxLength={25}
                      />
                    ) : (
                      <div className="form-value">{api.api_name}</div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">API Version</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="form-input"
                        value={editData.api_version || ''}
                        onChange={(e) => handleInputChange('api_version', e.target.value)}
                        placeholder="Enter API version"
                        minLength={1}
                        maxLength={8}
                      />
                    ) : (
                      <div className="form-value">{api.api_version}</div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">API Type</label>
                    {isEditing ? (
                      <select
                        className="form-select"
                        value={editData.api_type || ''}
                        onChange={(e) => handleInputChange('api_type', e.target.value)}
                      >
                        <option value="REST">REST</option>
                      </select>
                    ) : (
                      <div className="form-value">{api.api_type}</div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Retry Count</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="form-input"
                        value={editData.api_allowed_retry_count || 0}
                        onChange={(e) => handleInputChange('api_allowed_retry_count', parseInt(e.target.value) || 0)}
                        min="0"
                      />
                    ) : (
                      <div className="form-value">{api.api_allowed_retry_count}</div>
                    )}
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  {isEditing ? (
                    <textarea
                      className="form-textarea"
                      value={editData.api_description || ''}
                      onChange={(e) => handleInputChange('api_description', e.target.value)}
                      placeholder="Enter API description"
                      minLength={1}
                      maxLength={127}
                      rows={3}
                    />
                  ) : (
                    <div className="form-value">{api.api_description}</div>
                  )}
                </div>
                {api.api_path && (
                  <div className="form-group">
                    <label className="form-label">API Path</label>
                    <div className="form-value">{api.api_path}</div>
                  </div>
                )}
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Roles</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {(isEditing ? editData.api_allowed_roles : api.api_allowed_roles)?.map((role, index) => (
                      <span key={index} className="group-tag">
                        {role}
                        {isEditing && (
                          <button
                            type="button"
                            className="remove-group-btn"
                            onClick={() => removeRole(index)}
                          >
                            ×
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                  {isEditing && (
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
                  )}
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Groups</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {(isEditing ? editData.api_allowed_groups : api.api_allowed_groups)?.map((group, index) => (
                      <span key={index} className="group-tag">
                        {group}
                        {isEditing && (
                          <button
                            type="button"
                            className="remove-group-btn"
                            onClick={() => removeGroup(index)}
                          >
                            ×
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                  {isEditing && (
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
                  )}
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Backend Servers</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {(isEditing ? editData.api_servers : api.api_servers)?.map((server, index) => (
                      <span key={index} className="group-tag">
                        {server}
                        {isEditing && (
                          <button
                            type="button"
                            className="remove-group-btn"
                            onClick={() => removeServer(index)}
                          >
                            ×
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                  {isEditing && (
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
                  )}
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Authorization & Headers</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Authorization Field Swap</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="form-input"
                        value={editData.api_authorization_field_swap || ''}
                        onChange={(e) => handleInputChange('api_authorization_field_swap', e.target.value)}
                        placeholder="e.g., backend-auth-header"
                      />
                    ) : (
                      <div className="form-value">{api.api_authorization_field_swap || 'Not set'}</div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Token Group</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="form-input"
                        value={editData.api_token_group || ''}
                        onChange={(e) => handleInputChange('api_token_group', e.target.value)}
                        placeholder="e.g., ai-group-1"
                      />
                    ) : (
                      <div className="form-value">{api.api_token_group || 'Not set'}</div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tokens Enabled</label>
                    {isEditing ? (
                      <select
                        className="form-select"
                        value={editData.api_tokens_enabled ? 'true' : 'false'}
                        onChange={(e) => handleInputChange('api_tokens_enabled', e.target.value === 'true')}
                      >
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                      </select>
                    ) : (
                      <div className="form-value">{api.api_tokens_enabled ? 'Enabled' : 'Disabled'}</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Allowed Headers</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {(isEditing ? editData.api_allowed_headers : api.api_allowed_headers)?.map((header, index) => (
                      <span key={index} className="group-tag">
                        {header}
                        {isEditing && (
                          <button
                            type="button"
                            className="remove-group-btn"
                            onClick={() => removeHeader(index)}
                          >
                            ×
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                  {isEditing && (
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
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {showDeleteModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Delete API</h2>
            <p>Are you sure you want to delete the API "{api.api_name}"? This action cannot be undone.</p>
            <p>Please type the API name to confirm: <strong>{api.api_name}</strong></p>
            <input
              type="text"
              className="form-input"
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              placeholder="Enter API name to confirm"
            />
            <div className="modal-actions">
              <button className="cancel-button" onClick={handleDeleteCancel}>
                Cancel
              </button>
              <button className="delete-button" onClick={handleDeleteConfirm} disabled={deleting}>
                {deleting ? 'Deleting...' : 'Delete API'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ApiDetailPage; 