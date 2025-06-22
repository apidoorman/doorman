'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import './user-detail.css';

interface User {
  username: string;
  email: string;
  role: string;
  groups: string[];
  rate_limit_duration: number;
  rate_limit_duration_type: string;
  throttle_duration: number;
  throttle_duration_type: string;
  throttle_wait_duration: number;
  throttle_wait_duration_type: string;
  throttle_queue_limit: number | null;
  custom_attributes: Record<string, string>;
  active: boolean;
  ui_access?: boolean;
}

interface UpdateUserData {
  username?: string;
  email?: string;
  password?: string;
  role?: string;
  groups?: string[];
  rate_limit_duration?: number;
  rate_limit_duration_type?: string;
  throttle_duration?: number;
  throttle_duration_type?: string;
  throttle_wait_duration?: number;
  throttle_wait_duration_type?: string;
  throttle_queue_limit?: number | null;
  custom_attributes?: Record<string, string>;
  active?: boolean;
  ui_access?: boolean;
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

const UserDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const username = params.username as string;
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editData, setEditData] = useState<UpdateUserData>({});
  const [newCustomAttribute, setNewCustomAttribute] = useState({ key: '', value: '' });
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const userData = sessionStorage.getItem('selectedUser');
    if (userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        setEditData({
          username: parsedUser.username,
          email: parsedUser.email,
          role: parsedUser.role,
          groups: [...parsedUser.groups],
          rate_limit_duration: parsedUser.rate_limit_duration,
          rate_limit_duration_type: parsedUser.rate_limit_duration_type,
          throttle_duration: parsedUser.throttle_duration,
          throttle_duration_type: parsedUser.throttle_duration_type,
          throttle_wait_duration: parsedUser.throttle_wait_duration,
          throttle_wait_duration_type: parsedUser.throttle_wait_duration_type,
          throttle_queue_limit: parsedUser.throttle_queue_limit,
          custom_attributes: { ...parsedUser.custom_attributes },
          active: parsedUser.active,
          ui_access: parsedUser.ui_access
        });
        setLoading(false);
      } catch (err) {
        setError('Failed to load user data');
        setLoading(false);
      }
    } else {
      setError('No user data found');
      setLoading(false);
    }
  }, [username]);

  const handleBack = () => {
    router.back();
  };

  const formatDuration = (duration: number, durationType: string) => {
    const plural = duration !== 1 && (durationType.endsWith('minute') || durationType.endsWith('second') || durationType.endsWith('hour')) ? 's' : '';
    return `${duration} ${durationType}${plural}`;
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    // Reset edit data to original values
    if (user) {
      setEditData({
        username: user.username,
        email: user.email,
        role: user.role,
        groups: [...user.groups],
        rate_limit_duration: user.rate_limit_duration,
        rate_limit_duration_type: user.rate_limit_duration_type,
        throttle_duration: user.throttle_duration,
        throttle_duration_type: user.throttle_duration_type,
        throttle_wait_duration: user.throttle_wait_duration,
        throttle_wait_duration_type: user.throttle_wait_duration_type,
        throttle_queue_limit: user.throttle_queue_limit,
        custom_attributes: { ...user.custom_attributes },
        active: user.active,
        ui_access: user.ui_access
      });
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const response = await fetch(`http://localhost:3002/platform/user/${username}`, {
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
        throw new Error(errorData.error_message || 'Failed to update user');
      }

      // Update the user data in sessionStorage and state
      if (user) {
        const updatedUser: User = {
          ...user,
          ...editData,
          username: editData.username || user.username,
          email: editData.email || user.email,
          role: editData.role || user.role,
          groups: editData.groups || user.groups,
          rate_limit_duration: editData.rate_limit_duration ?? user.rate_limit_duration,
          rate_limit_duration_type: editData.rate_limit_duration_type || user.rate_limit_duration_type,
          throttle_duration: editData.throttle_duration ?? user.throttle_duration,
          throttle_duration_type: editData.throttle_duration_type || user.throttle_duration_type,
          throttle_wait_duration: editData.throttle_wait_duration ?? user.throttle_wait_duration,
          throttle_wait_duration_type: editData.throttle_wait_duration_type || user.throttle_wait_duration_type,
          throttle_queue_limit: editData.throttle_queue_limit ?? user.throttle_queue_limit,
          custom_attributes: editData.custom_attributes || user.custom_attributes,
          active: editData.active ?? user.active,
          ui_access: editData.ui_access ?? user.ui_access
        };
        sessionStorage.setItem('selectedUser', JSON.stringify(updatedUser));
        setUser(updatedUser);
      }
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: keyof UpdateUserData, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const handleGroupChange = (index: number, value: string) => {
    const newGroups = [...(editData.groups || [])];
    newGroups[index] = value;
    setEditData(prev => ({ ...prev, groups: newGroups }));
  };

  const addGroup = () => {
    setEditData(prev => ({ 
      ...prev, 
      groups: [...(prev.groups || []), ''] 
    }));
  };

  const removeGroup = (index: number) => {
    const newGroups = [...(editData.groups || [])];
    newGroups.splice(index, 1);
    setEditData(prev => ({ ...prev, groups: newGroups }));
  };

  const addCustomAttribute = () => {
    if (newCustomAttribute.key && newCustomAttribute.value) {
      setEditData(prev => ({
        ...prev,
        custom_attributes: {
          ...(prev.custom_attributes || {}),
          [newCustomAttribute.key]: newCustomAttribute.value
        }
      }));
      setNewCustomAttribute({ key: '', value: '' });
    }
  };

  const removeCustomAttribute = (key: string) => {
    const newCustomAttributes = { ...(editData.custom_attributes || {}) };
    delete newCustomAttributes[key];
    setEditData(prev => ({ ...prev, custom_attributes: newCustomAttributes }));
  };

  const handleDeleteClick = () => {
    setShowDeleteModal(true);
    setDeleteConfirmation('');
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setDeleteConfirmation('');
  };

  const handleDeleteConfirm = async () => {
    if (deleteConfirmation !== user?.username) {
      setError('Username confirmation does not match');
      return;
    }

    try {
      setDeleting(true);
      setError(null);

      const response = await fetch(`http://localhost:3002/platform/user/${username}`, {
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
        throw new Error(errorData.error_message || 'Failed to delete user');
      }

      // Redirect back to users list after successful deletion
      router.push('/users');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="user-detail-root">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading user details...</p>
        </div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="user-detail-root">
        <div className="error-container">
          <div className="error-message">
            {error || 'User not found'}
          </div>
          <button className="back-button" onClick={handleBack}>
            ← Back to Users
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="user-detail-topbar">
        Doorman
      </div>
      <div className="user-detail-root">
        <aside className="user-detail-sidebar">
          <div className="user-detail-sidebar-title">Menu</div>
          <ul className="user-detail-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`user-detail-sidebar-item${idx === 3 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`user-detail-sidebar-item${idx === 3 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="user-detail-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="user-detail-main">
          <div className="user-detail-header">
            <button className="back-button" onClick={handleBack}>
              <span className="back-arrow">←</span>
              Back to Users
            </button>
            <h1 className="user-detail-title">User Details</h1>
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit User
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
                  Delete User
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

          <div className="user-detail-content">
            <div className="user-detail-card">
              <div className="user-detail-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Username</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="edit-input"
                        value={editData.username || ''}
                        onChange={(e) => handleInputChange('username', e.target.value)}
                      />
                    ) : (
                      <span className="info-value">{user.username}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Email</label>
                    {isEditing ? (
                      <input
                        type="email"
                        className="edit-input"
                        value={editData.email || ''}
                        onChange={(e) => handleInputChange('email', e.target.value)}
                      />
                    ) : (
                      <span className="info-value">{user.email}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Role</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="edit-input"
                        value={editData.role || ''}
                        onChange={(e) => handleInputChange('role', e.target.value)}
                      />
                    ) : (
                      <span className="info-value">{user.role}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Status</label>
                    {isEditing ? (
                      <select
                        className="edit-select"
                        value={editData.active ? 'true' : 'false'}
                        onChange={(e) => handleInputChange('active', e.target.value === 'true')}
                      >
                        <option value="true">Active</option>
                        <option value="false">Inactive</option>
                      </select>
                    ) : (
                      <span className={`status-badge ${user.active ? 'active' : 'inactive'}`}>
                        {user.active ? 'Active' : 'Inactive'}
                      </span>
                    )}
                  </div>
                  {isEditing && (
                    <div className="info-item">
                      <label className="info-label">UI Access</label>
                      <select
                        className="edit-select"
                        value={editData.ui_access ? 'true' : 'false'}
                        onChange={(e) => handleInputChange('ui_access', e.target.value === 'true')}
                      >
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                      </select>
                    </div>
                  )}
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Groups</h2>
                <div className="groups-container">
                  {isEditing ? (
                    <div className="groups-edit">
                      {(editData.groups || []).map((group, index) => (
                        <div key={index} className="group-edit-item">
                          <input
                            type="text"
                            className="edit-input"
                            value={group}
                            onChange={(e) => handleGroupChange(index, e.target.value)}
                            placeholder="Group name"
                          />
                          <button
                            type="button"
                            className="remove-button"
                            onClick={() => removeGroup(index)}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button type="button" className="add-button" onClick={addGroup}>
                        + Add Group
                      </button>
                    </div>
                  ) : (
                    user.groups.length > 0 ? (
                      <div className="groups-list">
                        {user.groups.map((group, index) => (
                          <span key={index} className="group-tag">{group}</span>
                        ))}
                      </div>
                    ) : (
                      <span className="no-groups">No groups assigned</span>
                    )
                  )}
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Rate Limiting</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Rate Limit Duration</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="edit-input"
                        value={editData.rate_limit_duration || ''}
                        onChange={(e) => handleInputChange('rate_limit_duration', parseInt(e.target.value) || 0)}
                        min="0"
                      />
                    ) : (
                      <span className="info-value">{user.rate_limit_duration}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Rate Limit Type</label>
                    {isEditing ? (
                      <select
                        className="edit-select"
                        value={editData.rate_limit_duration_type || ''}
                        onChange={(e) => handleInputChange('rate_limit_duration_type', e.target.value)}
                      >
                        <option value="second">Second</option>
                        <option value="minute">Minute</option>
                        <option value="hour">Hour</option>
                        <option value="day">Day</option>
                      </select>
                    ) : (
                      <span className="info-value">{user.rate_limit_duration_type}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Throttling</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Throttle Duration</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="edit-input"
                        value={editData.throttle_duration || ''}
                        onChange={(e) => handleInputChange('throttle_duration', parseInt(e.target.value) || 0)}
                        min="0"
                      />
                    ) : (
                      <span className="info-value">{user.throttle_duration}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Throttle Type</label>
                    {isEditing ? (
                      <select
                        className="edit-select"
                        value={editData.throttle_duration_type || ''}
                        onChange={(e) => handleInputChange('throttle_duration_type', e.target.value)}
                      >
                        <option value="second">Second</option>
                        <option value="minute">Minute</option>
                        <option value="hour">Hour</option>
                        <option value="day">Day</option>
                      </select>
                    ) : (
                      <span className="info-value">{user.throttle_duration_type}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Wait Duration</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="edit-input"
                        value={editData.throttle_wait_duration || ''}
                        onChange={(e) => handleInputChange('throttle_wait_duration', parseInt(e.target.value) || 0)}
                        min="0"
                      />
                    ) : (
                      <span className="info-value">{user.throttle_wait_duration}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Wait Type</label>
                    {isEditing ? (
                      <select
                        className="edit-select"
                        value={editData.throttle_wait_duration_type || ''}
                        onChange={(e) => handleInputChange('throttle_wait_duration_type', e.target.value)}
                      >
                        <option value="second">Second</option>
                        <option value="minute">Minute</option>
                        <option value="hour">Hour</option>
                        <option value="day">Day</option>
                      </select>
                    ) : (
                      <span className="info-value">{user.throttle_wait_duration_type}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Queue Limit</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="edit-input"
                        value={editData.throttle_queue_limit || ''}
                        onChange={(e) => handleInputChange('throttle_queue_limit', e.target.value ? parseInt(e.target.value) : null)}
                        min="0"
                        placeholder="Unlimited"
                      />
                    ) : (
                      <span className="info-value">{user.throttle_queue_limit || 'Unlimited'}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Custom Attributes</h2>
                {isEditing ? (
                  <div className="custom-attributes-edit">
                    {Object.entries(editData.custom_attributes || {}).map(([key, value]) => (
                      <div key={key} className="custom-attribute-edit-item">
                        <span className="custom-attribute-key">{key}:</span>
                        <input
                          type="text"
                          className="edit-input"
                          value={value}
                          onChange={(e) => {
                            const newCustomAttributes = { ...(editData.custom_attributes || {}) };
                            newCustomAttributes[key] = e.target.value;
                            setEditData(prev => ({ ...prev, custom_attributes: newCustomAttributes }));
                          }}
                        />
                        <button
                          type="button"
                          className="remove-button"
                          onClick={() => removeCustomAttribute(key)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    <div className="add-custom-attribute">
                      <input
                        type="text"
                        className="edit-input"
                        placeholder="Key"
                        value={newCustomAttribute.key}
                        onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, key: e.target.value }))}
                      />
                      <input
                        type="text"
                        className="edit-input"
                        placeholder="Value"
                        value={newCustomAttribute.value}
                        onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, value: e.target.value }))}
                      />
                      <button type="button" className="add-button" onClick={addCustomAttribute}>
                        Add
                      </button>
                    </div>
                  </div>
                ) : (
                  Object.keys(user.custom_attributes).length > 0 ? (
                    <div className="custom-attributes">
                      {Object.entries(user.custom_attributes).map(([key, value]) => (
                        <div key={key} className="info-item">
                          <label className="info-label">{key}</label>
                          <span className="info-value">{value}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="no-groups">No custom attributes</span>
                  )
                )}
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title">Delete User</h2>
              <button className="modal-close" onClick={handleDeleteCancel}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-message">
                This action cannot be undone. This will permanently delete the user account for <strong>{user?.username}</strong>.
              </p>
              <p className="modal-warning">
                To confirm deletion, please type the username <strong>{user?.username}</strong> in the field below:
              </p>
              <input
                type="text"
                className="modal-input"
                placeholder="Enter username to confirm"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                autoFocus
              />
            </div>
            <div className="modal-footer">
              <button 
                className="modal-cancel-button" 
                onClick={handleDeleteCancel}
                disabled={deleting}
              >
                Cancel
              </button>
              <button 
                className="modal-delete-button" 
                onClick={handleDeleteConfirm}
                disabled={deleting || deleteConfirmation !== user?.username}
              >
                {deleting ? 'Deleting...' : 'Delete User'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default UserDetailPage; 