'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import '../groups.css';

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

const GroupDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const groupName = params.groupName as string;
  
  const [theme, setTheme] = useState('light');
  const [group, setGroup] = useState<Group | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Group>>({});
  const [saving, setSaving] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchGroup();
  }, [groupName]);

  const fetchGroup = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try to get from sessionStorage first
      const savedGroup = sessionStorage.getItem('selectedGroup');
      if (savedGroup) {
        const parsedGroup = JSON.parse(savedGroup);
        if (parsedGroup.group_name === groupName) {
          setGroup(parsedGroup);
          setEditData(parsedGroup);
          setLoading(false);
          return;
        }
      }

      // Fetch from API if not in sessionStorage
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to load group');
      }
      
      const data = await response.json();
      setGroup(data);
      setEditData(data);
    } catch (err) {
      setError('Failed to load group. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditData(group || {});
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
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
        throw new Error(errorData.error_message || 'Failed to update group');
      }
      
      setGroup({ ...group, ...editData } as Group);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update group. Please try again later.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      setError(null);
      
      const response = await fetch(`http://localhost:3002/platform/group/${encodeURIComponent(groupName)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete group');
      }
      
      router.push('/groups');
    } catch (err) {
      setError('Failed to delete group. Please try again later.');
      setShowDeleteModal(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleInputChange = (field: keyof Group, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const handleApiAccessChange = (index: number, value: string) => {
    const newApiAccess = [...(editData.api_access || [])];
    newApiAccess[index] = value;
    setEditData(prev => ({ ...prev, api_access: newApiAccess }));
  };

  const addApiAccess = () => {
    setEditData(prev => ({ 
      ...prev, 
      api_access: [...(prev.api_access || []), ''] 
    }));
  };

  const removeApiAccess = (index: number) => {
    const newApiAccess = [...(editData.api_access || [])];
    newApiAccess.splice(index, 1);
    setEditData(prev => ({ ...prev, api_access: newApiAccess }));
  };

  if (loading) {
    return (
      <>
        <div className="groups-topbar">Doorman</div>
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
            <button className="groups-logout-btn" onClick={handleLogout}>Logout</button>
          </aside>
          <main className="groups-main">
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading group...</p>
            </div>
          </main>
        </div>
      </>
    );
  }

  if (!group) {
    return (
      <>
        <div className="groups-topbar">Doorman</div>
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
            <button className="groups-logout-btn" onClick={handleLogout}>Logout</button>
          </aside>
          <main className="groups-main">
            <div className="error-container">
              <div className="error-message">Group not found</div>
              <Link href="/groups" className="back-link">Back to Groups</Link>
            </div>
          </main>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="groups-topbar">Doorman</div>
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
          <button className="groups-logout-btn" onClick={handleLogout}>Logout</button>
        </aside>
        <main className="groups-main">
          <div className="groups-header">
            <button className="back-button" onClick={() => router.push('/groups')}>
              <span className="back-arrow">←</span>
              Back to Groups
            </button>
            <h1 className="groups-title">Group Details</h1>
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit Group
              </button>
            ) : (
              <div className="edit-actions">
                <button className="save-button" onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button className="cancel-button" onClick={handleCancel} disabled={saving}>
                  Cancel
                </button>
                <button className="delete-button" onClick={() => setShowDeleteModal(true)} disabled={saving}>
                  Delete Group
                </button>
              </div>
            )}
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">{error}</div>
            </div>
          )}

          <div className="groups-detail-content">
            <div className="groups-detail-card">
              <div className="groups-detail-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Group Name</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="edit-input"
                        value={editData.group_name || ''}
                        onChange={(e) => handleInputChange('group_name', e.target.value)}
                        disabled={saving}
                      />
                    ) : (
                      <span className="info-value">{group.group_name}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Description</label>
                    {isEditing ? (
                      <textarea
                        className="edit-input"
                        value={editData.group_description || ''}
                        onChange={(e) => handleInputChange('group_description', e.target.value)}
                        disabled={saving}
                        rows={3}
                      />
                    ) : (
                      <span className="info-value">{group.group_description || 'No description'}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="groups-detail-section">
                <h2 className="section-title">API Access</h2>
                
                {isEditing ? (
                  <div className="groups-edit">
                    {(editData.api_access || []).map((api, index) => (
                      <div key={index} className="group-edit-item">
                        <input
                          type="text"
                          className="edit-input"
                          value={api}
                          onChange={(e) => handleApiAccessChange(index, e.target.value)}
                          placeholder="Enter API name/version (e.g., customer/v1)"
                          disabled={saving}
                        />
                        <button
                          type="button"
                          className="remove-button"
                          onClick={() => removeApiAccess(index)}
                          disabled={saving}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      className="add-button"
                      onClick={addApiAccess}
                      disabled={saving}
                    >
                      + Add API Access
                    </button>
                  </div>
                ) : (
                  <div className="groups-container">
                    {group.api_access && group.api_access.length > 0 ? (
                      <div className="groups-list">
                        {group.api_access.map((api, index) => (
                          <span key={index} className="group-tag">
                            {api}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="no-groups">No API access configured</span>
                    )}
                  </div>
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
              <h2 className="modal-title">Delete Group</h2>
              <button className="modal-close" onClick={() => setShowDeleteModal(false)}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-message">
                This action cannot be undone. This will permanently delete the group <strong>{group?.group_name}</strong>.
              </p>
              <p className="modal-warning">
                To confirm deletion, please type the group name <strong>{group?.group_name}</strong> in the field below:
              </p>
              <input
                type="text"
                className="modal-input"
                placeholder="Enter group name to confirm"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                autoFocus
              />
            </div>
            <div className="modal-footer">
              <button 
                className="modal-cancel-button" 
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button 
                className="modal-delete-button" 
                onClick={handleDelete}
                disabled={deleting || deleteConfirmation !== group?.group_name}
              >
                {deleting ? 'Deleting...' : 'Delete Group'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default GroupDetailPage; 