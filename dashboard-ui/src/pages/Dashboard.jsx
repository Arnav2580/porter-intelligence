import React, { useState, useEffect } from 'react';
import { apiGet, apiGetRaw } from '../utils/api';
import Clock from '../components/Clock';
import KPIPanel from '../components/KPIPanel';
import TierSummaryBar from '../components/TierSummaryBar';
import ReallocationPanel from '../components/ReallocationPanel';
import QueryPanel from '../components/QueryPanel';
import TripScorer from '../components/TripScorer';
import FraudFeed from '../components/FraudFeed';
import DriverIntelligence from '../components/DriverIntelligence';
import ZoneMap from '../components/ZoneMap';
import { Link } from 'react-router-dom';

function OfflineScreen({ onRetry }) {
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'var(--navy)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 24,
      zIndex: 9999,
    }}>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 48, fontWeight: 800, color: 'var(--border)' }}>P</div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Porter Intelligence Platform</div>
      <div style={{
        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '12px 24px', textAlign: 'center'
      }}>
        <div style={{ color: 'var(--danger)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 14, marginBottom: 6 }}>API Offline</div>
        <div style={{ color: 'var(--muted)', fontSize: 12, fontFamily: 'var(--font-mono)', lineHeight: 1.8 }}>
          Start the backend:<br/>
          <span style={{ color: 'var(--orange)' }}>uvicorn api.main:app --port 8000</span>
        </div>
      </div>
      <button onClick={onRetry} style={{
        background: 'var(--orange)', color: 'white', border: 'none', borderRadius: 6, padding: '10px 24px',
        fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 13, cursor: 'pointer', letterSpacing: '0.05em'
      }}>Retry Connection</button>
    </div>
  );
}

export default function Dashboard() {
  const [kpi, setKpi]               = useState(null);
  const [apiOk, setApiOk]           = useState(null);
  const [apiStatus, setApiStatus]   = useState('checking');

  const doHealthCheck = async () => {
    try {
      const h = await apiGetRaw('/health');
      if (h.ok) {
        const hd = await h.json();
        setApiOk(hd.model_loaded);
        setApiStatus('online');
        const kd = await apiGet('/kpi/summary');
        setKpi(kd);
      } else {
        setApiStatus('offline');
      }
    } catch(e) {
      setApiStatus('offline');
    }
  };

  useEffect(() => {
    doHealthCheck();
    const t = setInterval(() => {
      apiGet('/kpi/summary')
        .then(d => { setKpi(d); setApiStatus('online'); })
        .catch(() => setApiStatus('offline'));
    }, 30000);
    return () => clearInterval(t);
  }, []);

  if (apiStatus === 'checking') {
    return (
      <div style={{ position: 'fixed', inset: 0, background: 'var(--navy)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)', fontSize: 13 }}>
        <div className="spinner" /> Connecting to Porter Intelligence API...
      </div>
    );
  }

  if (apiStatus === 'offline') {
    return <OfflineScreen onRetry={() => { setApiStatus('checking'); doHealthCheck(); }} />;
  }

  return (
    <>
      <header className="header">
        <div className="header-logo">
          <div className="header-logo-mark">P</div>
          <div>
            <div className="header-title">Porter Intelligence Dashboard</div>
            <div className="header-subtitle">AI Fraud Detection Platform &middot; Bangalore Operations</div>
          </div>
        </div>
        <div className="header-right">
          <Link to="/login" style={{ fontSize: 12, color: 'var(--orange)', marginRight: 16 }}>Go to Analyst Workspace</Link>
          {apiOk !== null && (
            <div className="live-badge" style={{ color: apiOk ? 'var(--success)' : 'var(--danger)' }}>
              <div className="live-dot" style={{ background: apiOk ? 'var(--success)' : 'var(--danger)', animation: apiOk ? 'pulse-dot 2s infinite' : 'none' }} />
              {apiOk ? 'MODEL LIVE' : 'MODEL OFFLINE'}
            </div>
          )}
          <Clock />
        </div>
      </header>

      <main className="main">
        <div className="col">
          {kpi ? <KPIPanel kpi={kpi} /> : <div className="loading"><div className="spinner" /> Loading KPIs...</div>}
          <TierSummaryBar />
          <ReallocationPanel />
          <QueryPanel />
          <TripScorer />
        </div>
        <FraudFeed />
        <DriverIntelligence />
        <ZoneMap />
      </main>
    </>
  );
}
