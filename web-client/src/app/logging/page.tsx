'use client'

import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ChangeEvent } from 'react';
import './logging.css';

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

interface Log {
  timestamp: string;
  level: string;
  message: string;
  source: string;
  user?: string;
  api?: string;
  endpoint?: string;
  requestId?: string;
  group?: string;
  role?: string;
  statusCode?: number;
  method?: string;
  ipAddress?: string;
  responseTime?: number;
  requestSize?: number;
  responseSize?: number;
  protocol?: string;
  userAgent?: string;
}

interface FilterState {
  startDate: string;
  endDate: string;
  startTime: string;
  endTime: string;
  user: string;
  api: string;
  endpoint: string;
  requestId: string;
  group: string;
  role: string;
  statusCode: string;
  method: string;
  ipAddress: string;
  minResponseTime: string;
  maxResponseTime: string;
  protocol: string;
}

export default function LogsPage() {
  const [theme, setTheme] = useState('light');
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    startDate: '',
    endDate: '',
    startTime: '',
    endTime: '',
    user: '',
    api: '',
    endpoint: '',
    requestId: '',
    group: '',
    role: '',
    statusCode: '',
    method: '',
    ipAddress: '',
    minResponseTime: '',
    maxResponseTime: '',
    protocol: ''
  });

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [filters]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const queryParams = new URLSearchParams();
      if (filters.startDate) queryParams.append('start_date', filters.startDate);
      if (filters.endDate) queryParams.append('end_date', filters.endDate);
      if (filters.startTime) queryParams.append('start_time', filters.startTime);
      if (filters.endTime) queryParams.append('end_time', filters.endTime);
      if (filters.user) queryParams.append('user', filters.user);
      if (filters.api) queryParams.append('api', filters.api);
      if (filters.endpoint) queryParams.append('endpoint', filters.endpoint);
      if (filters.requestId) queryParams.append('request_id', filters.requestId);
      if (filters.group) queryParams.append('group', filters.group);
      if (filters.role) queryParams.append('role', filters.role);
      if (filters.statusCode) queryParams.append('status_code', filters.statusCode);
      if (filters.method) queryParams.append('method', filters.method);
      if (filters.ipAddress) queryParams.append('ip_address', filters.ipAddress);
      if (filters.minResponseTime) queryParams.append('min_response_time', filters.minResponseTime);
      if (filters.maxResponseTime) queryParams.append('max_response_time', filters.maxResponseTime);
      if (filters.protocol) queryParams.append('protocol', filters.protocol);

      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL}/platform/logs?${queryParams.toString()}`);
      if (!response.ok) {
        throw new Error('Failed to fetch logs');
      }
      const data = await response.json();
      setLogs(data);
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

  const handleFilterChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value
    }));
  };

  return (
    <>
      <div className="logs-topbar">
        Doorman
      </div>
      <div className="logs-root">
        <aside className="logs-sidebar">
          <div className="logs-sidebar-title">Menu</div>
          <ul className="logs-sidebar-list">
            {menuItems.map((item, idx) => (
              item.href ? (
                <li key={item.label} className={`logs-sidebar-item${idx === 7 ? ' active' : ''}`}>
                  <a href={item.href} style={{ color: 'inherit', textDecoration: 'none', display: 'block', width: '100%' }}>{item.label}</a>
                </li>
              ) : (
                <li key={item.label} className={`logs-sidebar-item${idx === 7 ? ' active' : ''}`}>{item.label}</li>
              )
            ))}
          </ul>
          <button className="logs-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </aside>
        <main className="logs-main">
          <div className="logs-header">
            <h1>Logs</h1>
            <button className="refresh-button" onClick={fetchLogs}>
              <span className="refresh-icon">↻</span>
              Refresh
            </button>
          </div>

          <div className="filters-container">
            <div className="filters-grid">
              <div className="filter-group">
                <label htmlFor="startDate">Start Date</label>
                <input
                  type="date"
                  id="startDate"
                  name="startDate"
                  value={filters.startDate}
                  onChange={handleFilterChange}
                />
              </div>
              <div className="filter-group">
                <label htmlFor="endDate">End Date</label>
                <input
                  type="date"
                  id="endDate"
                  name="endDate"
                  value={filters.endDate}
                  onChange={handleFilterChange}
                />
              </div>
              <div className="filter-group">
                <label htmlFor="startTime">Start Time</label>
                <input
                  type="time"
                  id="startTime"
                  name="startTime"
                  value={filters.startTime}
                  onChange={handleFilterChange}
                />
              </div>
              <div className="filter-group">
                <label htmlFor="endTime">End Time</label>
                <input
                  type="time"
                  id="endTime"
                  name="endTime"
                  value={filters.endTime}
                  onChange={handleFilterChange}
                />
              </div>
            </div>
            
            <button 
              className="more-filters-button"
              onClick={() => setShowMoreFilters(!showMoreFilters)}
            >
              {showMoreFilters ? 'Show Less Filters' : 'More Filters'}
              <span className={`more-filters-icon ${showMoreFilters ? 'expanded' : ''}`}>▼</span>
            </button>

            {showMoreFilters && (
              <div className="more-filters-section">
                <div className="filter-group">
                  <label htmlFor="user">User</label>
                  <input
                    type="text"
                    id="user"
                    name="user"
                    placeholder="Filter by user"
                    value={filters.user}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="api">API</label>
                  <input
                    type="text"
                    id="api"
                    name="api"
                    placeholder="Filter by API"
                    value={filters.api}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="endpoint">Endpoint</label>
                  <input
                    type="text"
                    id="endpoint"
                    name="endpoint"
                    placeholder="Filter by endpoint"
                    value={filters.endpoint}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="requestId">Request ID</label>
                  <input
                    type="text"
                    id="requestId"
                    name="requestId"
                    placeholder="Filter by request ID"
                    value={filters.requestId}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="group">Group</label>
                  <input
                    type="text"
                    id="group"
                    name="group"
                    placeholder="Filter by group"
                    value={filters.group}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="role">Role</label>
                  <input
                    type="text"
                    id="role"
                    name="role"
                    placeholder="Filter by role"
                    value={filters.role}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="statusCode">Status Code</label>
                  <input
                    type="text"
                    id="statusCode"
                    name="statusCode"
                    placeholder="e.g., 200, 404, 500"
                    value={filters.statusCode}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="method">HTTP Method</label>
                  <select
                    id="method"
                    name="method"
                    value={filters.method}
                    onChange={handleFilterChange}
                  >
                    <option value="">All Methods</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                    <option value="HEAD">HEAD</option>
                    <option value="OPTIONS">OPTIONS</option>
                  </select>
                </div>
                <div className="filter-group">
                  <label htmlFor="ipAddress">IP Address</label>
                  <input
                    type="text"
                    id="ipAddress"
                    name="ipAddress"
                    placeholder="Filter by IP"
                    value={filters.ipAddress}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="minResponseTime">Min Response Time (ms)</label>
                  <input
                    type="number"
                    id="minResponseTime"
                    name="minResponseTime"
                    placeholder="Min time"
                    value={filters.minResponseTime}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="maxResponseTime">Max Response Time (ms)</label>
                  <input
                    type="number"
                    id="maxResponseTime"
                    name="maxResponseTime"
                    placeholder="Max time"
                    value={filters.maxResponseTime}
                    onChange={handleFilterChange}
                  />
                </div>
                <div className="filter-group">
                  <label htmlFor="protocol">Protocol</label>
                  <select
                    id="protocol"
                    name="protocol"
                    value={filters.protocol}
                    onChange={handleFilterChange}
                  >
                    <option value="">All Protocols</option>
                    <option value="HTTP">HTTP</option>
                    <option value="HTTPS">HTTPS</option>
                    <option value="HTTP/2">HTTP/2</option>
                    <option value="HTTP/3">HTTP/3</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {loading ? (
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Loading logs...</p>
            </div>
          ) : (
            <div className="logs-container">
              {logs.length === 0 ? (
                <div className="no-logs">
                  No logs found for the selected time period
                </div>
              ) : (
                <table className="logs-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Level</th>
                      <th>Message</th>
                      <th>Source</th>
                      <th>User</th>
                      <th>API</th>
                      <th>Endpoint</th>
                      <th>Method</th>
                      <th>Status</th>
                      <th>Response Time</th>
                      <th>IP Address</th>
                      <th>Protocol</th>
                      <th>Request ID</th>
                      <th>Group</th>
                      <th>Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, index) => (
                      <tr key={index} className={`log-row ${log.level.toLowerCase()}`}>
                        <td>{format(new Date(log.timestamp), 'yyyy-MM-dd HH:mm:ss')}</td>
                        <td>
                          <span className={`log-level ${log.level.toLowerCase()}`}>
                            {log.level}
                          </span>
                        </td>
                        <td>{log.message}</td>
                        <td>{log.source}</td>
                        <td>{log.user || '-'}</td>
                        <td>{log.api || '-'}</td>
                        <td>{log.endpoint || '-'}</td>
                        <td>{log.method || '-'}</td>
                        <td>
                          <span className={`status-code ${log.statusCode ? (log.statusCode >= 200 && log.statusCode < 300 ? 'success' : log.statusCode >= 400 ? 'error' : 'warning') : ''}`}>
                            {log.statusCode || '-'}
                          </span>
                        </td>
                        <td>{log.responseTime ? `${log.responseTime}ms` : '-'}</td>
                        <td>{log.ipAddress || '-'}</td>
                        <td>{log.protocol || '-'}</td>
                        <td>{log.requestId || '-'}</td>
                        <td>{log.group || '-'}</td>
                        <td>{log.role || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </main>
      </div>
    </>
  );
} 