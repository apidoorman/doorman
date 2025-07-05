'use client'

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import '../routings.css';
import './add-routing.css';

interface CreateRoutingData {
  routing_name: string;
  routing_servers: string[];
  routing_description: string;
  client_key?: string;
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

const AddRoutingPage = () => {
  const router = useRouter();
  const [formData, setFormData] = useState<CreateRoutingData>({
    routing_name: '',
    routing_servers: [],
    routing_description: '',
    server_index: 0
  });
  const [newServer, setNewServer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (field: keyof CreateRoutingData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const addServer = () => {
    if (newServer.trim()) {
      setFormData(prev => ({ ...prev, routing_servers: [...prev.routing_servers, newServer.trim()] }));
      setNewServer('');
    }
  };

  const removeServer = (index: number) => {
    setFormData(prev => ({ ...prev, routing_servers: prev.routing_servers.filter((_, i) => i !== index) }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.routing_name || formData.routing_servers.length === 0) {
      setError('Please fill in routing name and add at least one server');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:3002/platform/routing/', {
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
        throw new Error(errorData.error_message || 'Failed to create routing');
      }

      // Redirect to routings list after successful creation
      router.push('/routings');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create routing');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    router.back();
  };

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
          <div className="routings-header-row">
            <div className="add-routing-header">
              <button className="back-button" onClick={handleBack}>
                <span className="back-arrow">←</span>
                Back to Routings
              </button>
              <h1 className="routings-title">Add New Routing</h1>
            </div>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="add-routing-content">
            <form className="add-routing-form" onSubmit={handleSubmit}>
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Routing Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter routing name"
                      value={formData.routing_name}
                      onChange={(e) => handleInputChange('routing_name', e.target.value)}
                      maxLength={50}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Client Key (Optional)</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Enter client key"
                      value={formData.client_key || ''}
                      onChange={(e) => handleInputChange('client_key', e.target.value)}
                      maxLength={50}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-input"
                    placeholder="Enter routing description"
                    value={formData.routing_description}
                    onChange={(e) => handleInputChange('routing_description', e.target.value)}
                    maxLength={255}
                    rows={3}
                  />
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Server Configuration</h2>
                <div className="servers-container">
                  <div className="servers-list">
                    {formData.routing_servers.map((server, index) => (
                      <div key={index} className="server-tag">
                        <span>{server}</span>
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
                      placeholder="Enter server URL (e.g., http://localhost:8080)"
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
                <div className="form-group">
                  <label className="form-label">Default Server Index</label>
                  <input
                    type="number"
                    className="form-input"
                    placeholder="0"
                    value={formData.server_index || 0}
                    onChange={(e) => handleInputChange('server_index', parseInt(e.target.value) || 0)}
                    min={0}
                  />
                </div>
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  className="cancel-button"
                  onClick={handleBack}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Creating...' : 'Create Routing'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </>
  );
};

export default AddRoutingPage; 