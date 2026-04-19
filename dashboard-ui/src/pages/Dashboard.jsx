import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGetRaw, apiGet } from '../utils/api';
import Clock from '../components/Clock';
import FraudFeed from '../components/FraudFeed';
import DriverIntelligence from '../components/DriverIntelligence';
import ZoneMap from '../components/ZoneMap';
import TripScorer from '../components/TripScorer';

const BENCHMARK = {
  total_flagged_24h:                  4442,
  action_tier_24h:                    1027,
  watchlist_tier_24h:                 3415,
  action_score_avg_pct:               94.4,
  estimated_recoverable_per_trip:     5.08,
  indicative_annual_recovery_crore:   6.87,
};

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

function OfflineScreen({ onRetry }) {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: '#0a0c10',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 20,
    }}>
      <div style={{
        width: 44, height: 44,
        background: 'var(--orange)', borderRadius: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontWeight: 800, fontSize: 22, color: 'white',
        fontFamily: 'var(--font-display)',
      }}>P</div>
      <div style={{ color: 'var(--text)', fontSize: 16, fontWeight: 600, fontFamily: 'var(--font-display)' }}>
        Porter Trip Intelligence
      </div>
      <div style={{
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.25)',
        borderRadius: 8, padding: '12px 24px', textAlign: 'center',
      }}>
        <div style={{ color: 'var(--danger)', fontWeight: 700, fontSize: 13, marginBottom: 4 }}>API Offline</div>
        <div style={{ color: 'var(--muted)', fontSize: 11 }}>Check backend connection</div>
      </div>
      <button
        onClick={onRetry}
        style={{
          padding: '8px 22px', background: 'var(--orange)', border: 'none',
          borderRadius: 6, color: 'white', fontWeight: 700, fontSize: 12,
          cursor: 'pointer', fontFamily: 'var(--font-display)',
        }}
      >
        Retry Connection
      </button>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [apiStatus, setApiStatus] = useState('checking');
  const [healthMeta, setHealthMeta] = useState(null);
  const [kpi, setKpi] = useState(BENCHMARK);
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
      setKpi({
        ...BENCHMARK,
        ...Object.fromEntries(
          Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== 0 && v !== '')
        ),
      });
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

  if (apiStatus === 'offline') {
    return <OfflineScreen onRetry={() => { setApiStatus('checking'); doHealthCheck(); }} />;
  }

  const syntheticFeed = healthMeta?.synthetic_feed_enabled;
  const runtimeMode   = healthMeta?.runtime_mode ?? 'unknown';
  const modeLabel     = syntheticFeed ? 'DEMO MODE' : runtimeMode === 'prod' ? 'LIVE' : 'SHADOW';
  const modeColor     = syntheticFeed ? 'var(--warning)' : 'var(--success)';

  const flaggedToday  = kpi.total_flagged_24h
    || ((kpi.action_tier_24h || 0) + (kpi.watchlist_tier_24h || 0))
    || 4442;
  const actionCount   = kpi.action_tier_24h || 1027;
  const scoreAvg      = kpi.action_score_avg_pct || 94.4;
  const recPerTrip    = kpi.estimated_recoverable_per_trip || 5.08;
  const annualCrore   = kpi.indicative_annual_recovery_crore || 6.87;

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
          SYNTHETIC DEMO DATA · PORTER INTELLIGENCE PLATFORM
        </span>
      </div>
    </div>
  );
}
