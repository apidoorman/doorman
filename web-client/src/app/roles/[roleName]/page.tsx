'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import '../roles.css';

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
  view_logs?: boolean;
  export_logs?: boolean;
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

const RoleDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const roleName = params.roleName as string;
  
  const [theme, setTheme] = useState('light');
  const [role, setRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Partial<Role>>({});
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
    fetchRole();
  }, [roleName]);

  const fetchRole = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try to get from sessionStorage first
      const savedRole = sessionStorage.getItem('selectedRole');
      if (savedRole) {
        const parsedRole = JSON.parse(savedRole);
        if (parsedRole.role_name === roleName) {
          setRole(parsedRole);
          setEditData(parsedRole);
          setLoading(false);
          return;
        }
      }

      // Fetch from API if not in sessionStorage
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to load role');
      }
      
      const data = await response.json();
      setRole(data);
      setEditData(data);
    } catch (err) {
      setError('Failed to load role. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditData(role || {});
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
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
        throw new Error(errorData.error_message || 'Failed to update role');
      }
      
      setRole({ ...role, ...editData } as Role);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role. Please try again later.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      setError(null);
      
      const response = await fetch(`http://localhost:3002/platform/role/${encodeURIComponent(roleName)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete role');
      }
      
      router.push('/roles');
    } catch (err) {
      setError('Failed to delete role. Please try again later.');
      setShowDeleteModal(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleInputChange = (field: keyof Role, value: any) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const handlePermissionChange = (permission: keyof Role, value: boolean) => {
    setEditData(prev => ({ ...prev, [permission]: value }));
  };

  const getPermissionCount = (roleData: Role) => {
    return Object.values(roleData).filter(val => typeof val === 'boolean' && val).length;
  };

  if (loading) {
    return (
      <>
        <div className="roles-topbar">Doorman</div>
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
            <button className="roles-logout-btn" onClick={handleLogout}>Logout</button>
          </aside>
          <main className="roles-main">
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading role...</p>
            </div>
          </main>
        </div>
      </>
    );
  }

  if (!role) {
    return (
      <>
        <div className="roles-topbar">Doorman</div>
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
            <button className="roles-logout-btn" onClick={handleLogout}>Logout</button>
          </aside>
          <main className="roles-main">
            <div className="error-container">
              <div className="error-message">Role not found</div>
              <Link href="/roles" className="back-link">Back to Roles</Link>
            </div>
          </main>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="roles-topbar">Doorman</div>
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
          <button className="roles-logout-btn" onClick={handleLogout}>Logout</button>
        </aside>
        <main className="roles-main">
          <div className="roles-header">
            <button className="back-button" onClick={() => router.push('/roles')}>
              <span className="back-arrow">←</span>
              Back to Roles
            </button>
            <h1 className="roles-title">Role Details</h1>
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit Role
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
                  Delete Role
                </button>
              </div>
            )}
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">{error}</div>
            </div>
          )}

          <div className="roles-detail-content">
            <div className="roles-detail-card">
              <div className="roles-detail-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Role Name</label>
                    {isEditing ? (
                      <input
                        type="text"
                        className="edit-input"
                        value={editData.role_name || ''}
                        onChange={(e) => handleInputChange('role_name', e.target.value)}
                        disabled={saving}
                      />
                    ) : (
                      <span className="info-value">{role.role_name}</span>
                    )}
                  </div>
                  <div className="info-item">
                    <label className="info-label">Description</label>
                    {isEditing ? (
                      <textarea
                        className="edit-input"
                        value={editData.role_description || ''}
                        onChange={(e) => handleInputChange('role_description', e.target.value)}
                        disabled={saving}
                        rows={3}
                      />
                    ) : (
                      <span className="info-value">{role.role_description || 'No description'}</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="roles-detail-section">
                <h2 className="section-title">Permissions</h2>
                
                <div className="permissions-grid">
                  {[
                    { key: 'manage_users', label: 'Manage Users' },
                    { key: 'manage_apis', label: 'Manage APIs' },
                    { key: 'manage_endpoints', label: 'Manage Endpoints' },
                    { key: 'manage_groups', label: 'Manage Groups' },
                    { key: 'manage_roles', label: 'Manage Roles' },
                    { key: 'manage_routings', label: 'Manage Routings' },
                    { key: 'manage_gateway', label: 'Manage Gateway' },
                    { key: 'manage_subscriptions', label: 'Manage Subscriptions' },
                    { key: 'view_logs', label: 'View Logs' },
                    { key: 'export_logs', label: 'Export Logs' }
                  ].map(({ key, label }) => (
                    <div key={key} className="permission-item">
                      {isEditing ? (
                        <label className="permission-label">
                          <input
                            type="checkbox"
                            checked={editData[key as keyof Role] as boolean || false}
                            onChange={(e) => handlePermissionChange(key as keyof Role, e.target.checked)}
                            disabled={saving}
                          />
                          <span className="permission-text">{label}</span>
                        </label>
                      ) : (
                        <div className="permission-display">
                          <span className={`permission-badge ${(role[key as keyof Role] as boolean) ? 'enabled' : 'disabled'}`}>
                            {(role[key as keyof Role] as boolean) ? '✓' : '✗'} {label}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                
                {!isEditing && (
                  <div className="permissions-summary">
                    <span className="permission-badge">
                      {getPermissionCount(role)} permission{getPermissionCount(role) !== 1 ? 's' : ''} enabled
                    </span>
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
              <h2 className="modal-title">Delete Role</h2>
              <button className="modal-close" onClick={() => setShowDeleteModal(false)}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-message">
                This action cannot be undone. This will permanently delete the role <strong>{role?.role_name}</strong>.
              </p>
              <p className="modal-warning">
                To confirm deletion, please type the role name <strong>{role?.role_name}</strong> in the field below:
              </p>
              <input
                type="text"
                className="modal-input"
                placeholder="Enter role name to confirm"
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
                disabled={deleting || deleteConfirmation !== role?.role_name}
              >
                {deleting ? 'Deleting...' : 'Delete Role'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default RoleDetailPage; 