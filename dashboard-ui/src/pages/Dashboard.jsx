import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGetRaw, apiGet } from '../utils/api';
import Clock from '../components/Clock';
import FraudFeed from '../components/FraudFeed';
import DriverIntelligence from '../components/DriverIntelligence';
import ZoneMap from '../components/ZoneMap';
import TripScorer from '../components/TripScorer';

const EMPTY_KPI = {
  total_flagged_24h: 0,
  action_tier_24h: 0,
  watchlist_tier_24h: 0,
  action_score_avg_pct: 0,
  estimated_recoverable_per_trip: 0,
  indicative_annual_recovery_crore: 0,
};

const fmtInt = (n) => (Number(n) || 0).toLocaleString('en-IN');
const fmtPct = (n) => `${(Number(n) || 0).toFixed(1)}%`;
const fmtInr = (n) => `\u20B9${(Number(n) || 0).toFixed(2)}`;
const fmtCr  = (n) => `\u20B9${(Number(n) || 0).toFixed(2)} Cr`;

function MetricCard({ value, label, sub, highlight }) {
  return (
    <div style={{
      flex: 1,
      padding: '12px 16px',
      background: highlight
        ? 'rgba(255,107,53,0.07)'
        : 'rgba(255,255,255,0.025)',
      border: `1px solid ${highlight ? 'rgba(255,107,53,0.2)' : 'rgba(255,255,255,0.06)'}`,
      borderRadius: 8,
      minWidth: 0,
    }}>
      <div style={{
        fontSize: 22,
        fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        color: highlight ? 'var(--orange)' : 'var(--text)',
        lineHeight: 1,
        marginBottom: 5,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {value}
      </div>
      <div style={{
        fontSize: 10,
        color: 'var(--muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.07em',
        fontWeight: 500,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }}>
        {label}
      </div>
      {sub && (
        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.22)', marginTop: 2 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function OfflineBanner({ onRetry }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '8px 20px',
      background: 'rgba(239,68,68,0.08)',
      borderBottom: '1px solid rgba(239,68,68,0.25)',
      fontSize: 12, color: 'var(--danger)', flexShrink: 0,
    }}>
      <span>
        <strong>API offline.</strong> Live KPIs and feeds are paused. Retrying every 30 s.
      </span>
      <button
        onClick={onRetry}
        style={{
          padding: '4px 12px', background: 'rgba(239,68,68,0.15)',
          border: '1px solid rgba(239,68,68,0.3)', borderRadius: 4,
          color: 'var(--danger)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
        }}
      >
        Retry now
      </button>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [apiStatus, setApiStatus] = useState('checking');
  const [healthMeta, setHealthMeta] = useState(null);
  const [kpi, setKpi] = useState(EMPTY_KPI);
  const [scorerOpen, setScorerOpen] = useState(false);

  const doHealthCheck = async () => {
    try {
      const h = await apiGetRaw('/health');
      if (h.ok) {
        const hd = await h.json();
        setHealthMeta(hd);
        setApiStatus('online');
      } else {
        setApiStatus('offline');
      }
    } catch {
      setApiStatus('offline');
    }
  };

  const fetchKpi = async () => {
    try {
      const data = await apiGet('/kpi/live');
      setKpi({ ...EMPTY_KPI, ...data });
    } catch { /* keep prior KPI snapshot */ }
  };

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await doHealthCheck();
    };
    tick();
    const t = setInterval(tick, 30000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  useEffect(() => {
    if (apiStatus !== 'online') return;
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await fetchKpi();
    };
    tick();
    const t = setInterval(tick, 30000);
    return () => { cancelled = true; clearInterval(t); };
  }, [apiStatus]);

  if (apiStatus === 'checking') {
    return (
      <div style={{
        position: 'fixed', inset: 0, background: '#0a0c10',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 10, color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-mono)',
      }}>
        <div className="spinner" /> Connecting to Porter Intelligence API...
      </div>
    );
  }

  const isOffline      = apiStatus === 'offline';
  const syntheticFeed  = healthMeta?.synthetic_feed_enabled;
  const runtimeMode    = healthMeta?.runtime_mode ?? 'unknown';
  const modeLabel      = isOffline ? 'OFFLINE' : syntheticFeed ? 'DEMO MODE' : runtimeMode === 'prod' ? 'LIVE' : 'SHADOW';
  const modeColor      = isOffline ? 'var(--danger)' : syntheticFeed ? 'var(--warning)' : 'var(--success)';

  const flaggedToday = kpi.total_flagged_24h
    || ((kpi.action_tier_24h || 0) + (kpi.watchlist_tier_24h || 0));
  const actionCount  = kpi.action_tier_24h || 0;
  const scoreAvg     = kpi.action_score_avg_pct || 0;
  const recPerTrip   = kpi.estimated_recoverable_per_trip || 0;
  const annualCrore  = kpi.indicative_annual_recovery_crore || 0;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: '100vh', background: '#0a0c10',
      color: 'var(--text)', overflow: 'hidden',
    }}>
      {/* ── Header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', height: 50,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0, background: '#0d0f14',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--orange)', borderRadius: 6,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 800, fontSize: 14, color: 'white', fontFamily: 'var(--font-display)',
          }}>P</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.2, fontFamily: 'var(--font-display)' }}>
              Trip Intelligence
            </div>
            <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 1 }}>
              22 Cities · Behavioral Scoring Layer
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: modeColor,
              animation: 'pulse-dot 2s infinite',
            }} />
            <span style={{ fontSize: 10, color: modeColor, fontWeight: 700, letterSpacing: '0.07em' }}>
              {modeLabel}
            </span>
          </div>

          <Clock />

          <button
            onClick={() => setScorerOpen(v => !v)}
            style={{
              padding: '5px 11px',
              background: scorerOpen ? 'rgba(255,107,53,0.15)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${scorerOpen ? 'rgba(255,107,53,0.3)' : 'rgba(255,255,255,0.1)'}`,
              borderRadius: 5, color: scorerOpen ? 'var(--orange)' : 'var(--muted)',
              fontSize: 11, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font-display)',
            }}
          >
            Score Trip
          </button>

          <button
            onClick={() => navigate('/login')}
            style={{
              padding: '5px 12px',
              background: 'rgba(255,107,53,0.1)',
              border: '1px solid rgba(255,107,53,0.2)',
              borderRadius: 5, color: 'var(--orange)',
              fontSize: 11, fontWeight: 600, cursor: 'pointer',
              fontFamily: 'var(--font-display)',
            }}
          >
            Analyst →
          </button>
        </div>
      </div>

      {isOffline && (
        <OfflineBanner onRetry={() => { setApiStatus('checking'); doHealthCheck(); }} />
      )}

      {/* ── KPI Strip ── */}
      <div style={{
        display: 'flex', gap: 8, padding: '8px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        flexShrink: 0, background: '#0a0c10',
      }}>
        <MetricCard
          value={flaggedToday.toLocaleString('en-IN')}
          label="Flagged Today"
          sub="action + watchlist"
        />
        <MetricCard
          value={actionCount.toLocaleString('en-IN')}
          label="Action Tier"
          sub="requires analyst review"
          highlight
        />
        <MetricCard
          value={`${scoreAvg.toFixed(1)}%`}
          label="Model Score Avg"
          sub="action-tier cases"
        />
        <MetricCard
          value={`₹${recPerTrip.toFixed(2)}`}
          label="Recovery / Trip"
          sub="action tier avg"
        />
        <MetricCard
          value={`₹${annualCrore.toFixed(2)} Cr`}
          label="Annual Recovery"
          sub="at Porter scale"
        />
      </div>

      {/* ── 3-column body ── */}
      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '300px 1fr 280px',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Left: Trip Feed */}
        <div style={{
          borderRight: '1px solid rgba(255,255,255,0.06)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <FraudFeed thresholds={healthMeta?.thresholds} />
        </div>

        {/* Center: Map */}
        <div style={{ overflow: 'hidden', position: 'relative' }}>
          <ZoneMap />
        </div>

        {/* Right: Driver Intelligence */}
        <div style={{
          borderLeft: '1px solid rgba(255,255,255,0.06)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <DriverIntelligence />
        </div>
      </div>

      {/* ── Trip Scorer (collapsible bottom panel) ── */}
      {scorerOpen && (
        <div style={{
          borderTop: '1px solid rgba(255,107,53,0.2)',
          flexShrink: 0,
          maxHeight: '40vh',
          overflowY: 'auto',
          background: '#0d0f14',
        }}>
          <TripScorer />
        </div>
      )}

      {/* ── Footer ── */}
      <div style={{
        height: 24, background: '#0d0f14',
        borderTop: '1px solid rgba(255,255,255,0.04)',
        display: 'flex', alignItems: 'center',
        justifyContent: 'flex-end',
        padding: '0 16px',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)', letterSpacing: '0.05em' }}>
          {syntheticFeed ? 'SYNTHETIC DEMO DATA' : runtimeMode === 'prod' ? 'LIVE DATA' : 'SHADOW MODE'} · PORTER INTELLIGENCE PLATFORM
        </span>
      </div>
    </div>
  );
}
