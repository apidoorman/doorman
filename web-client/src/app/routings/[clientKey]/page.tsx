'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';
import './routing-detail.css';

interface Routing {
  routing_name: string;
  routing_servers: string[];
  routing_description: string;
  client_key: string;
  server_index?: number;
}

interface UpdateRoutingData {
  routing_name?: string;
  routing_servers?: string[];
  routing_description?: string;
  server_index?: number;
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
  { label: 'Security' },
  { label: 'Settings', href: '/settings' },
];

const handleLogout = () => {
  localStorage.clear();
  sessionStorage.clear();
  setTimeout(() => {
    window.location.replace('/');
  }, 50);
};

const RoutingDetailPage = () => {
  const router = useRouter();
  const params = useParams();
  const clientKey = params.clientKey as string;
  const [routing, setRouting] = useState<Routing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editData, setEditData] = useState<UpdateRoutingData>({});
  const [newServer, setNewServer] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const routingData = sessionStorage.getItem('selectedRouting');
    if (routingData) {
      try {
        const parsedRouting = JSON.parse(routingData);
        setRouting(parsedRouting);
        setEditData({
          routing_name: parsedRouting.routing_name,
          routing_servers: [...parsedRouting.routing_servers],
          routing_description: parsedRouting.routing_description,
          server_index: parsedRouting.server_index || 0
        });
        setLoading(false);
      } catch (err) {
        setError('Failed to load routing data');
        setLoading(false);
      }
    } else {
      setError('No routing data found');
      setLoading(false);
    }
  }, [clientKey]);

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
    if (routing) {
      setEditData({
        routing_name: routing.routing_name,
        routing_servers: [...routing.routing_servers],
        routing_description: routing.routing_description,
        server_index: routing.server_index || 0
      });
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const response = await fetch(`http://localhost:3002/platform/routing/${clientKey}`, {
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
        throw new Error(errorData.error_message || 'Failed to update routing');
      }

      // Update the routing data in sessionStorage and state
      if (routing) {
        const updatedRouting: Routing = {
          ...routing,
          ...editData,
          routing_name: editData.routing_name || routing.routing_name,
          routing_servers: editData.routing_servers || routing.routing_servers,
          routing_description: editData.routing_description || routing.routing_description,
          server_index: editData.server_index ?? routing.server_index
        };
        sessionStorage.setItem('selectedRouting', JSON.stringify(updatedRouting));
        setRouting(updatedRouting);
      }
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update routing');
    } finally {
      setSaving(false);
    }
  };

  const handleServerChange = (index: number, value: string) => {
    const newServers = [...(editData.routing_servers || [])];
    newServers[index] = value;
    setEditData(prev => ({ ...prev, routing_servers: newServers }));
  };

  const addServer = () => {
    if (newServer.trim()) {
      setEditData(prev => ({
        ...prev,
        routing_servers: [...(prev.routing_servers || []), newServer.trim()]
      }));
      setNewServer('');
    }
  };

  const removeServer = (index: number) => {
    setEditData(prev => ({
      ...prev,
      routing_servers: (prev.routing_servers || []).filter((_, i) => i !== index)
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
    if (deleteConfirmation !== routing?.routing_name) {
      setError('Confirmation does not match routing name');
      return;
    }

    try {
      setDeleting(true);
      setError(null);

      const response = await fetch(`http://localhost:3002/platform/routing/${clientKey}`, {
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
        throw new Error(errorData.error_message || 'Failed to delete routing');
      }

      // Redirect to routings list after successful deletion
      router.push('/routings');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete routing');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner"></div>
        <p>Loading routing...</p>
      </div>
    );
  }

  if (error && !routing) {
    return (
      <div className="error-container">
        <div className="error-message">
          {error}
        </div>
        <button className="back-button" onClick={handleBack}>
          <span className="back-arrow">←</span>
          Back to Routings
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="routings-topbar">
        Doorman
      </div>
      <div className="routings-root">
        <aside className="routings-sidebar">
          <div className="routings-sidebar-title">Menu</div>
          <ul className="routings-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`routings-sidebar-item${idx === 2 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`routings-sidebar-item${idx === 2 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="routings-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="routings-main">
          <div className="routing-detail-header">
            <button className="back-button" onClick={handleBack}>
              <span className="back-arrow">←</span>
              Back to Routings
            </button>
            <h1 className="routing-detail-title">Routing Details</h1>
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit Routing
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
                  Delete Routing
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

          {routing && (
            <div className="routing-detail-content">
              <div className="routing-detail-form">
                <div className="form-section">
                  <h2 className="section-title">Basic Information</h2>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Routing Name</label>
                      {isEditing ? (
                        <input
                          type="text"
                          className="form-input"
                          value={editData.routing_name || ''}
                          onChange={(e) => setEditData(prev => ({ ...prev, routing_name: e.target.value }))}
                          maxLength={50}
                        />
                      ) : (
                        <div className="form-value">{routing.routing_name}</div>
                      )}
                    </div>
                    <div className="form-group">
                      <label className="form-label">Client Key</label>
                      <div className="form-value">{routing.client_key}</div>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    {isEditing ? (
                      <textarea
                        className="form-input"
                        value={editData.routing_description || ''}
                        onChange={(e) => setEditData(prev => ({ ...prev, routing_description: e.target.value }))}
                        maxLength={255}
                        rows={3}
                      />
                    ) : (
                      <div className="form-value">{routing.routing_description || 'No description'}</div>
                    )}
                  </div>
                </div>

                <div className="form-section">
                  <h2 className="section-title">Server Configuration</h2>
                  <div className="form-group">
                    <label className="form-label">Servers</label>
                    {isEditing ? (
                      <div className="servers-container">
                        <div className="servers-list">
                          {(editData.routing_servers || []).map((server, index) => (
                            <div key={index} className="server-input-group">
                              <input
                                type="text"
                                className="form-input"
                                value={server}
                                onChange={(e) => handleServerChange(index, e.target.value)}
                                placeholder="Server URL"
                              />
                              <button
                                type="button"
                                className="remove-server-btn"
                                onClick={() => removeServer(index)}
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                        <div className="add-server">
                          <input
                            type="text"
                            className="form-input"
                            placeholder="Enter server URL"
                            value={newServer}
                            onChange={(e) => setNewServer(e.target.value)}
                          />
                          <button
                            type="button"
                            className="add-button"
                            onClick={addServer}
                          >
                            Add Server
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="servers-list">
                        {routing.routing_servers.map((server, index) => (
                          <div key={index} className="server-tag">
                            <span>{server}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Default Server Index</label>
                    {isEditing ? (
                      <input
                        type="number"
                        className="form-input"
                        value={editData.server_index || 0}
                        onChange={(e) => setEditData(prev => ({ ...prev, server_index: parseInt(e.target.value) || 0 }))}
                        min={0}
                      />
                    ) : (
                      <div className="form-value">{routing.server_index || 0}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Delete Confirmation Modal */}
          {showDeleteModal && (
            <div className="modal-overlay">
              <div className="modal-content">
                <h3>Delete Routing</h3>
                <p>Are you sure you want to delete this routing? This action cannot be undone.</p>
                <p>To confirm, please type the routing name: <strong>{routing?.routing_name}</strong></p>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Enter routing name to confirm"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                />
                <div className="modal-actions">
                  <button
                    type="button"
                    className="cancel-button"
                    onClick={handleDeleteCancel}
                    disabled={deleting}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="delete-button"
                    onClick={handleDeleteConfirm}
                    disabled={deleting || deleteConfirmation !== routing?.routing_name}
                  >
                    {deleting ? 'Deleting...' : 'Delete Routing'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default RoutingDetailPage; 