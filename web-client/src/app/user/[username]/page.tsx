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

  useEffect(() => {
    const userData = sessionStorage.getItem('selectedUser');
    if (userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
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
          </div>

          <div className="user-detail-content">
            <div className="user-detail-card">
              <div className="user-detail-section">
                <h2 className="section-title">Basic Information</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Username</label>
                    <span className="info-value">{user.username}</span>
                  </div>
                  <div className="info-item">
                    <label className="info-label">Email</label>
                    <span className="info-value">{user.email}</span>
                  </div>
                  <div className="info-item">
                    <label className="info-label">Role</label>
                    <span className="info-value">{user.role}</span>
                  </div>
                  <div className="info-item">
                    <label className="info-label">Status</label>
                    <span className={`status-badge ${user.active ? 'active' : 'inactive'}`}>
                      {user.active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Groups</h2>
                <div className="groups-container">
                  {user.groups.length > 0 ? (
                    <div className="groups-list">
                      {user.groups.map((group, index) => (
                        <span key={index} className="group-tag">{group}</span>
                      ))}
                    </div>
                  ) : (
                    <span className="no-groups">No groups assigned</span>
                  )}
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Rate Limiting</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Rate Limit</label>
                    <span className="info-value">{formatDuration(user.rate_limit_duration, user.rate_limit_duration_type)}</span>
                  </div>
                </div>
              </div>

              <div className="user-detail-section">
                <h2 className="section-title">Throttling</h2>
                <div className="info-grid">
                  <div className="info-item">
                    <label className="info-label">Throttle Duration</label>
                    <span className="info-value">{formatDuration(user.throttle_duration, user.throttle_duration_type)}</span>
                  </div>
                  <div className="info-item">
                    <label className="info-label">Wait Duration</label>
                    <span className="info-value">{formatDuration(user.throttle_wait_duration, user.throttle_wait_duration_type)}</span>
                  </div>
                  <div className="info-item">
                    <label className="info-label">Queue Limit</label>
                    <span className="info-value">{user.throttle_queue_limit || 'Unlimited'}</span>
                  </div>
                </div>
              </div>

              {Object.keys(user.custom_attributes).length > 0 && (
                <div className="user-detail-section">
                  <h2 className="section-title">Custom Attributes</h2>
                  <div className="custom-attributes">
                    {Object.entries(user.custom_attributes).map(([key, value]) => (
                      <div key={key} className="info-item">
                        <label className="info-label">{key}</label>
                        <span className="info-value">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </>
  );
};

export default UserDetailPage; 