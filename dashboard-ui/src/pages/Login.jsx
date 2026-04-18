import React, { useState } from 'react';
import { apiFormPost } from '../utils/api';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const form = new URLSearchParams();
      form.append('username', username);
      form.append('password', password);
      const data = await apiFormPost('/auth/token', form);
      login(data.access_token, data.role || 'ops_analyst', data.name || username);
      navigate('/analyst');
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  }

  const DEMO_CREDS = [
    { label: 'Analyst', username: 'analyst_1', password: 'DemoAnalyst2026!' },
    { label: 'Ops Manager', username: 'ops_manager', password: 'DemoOps2026!' },
    { label: 'Admin', username: 'admin', password: 'DemoAdmin2026!' },
  ];

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-mark">P</div>
          <div>
            <div className="login-title">Porter Intelligence</div>
            <div className="login-sub">Analyst Workstation</div>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <span>⚠</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="login-field">
            <label className="login-label">Username</label>
            <input
              className="login-input"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="e.g. analyst_1"
              autoFocus
              required
            />
          </div>
          <div className="login-field">
            <label className="login-label">Password</label>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          <button className="login-btn" type="submit" disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div style={{
          marginTop: 24,
          padding: '12px 16px',
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--muted)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8, color: 'var(--text)' }}>
            Demo Credentials
          </div>
          {DEMO_CREDS.map(cred => (
            <div
              key={cred.username}
              style={{
                marginBottom: 4, cursor: 'pointer', padding: '4px 6px',
                borderRadius: 4, transition: 'background 0.15s',
              }}
              onClick={() => { setUsername(cred.username); setPassword(cred.password); }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <strong style={{ color: 'var(--text)' }}>{cred.label}:</strong>{' '}
              {cred.username} / {cred.password}
            </div>
          ))}
          <div style={{ marginTop: 8, fontSize: 11 }}>Click any row to auto-fill</div>
        </div>
      </div>
    </div>
  );
}
