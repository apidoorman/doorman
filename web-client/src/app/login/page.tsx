'use client'

import React, { useState, useEffect } from 'react';
import "./login.css";

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isClient, setIsClient] = useState(false);
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    setIsClient(true);
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  const pylogin_server = process.env.NEXT_PUBLIC_PYLOGIN_SERVER;

  interface LoginResponse {
    detail?: string;
    server?: string;
    username?: string;
  }

  const handleLogin = async (e: React.MouseEvent<HTMLButtonElement>): Promise<void> => {
    e.preventDefault();

    let server;

    var organization = email.substring(email.lastIndexOf("@") +1);

    try {
      server = "http://localhost:3002";

      const authResponse = await fetch(`${server}/platform/authorization`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ email, password }),
      });

      if (authResponse.ok) {
        const authData = await authResponse.json();
        if (authData.token) {
          localStorage.setItem('authToken', authData.token);
        }
        window.location.href = '/dashboard';
      } else {
        const errorData: LoginResponse = await authResponse.json();
        setErrorMessage(errorData.detail || 'An error occurred');
      }
    } catch {
      setErrorMessage('Invalid email or password');
    }
  };

  if (!isClient) {
    return null;
  }

  return (
    <div className="login-page">
      <div className="container">
        <div className="content">
          <div className="copy">
            <h1 className="title">Login</h1>
            <p className="enter-your-email-and-password">
              Enter your email and password
            </p>
          </div>
          <div className="input-and-button">
            <form onSubmit={(e) => e.preventDefault()}>
              <div className="email-field">
                <input
                  type="email"
                  className="email"
                  placeholder="email@domain.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="password-field">
                <input 
                  type="password" 
                  className="password" 
                  placeholder="••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <button className="button" onClick={handleLogin}>Login</button>
            </form>
          </div>
          {errorMessage && <div className="error-message">{errorMessage}</div>}
          <p className="terms">
            By clicking Login, you agree to our{" "}
            <a href="/terms" className="link">Terms of Service</a> and{" "}
            <a href="/privacy" className="link">Privacy Policy</a>.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;