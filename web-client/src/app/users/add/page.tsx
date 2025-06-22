'use client'

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import '../users.css';
import './add-user.css';

interface CreateUserData {
  username: string;
  email: string;
  password: string;
  role: string;
  groups: string[];
  rate_limit_duration?: number;
  rate_limit_duration_type?: string;
  throttle_duration?: number;
  throttle_duration_type?: string;
  throttle_wait_duration?: number;
  throttle_wait_duration_type?: string;
  throttle_queue_limit?: number | null;
  custom_attributes: Record<string, string>;
  active: boolean;
  ui_access: boolean;
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

const AddUserPage = () => {
  const router = useRouter();
  const [formData, setFormData] = useState<CreateUserData>({
    username: '',
    email: '',
    password: '',
    role: '',
    groups: [],
    custom_attributes: {},
    active: true,
    ui_access: false
  });
  const [newGroup, setNewGroup] = useState('');
  const [newCustomAttribute, setNewCustomAttribute] = useState({ key: '', value: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState({ score: 0, message: '' });

  const handleInputChange = (field: keyof CreateUserData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Check password strength when password changes
    if (field === 'password') {
      checkPasswordStrength(value);
    }
  };

  const checkPasswordStrength = (password: string) => {
    let score = 0;
    let message = '';

    if (password.length >= 16) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[a-z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score++;

    if (score < 3) message = 'Weak - Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character';
    else if (score < 5) message = 'Medium - Add more complexity';
    else message = 'Strong - Password meets security requirements';

    setPasswordStrength({ score, message });
  };

  const addGroup = () => {
    if (newGroup.trim()) {
      setFormData(prev => ({ ...prev, groups: [...prev.groups, newGroup.trim()] }));
      setNewGroup('');
    }
  };

  const removeGroup = (index: number) => {
    setFormData(prev => ({ ...prev, groups: prev.groups.filter((_, i) => i !== index) }));
  };

  const addCustomAttribute = () => {
    if (newCustomAttribute.key && newCustomAttribute.value) {
      setFormData(prev => ({
        ...prev,
        custom_attributes: {
          ...prev.custom_attributes,
          [newCustomAttribute.key]: newCustomAttribute.value
        }
      }));
      setNewCustomAttribute({ key: '', value: '' });
    }
  };

  const removeCustomAttribute = (key: string) => {
    const newCustomAttributes = { ...formData.custom_attributes };
    delete newCustomAttributes[key];
    setFormData(prev => ({ ...prev, custom_attributes: newCustomAttributes }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.username || !formData.email || !formData.password || !formData.role) {
      setError('Please fill in all required fields');
      return;
    }

    if (passwordStrength.score < 5) {
      setError('Password does not meet security requirements');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:3002/platform/user/', {
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
        throw new Error(errorData.error_message || 'Failed to create user');
      }

      // Redirect to users list after successful creation
      router.push('/users');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    router.back();
  };

  return (
    <>
      <div className="users-topbar">
        Doorman
      </div>
      <div className="users-root">
        <aside className="users-sidebar">
          <div className="users-sidebar-title">Menu</div>
          <ul className="users-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`users-sidebar-item${idx === 3 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`users-sidebar-item${idx === 3 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="users-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="users-main">
          <div className="users-header-row">
            <div className="add-user-header">
              <button className="back-button" onClick={handleBack}>
                <span className="back-arrow">←</span>
                Back to Users
              </button>
              <h1 className="users-title">Add New User</h1>
            </div>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          <div className="add-user-content">
            <form onSubmit={handleSubmit} className="add-user-form">
              <div className="form-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Username *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.username}
                      onChange={(e) => handleInputChange('username', e.target.value)}
                      placeholder="Enter username"
                      minLength={3}
                      maxLength={50}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email *</label>
                    <input
                      type="email"
                      className="form-input"
                      value={formData.email}
                      onChange={(e) => handleInputChange('email', e.target.value)}
                      placeholder="Enter email"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Password *</label>
                    <input
                      type="password"
                      className="form-input"
                      value={formData.password}
                      onChange={(e) => handleInputChange('password', e.target.value)}
                      placeholder="Enter password (min 16 chars)"
                      minLength={16}
                      maxLength={50}
                      required
                    />
                    {formData.password && (
                      <div className={`password-strength ${passwordStrength.score < 5 ? 'weak' : 'strong'}`}>
                        {passwordStrength.message}
                      </div>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Role *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.role}
                      onChange={(e) => handleInputChange('role', e.target.value)}
                      placeholder="Enter role"
                      minLength={2}
                      maxLength={50}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-select"
                      value={formData.active ? 'true' : 'false'}
                      onChange={(e) => handleInputChange('active', e.target.value === 'true')}
                    >
                      <option value="true">Active</option>
                      <option value="false">Inactive</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">UI Access</label>
                    <select
                      className="form-select"
                      value={formData.ui_access ? 'true' : 'false'}
                      onChange={(e) => handleInputChange('ui_access', e.target.value === 'true')}
                    >
                      <option value="false">Disabled</option>
                      <option value="true">Enabled</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Groups</h2>
                <div className="groups-container">
                  <div className="groups-list">
                    {formData.groups.map((group, index) => (
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
                <h2 className="section-title">Rate Limiting</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Rate Limit Duration</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.rate_limit_duration || ''}
                      onChange={(e) => handleInputChange('rate_limit_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                      min="0"
                      placeholder="100"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Rate Limit Type</label>
                    <select
                      className="form-select"
                      value={formData.rate_limit_duration_type || ''}
                      onChange={(e) => handleInputChange('rate_limit_duration_type', e.target.value)}
                    >
                      <option value="">Select type</option>
                      <option value="second">Second</option>
                      <option value="minute">Minute</option>
                      <option value="hour">Hour</option>
                      <option value="day">Day</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Throttling</h2>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Throttle Duration</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.throttle_duration || ''}
                      onChange={(e) => handleInputChange('throttle_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                      min="0"
                      placeholder="10"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Throttle Type</label>
                    <select
                      className="form-select"
                      value={formData.throttle_duration_type || ''}
                      onChange={(e) => handleInputChange('throttle_duration_type', e.target.value)}
                    >
                      <option value="">Select type</option>
                      <option value="second">Second</option>
                      <option value="minute">Minute</option>
                      <option value="hour">Hour</option>
                      <option value="day">Day</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Wait Duration</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.throttle_wait_duration || ''}
                      onChange={(e) => handleInputChange('throttle_wait_duration', e.target.value ? parseInt(e.target.value) : undefined)}
                      min="0"
                      placeholder="5"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Wait Type</label>
                    <select
                      className="form-select"
                      value={formData.throttle_wait_duration_type || ''}
                      onChange={(e) => handleInputChange('throttle_wait_duration_type', e.target.value)}
                    >
                      <option value="">Select type</option>
                      <option value="second">Second</option>
                      <option value="minute">Minute</option>
                      <option value="hour">Hour</option>
                      <option value="day">Day</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Queue Limit</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.throttle_queue_limit || ''}
                      onChange={(e) => handleInputChange('throttle_queue_limit', e.target.value ? parseInt(e.target.value) : null)}
                      min="0"
                      placeholder="10"
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h2 className="section-title">Custom Attributes</h2>
                <div className="custom-attributes-container">
                  {Object.entries(formData.custom_attributes).map(([key, value]) => (
                    <div key={key} className="custom-attribute-item">
                      <span className="custom-attribute-key">{key}:</span>
                      <span className="custom-attribute-value">{value}</span>
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
                      className="form-input"
                      placeholder="Key"
                      value={newCustomAttribute.key}
                      onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, key: e.target.value }))}
                    />
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Value"
                      value={newCustomAttribute.value}
                      onChange={(e) => setNewCustomAttribute(prev => ({ ...prev, value: e.target.value }))}
                    />
                    <button type="button" className="add-button" onClick={addCustomAttribute}>
                      Add
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-actions">
                <button type="button" className="cancel-button" onClick={handleBack}>
                  Cancel
                </button>
                <button type="submit" className="save-button" disabled={loading}>
                  {loading ? 'Creating User...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </>
  );
};

export default AddUserPage; 