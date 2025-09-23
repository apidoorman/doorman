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
  request_id?: string;
  level: string;
  message: string;
  source: string;
  user?: string;
  endpoint?: string;
  method?: string;
  ipAddress?: string;
  responseTime?: number;
}

interface FilterState {
  startDate: string;
  endDate: string;
  startTime: string;
  endTime: string;
  user: string;
  endpoint: string;
  request_id: string;
  method: string;
  ipAddress: string;
  minResponseTime: string;
  maxResponseTime: string;
  level: string;
}



export default function LogsPage() {

  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState<FilterState>(() => {
    // Set default to last 30 minutes of today
    const now = new Date();
    const today = now.toISOString().split('T')[0]; // Always use today's date
    
    // Calculate 30 minutes ago, but ensure we stay within today
    const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000);
    const startTime = thirtyMinutesAgo.toTimeString().slice(0, 5);
    const endTime = now.toTimeString().slice(0, 5);
    
    return {
      startDate: today,
      endDate: today,
      startTime: startTime,
      endTime: endTime,
      user: '',
      endpoint: '',
      request_id: '',
      method: '',
      ipAddress: '',
      minResponseTime: '',
      maxResponseTime: '',
      level: ''
    };
  });



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
      if (filters.endpoint) queryParams.append('endpoint', filters.endpoint);
      if (filters.request_id) queryParams.append('request_id', filters.request_id);
      if (filters.method) queryParams.append('method', filters.method);
      if (filters.ipAddress) queryParams.append('ip_address', filters.ipAddress);
      if (filters.minResponseTime) queryParams.append('min_response_time', filters.minResponseTime);
      if (filters.maxResponseTime) queryParams.append('max_response_time', filters.maxResponseTime);
      if (filters.level) queryParams.append('level', filters.level);

      const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL || 'http://localhost:3002';
      const url = `${serverUrl}/platform/logging/logs?${queryParams.toString()}`;
      console.log('Fetching logs with URL:', url);
      console.log('Filters:', filters);
      
      const response = await fetch(url, {
        credentials: 'include'
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.error_message || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(errorMessage);
      }
      const responseData = await response.json();
      
      // Handle the response format
      if (responseData && responseData.logs) {
        setLogs(responseData.logs);
      } else if (responseData && Array.isArray(responseData)) {
        // Fallback for array format
        setLogs(responseData);
      } else {
        // No logs found or unexpected format
        setLogs([]);
        console.warn('Unexpected response format:', responseData);
      }
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

  const clearFilters = () => {
    const now = new Date();
    const today = now.toISOString().split('T')[0]; // Always use today's date
    
    // Calculate 30 minutes ago, but ensure we stay within today
    const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000);
    const startTime = thirtyMinutesAgo.toTimeString().slice(0, 5);
    const endTime = now.toTimeString().slice(0, 5);
    
    setFilters({
      startDate: today,
      endDate: today,
      startTime: startTime,
      endTime: endTime,
      user: '',
      endpoint: '',
      request_id: '',
      method: '',
      ipAddress: '',
      minResponseTime: '',
      maxResponseTime: '',
      level: ''
    });
  };

  const exportLogs = async (format: 'json' | 'csv') => {
    try {
      setExporting(true);
      const queryParams = new URLSearchParams();
      queryParams.append('format', format);
      if (filters.startDate) queryParams.append('start_date', filters.startDate);
      if (filters.endDate) queryParams.append('end_date', filters.endDate);
      if (filters.user) queryParams.append('user', filters.user);
      if (filters.endpoint) queryParams.append('endpoint', filters.endpoint);
      if (filters.level) queryParams.append('level', filters.level);

      const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL || 'http://localhost:3002';
      const response = await fetch(`${serverUrl}/platform/logging/logs/download?${queryParams.toString()}`, {
        credentials: 'include'
      });
      if (!response.ok) {
        throw new Error('Failed to export logs');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `logs_export_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unknown error occurred during export');
      }
    } finally {
      setExporting(false);
    }
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
            <div className="logs-header-controls">
              <div className="export-buttons">
                <button 
                  className="export-button"
                  onClick={() => exportLogs('json')}
                  disabled={exporting}
                >
                  {exporting ? 'Exporting...' : 'Export JSON'}
                </button>
                <button 
                  className="export-button"
                  onClick={() => exportLogs('csv')}
                  disabled={exporting}
                >
                  {exporting ? 'Exporting...' : 'Export CSV'}
                </button>
              </div>
              <button className="refresh-button" onClick={fetchLogs}>
                <span className="refresh-icon">↻</span>
                Refresh
              </button>
            </div>
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
            
            <div className="filter-buttons">
              <button 
                className="more-filters-button"
                onClick={() => setShowMoreFilters(!showMoreFilters)}
              >
                {showMoreFilters ? 'Show Less Filters' : 'More Filters'}
                <span className={`more-filters-icon ${showMoreFilters ? 'expanded' : ''}`}>▼</span>
              </button>
              <button 
                className="clear-filters-button"
                onClick={clearFilters}
              >
                Clear Filters
              </button>
            </div>

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
                  <label htmlFor="request_id">Request ID</label>
                  <input
                    type="text"
                    id="request_id"
                    name="request_id"
                    placeholder="Filter by request ID"
                    value={filters.request_id}
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
                  <label htmlFor="level">Log Level</label>
                  <select
                    id="level"
                    name="level"
                    value={filters.level}
                    onChange={handleFilterChange}
                  >
                    <option value="">All Levels</option>
                    <option value="ERROR">Error</option>
                    <option value="WARNING">Warning</option>
                    <option value="INFO">Info</option>
                    <option value="DEBUG">Debug</option>
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
                      <th>Request ID</th>
                      <th>Level</th>
                      <th>Message</th>
                      <th>Source</th>
                      <th>User</th>
                      <th>Endpoint</th>
                      <th>Method</th>
                      <th>Response Time</th>
                      <th>IP Address</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, index) => (
                      <tr key={index} className={`log-row ${log.level.toLowerCase()}`}>
                        <td>{format(new Date(log.timestamp), 'yyyy-MM-dd HH:mm:ss')}</td>
                        <td>{log.request_id || '-'}</td>
                        <td>
                          <span className={`log-level ${log.level.toLowerCase()}`}>
                            {log.level}
                          </span>
                        </td>
                        <td>{log.message}</td>
                        <td>{log.source}</td>
                        <td>{log.user || '-'}</td>
                        <td>{log.endpoint || '-'}</td>
                        <td>{log.method || '-'}</td>
                        <td>
                          <span className={`status-code ${log.responseTime ? (log.responseTime < 100 ? 'success' : log.responseTime < 500 ? 'warning' : 'error') : ''}`}>
                            {log.responseTime ? `${log.responseTime}ms` : '-'}
                          </span>
                        </td>
                        <td>{log.ipAddress || '-'}</td>
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