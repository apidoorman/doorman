'use client'

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import './monitor.css';

interface Metric {
  timestamp: string;
  value: number;
}

interface Metrics {
  totalRequests: Metric[];
  errorRate: Metric[];
  avgResponseTime: Metric[];
  activeUsers: Metric[];
  bandwidthUsage: Metric[];
  cpuUsage: Metric[];
  memoryUsage: Metric[];
  statusCodes: {
    [key: string]: number;
  };
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

const MonitorPage: React.FC = () => {
  const [theme, setTheme] = useState('light');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [timeRange, setTimeRange] = useState('24h');

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [timeRange]);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/platform/metrics?range=${timeRange}`);
      if (!response.ok) {
        throw new Error('Failed to fetch metrics');
      }
      const data = await response.json();
      setMetrics(data);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unknown error occurred');
      }
      setMetrics([]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    sessionStorage.clear();
    setTimeout(() => {
      window.location.replace('/');
    }, 50);
  };

  const renderMetricChart = (data: Metric[], title: string): React.ReactNode => {
    return (
      <div className="monitor-metric-chart">
        <div className="monitor-chart-placeholder">
          {title} chart will be implemented here
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="monitor-topbar">
        Doorman
      </div>
      <div className="monitor-root">
          <aside className="monitor-sidebar">
          <div className="monitor-sidebar-title">Menu</div>
          <ul className="monitor-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`monitor-sidebar-item${idx === 6 ? ' active' : ''}`}>
                  <Link href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</Link>
                </li>
              ) : (
                <li key={item.label} className={`monitor-sidebar-item${idx === 6 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="monitor-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="monitor-main">
          <div className="monitor-header-row">
            <h1 className="monitor-title">Monitor</h1>
            <button className="monitor-refresh-button" onClick={fetchMetrics}>
              <span className="monitor-refresh-icon">↻</span>
              Refresh
            </button>
          </div>
          <div className="monitor-controls">
            <select 
              value={timeRange} 
              onChange={(e) => setTimeRange(e.target.value)}
              className="monitor-time-range-select"
            >
              <option value="1h">Last Hour</option>
              <option value="6h">Last 6 Hours</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>

          {error && (
            <div className="monitor-error-message">
              {error}
            </div>
          )}

          {loading ? (
            <div className="monitor-loading-spinner">
              <div className="monitor-spinner"></div>
              <p>Loading metrics...</p>
            </div>
          ) : (
            <div className="monitor-metrics-grid">
              <div className="monitor-metric-card">
                <h3>Total Requests</h3>
                <div className="monitor-metric-value">
                  {metrics.length > 0 
                    ? metrics.reduce((sum, m) => sum + m.requests, 0).toLocaleString()
                    : '0'
                  }
                </div>
                {renderMetricChart(
                  metrics.length > 0 
                    ? metrics.map(m => ({ timestamp: m.timestamp, value: m.requests }))
                    : [],
                  'Total Requests'
                )}
              </div>

              <div className="monitor-metric-card">
                <h3>Error Rate</h3>
                <div className="monitor-metric-value">
                  {metrics.length > 0
                    ? ((metrics.reduce((sum, m) => sum + m.errors, 0) / 
                        metrics.reduce((sum, m) => sum + m.requests, 0)) * 100).toFixed(2)
                    : '0.00'
                  }%
                </div>
                {renderMetricChart(
                  metrics.length > 0
                    ? metrics.map(m => ({ timestamp: m.timestamp, value: m.errors }))
                    : [],
                  'Error Rate'
                )}
              </div>

              <div className="monitor-metric-card">
                <h3>Average Response Time</h3>
                <div className="monitor-metric-value">
                  {metrics.length > 0
                    ? Math.round(metrics.reduce((sum, m) => sum + m.avgResponseTime, 0) / metrics.length)
                    : '0'
                  }ms
                </div>
                {renderMetricChart(
                  metrics.length > 0
                    ? metrics.map(m => ({ timestamp: m.timestamp, value: m.avgResponseTime }))
                    : [],
                  'Average Response Time'
                )}
              </div>

              <div className="monitor-metric-card">
                <h3>Active Users</h3>
                <div className="monitor-metric-value">
                  {metrics.length > 0
                    ? Math.max(...metrics.map(m => m.activeUsers))
                    : '0'
                  }
                </div>
                {renderMetricChart(
                  metrics.length > 0
                    ? metrics.map(m => ({ timestamp: m.timestamp, value: m.activeUsers }))
                    : [],
                  'Active Users'
                )}
              </div>

              <div className="monitor-metric-card">
                <h3>Bandwidth Usage</h3>
                <div className="monitor-metric-value">
                  {metrics.length > 0
                    ? (metrics.reduce((sum, m) => sum + m.bandwidth, 0) / 1000000).toFixed(2)
                    : '0.00'
                  } MB
                </div>
                {renderMetricChart(
                  metrics.length > 0
                    ? metrics.map(m => ({ timestamp: m.timestamp, value: m.bandwidth }))
                    : [],
                  'Bandwidth Usage'
                )}
              </div>

              <div className="monitor-metric-card wide">
                <h3>Status Code Distribution</h3>
                <div className="monitor-status-codes">
                  {metrics.length > 0 ? (
                    Object.entries(metrics[metrics.length - 1].statusCodes).map(([code, count]) => (
                      <div key={code} className="monitor-status-code-item">
                        <span className="monitor-status-code-label">{code}</span>
                        <span className="monitor-status-code-count">{Number(count)}</span>
                      </div>
                    ))
                  ) : (
                    <div className="monitor-status-code-item">
                      <span className="monitor-status-code-label">No data</span>
                      <span className="monitor-status-code-count">0</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default MonitorPage; 