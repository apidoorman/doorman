'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './settings.css';

interface UserSettings {
  username: string;
  email: string;
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
  originalUsername: string;
  originalEmail: string;
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

const SettingsPage = () => {
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [settings, setSettings] = useState<UserSettings>({
    username: '',
    email: '',
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    originalUsername: '',
    originalEmail: '',
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
    fetchUserSettings();
  }, []);

  const fetchUserSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('http://localhost:3002/platform/user/me', {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to load user settings');
      }
      const data = await response.json();
      setSettings(prev => ({
        ...prev,
        username: data.username,
        email: data.email,
        originalUsername: data.username,
        originalEmail: data.email,
      }));
    } catch (err) {
      setError('Failed to load user settings. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      setLoading(true);

      // Update user info if username or email changed
      if (settings.username !== settings.originalUsername || settings.email !== settings.originalEmail) {
        const userInfoResponse = await fetch(`http://localhost:3002/platform/user/${settings.originalUsername}`, {
          method: 'PUT',
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
          },
          body: JSON.stringify({
            username: settings.username,
            email: settings.email
          })
        });

        if (!userInfoResponse.ok) {
          const errorData = await userInfoResponse.json();
          throw new Error(errorData.error_message || 'Failed to update user info');
        }

        // Update original values after successful update
        setSettings(prev => ({
          ...prev,
          originalUsername: settings.username,
          originalEmail: settings.email
        }));
      }

      // Update password if new password is provided
      if (settings.newPassword) {
        if (settings.newPassword !== settings.confirmPassword) {
          setError('New passwords do not match');
          return;
        }

        const passwordResponse = await fetch(`http://localhost:3002/platform/user/${settings.username}/update-password`, {
          method: 'PUT',
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cookie': `access_token_cookie=${document.cookie.split('; ').find(row => row.startsWith('access_token_cookie='))?.split('=')[1]}`
          },
          body: JSON.stringify({
            old_password: settings.currentPassword,
            new_password: settings.newPassword
          })
        });

        if (!passwordResponse.ok) {
          const errorData = await passwordResponse.json();
          throw new Error(errorData.error_message || 'Failed to update password');
        }
      }

      setSuccess('Settings updated successfully');
      setSettings(prev => ({
        ...prev,
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update settings. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="settings-topbar">
        Doorman
      </div>
      <div className="settings-root">
        <aside className="settings-sidebar">
          <div className="settings-sidebar-title">Menu</div>
          <ul className="settings-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`settings-sidebar-item${idx === 9 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`settings-sidebar-item${idx === 9 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="settings-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="settings-main">
          <div className="settings-header-row">
            <h1 className="settings-title">Settings</h1>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                {error}
              </div>
            </div>
          )}

          {success && (
            <div className="success-container">
              <div className="success-message">
                {success}
              </div>
            </div>
          )}

          {loading ? (
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading settings...</p>
            </div>
          ) : (
            <div className="settings-panel">
              <form onSubmit={handleSubmit} className="settings-form">
                <div className="settings-section">
                  <h2>Account Information</h2>
                  <div className="form-group">
                    <label htmlFor="username">Username</label>
                    <input
                      type="text"
                      id="username"
                      name="username"
                      value={settings.username}
                      onChange={handleInputChange}
                      className="settings-input"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="email">Email</label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={settings.email}
                      onChange={handleInputChange}
                      className="settings-input"
                    />
                  </div>
                </div>

                <div className="settings-section">
                  <h2>Change Password</h2>
                  <div className="form-group">
                    <label htmlFor="currentPassword">Current Password</label>
                    <input
                      type="password"
                      id="currentPassword"
                      name="currentPassword"
                      value={settings.currentPassword}
                      onChange={handleInputChange}
                      className="settings-input"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="newPassword">New Password</label>
                    <input
                      type="password"
                      id="newPassword"
                      name="newPassword"
                      value={settings.newPassword}
                      onChange={handleInputChange}
                      className="settings-input"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="confirmPassword">Confirm New Password</label>
                    <input
                      type="password"
                      id="confirmPassword"
                      name="confirmPassword"
                      value={settings.confirmPassword}
                      onChange={handleInputChange}
                      className="settings-input"
                    />
                  </div>
                </div>

                <div className="settings-actions">
                  <button type="submit" className="settings-save-btn">
                    Save Changes
                  </button>
                </div>
                <br />
                <div className="update-warning">Warning: Any settings changes will log you out.</div>
              </form>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default SettingsPage; 