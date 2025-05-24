'use client'

import React, { useState, useEffect } from 'react';
import './dashboard.css';

interface DashboardData {
  totalRequests: number;
  activeUsers: number;
  newApis: number;
  monthlyUsage: {
    [key: string]: number;
  };
  activeUsersList: Array<{
    name: string;
    email: string;
  }>;
  popularApis: Array<{
    id: string;
    name: string;
    version: string;
    requests: string;
    subscribers: number;
  }>;
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

const Dashboard = () => {
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    totalRequests: 0,
    activeUsers: 0,
    newApis: 0,
    monthlyUsage: {},
    activeUsersList: [],
    popularApis: []
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/dashboard`);
      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }
      const data = await response.json();
      setDashboardData(data);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="dashboard-topbar">
        Doorman
      </div>
      <div className="dashboard-root">
        <aside className="sidebar">
          <div className="sidebar-title">Menu</div>
          <ul className="sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`sidebar-item${idx === 0 ? ' active' : ''}`}>
                  <a href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</a>
                </li>
              ) : (
                <li key={item.label} className={`sidebar-item${idx === 0 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="dashboard-main">
          <div className="dashboard-header">
            <h1>Dashboard</h1>
            <button className="refresh-button" onClick={fetchData}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          {error && (
            <div className="error-container">
              <div className="error-message">
                <span className="error-icon">⚠</span>
                {error}
              </div>
            </div>
          )}

          <div className="dashboard-cards-row">
            <div className="dashboard-card">
              <div className="dashboard-card-title">Total Monthly Requests</div>
              <div className="dashboard-card-value">{dashboardData.totalRequests.toLocaleString()}</div>
              <div className="dashboard-card-sub">+17% this month</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-card-title">Active Monthly Users</div>
              <div className="dashboard-card-value">{dashboardData.activeUsers}</div>
              <div className="dashboard-card-sub">+4% this month</div>
            </div>
            <div className="dashboard-card">
              <div className="dashboard-card-title">New APIs This Month</div>
              <div className="dashboard-card-value">{dashboardData.newApis}</div>
              <div className="dashboard-card-sub">+25% this month</div>
            </div>
          </div>
          <div className="dashboard-row">
            <div className="dashboard-panel dashboard-usage">
              <div className="dashboard-panel-title">Monthly Usage</div>
              <div className="dashboard-bar-chart">
                {['Jan','Feb','Mar','Apr','May','June','July','Aug','Sept','Oct','Nov','Dec'].map((m, i) => (
                  <div key={m} className="bar-group">
                    <div 
                      className="bar" 
                      style={{
                        height: `${dashboardData.monthlyUsage[m] || 0}%`
                      }}
                    ></div>
                    <div className="bar-label">{m}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="dashboard-panel dashboard-users">
              <div className="dashboard-panel-title">Most Active Users</div>
              <ul className="dashboard-user-list">
                {dashboardData.activeUsersList.map(u => (
                  <li key={u.email} className="dashboard-user-item">
                    <div className="user-avatar"></div>
                    <div>
                      <div className="user-name">{u.name}</div>
                      <div className="user-email">{u.email}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="dashboard-panel dashboard-table">
            <div className="dashboard-panel-title">Popular APIs This Month</div>
            <table className="dashboard-table-main">
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Name</th>
                  <th>Version</th>
                  <th>Requests</th>
                  <th>Subscribers</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {dashboardData.popularApis.map(api => (
                  <tr key={api.id}>
                    <td>{api.id}</td>
                    <td>{api.name}</td>
                    <td>{api.version}</td>
                    <td>{api.requests}</td>
                    <td>{api.subscribers}</td>
                    <td>...</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </main>
      </div>
    </>
  );
};

export default Dashboard;
