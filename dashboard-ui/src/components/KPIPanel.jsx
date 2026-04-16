import { useState, useEffect } from 'react';
import { apiGet } from '../utils/api';

function KPICard({ label, value, sub, color }) {
  return (
    <div className={`kpi-card ${color}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-sub">{sub}</div>
    </div>
  );
}

function formatPercent(value, available, digits = 1) {
  if (!available) return '--';
  return `${value.toFixed(digits)}%`;
}

export default function KPIPanel({ runtimeMeta = null }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);

  const fetchKpi = () => {
    apiGet('/kpi/live')
      .then(d => { setData(d); setLoading(false); setError(false); })
      .catch(() => { setError(true); setLoading(false); });
  };

  useEffect(() => {
    fetchKpi();
    const t = setInterval(fetchKpi, 30000);
    return () => clearInterval(t);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-label">Live Operations Signals</div>
        <div className="loading"><div className="spinner" /> Loading live data...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="section-label">Live Operations Signals</div>
        <div className="loading" style={{ color: 'var(--danger)' }}>Live KPI unavailable</div>
      </div>
    );
  }

  const reviewedCases = data.reviewed_cases_24h ?? 0;
  const reviewedMetricsLive = reviewedCases > 0;
  const reviewedPrecision = data.reviewed_case_precision_pct ?? 0;
  const reviewedFalseAlarmRate = (
    data.reviewed_false_alarm_rate_pct ?? 0
  );
  const confirmedRecoverable = (
    data.confirmed_recoverable_inr_24h ?? 0
  );
  const confirmedFraud = data.confirmed_fraud_24h ?? 0;
  const pendingReviewCases = data.pending_review_cases ?? 0;
  const actionCases = data.action_tier_24h ?? 0;
  const watchlistCases = data.watchlist_tier_24h ?? 0;
  const actionScoreAvg = data.action_score_avg_pct ?? 0;
  const netRecTrip = data.estimated_recoverable_per_trip ?? 0;
  const annualCrore = data.indicative_annual_recovery_crore ?? 0;
  const reviewConfidenceLabel = (
    data.review_confidence_label ?? 'Awaiting Analyst Reviews'
  );
  const reviewConfidenceNote = (
    data.review_confidence_note
    ?? 'Reviewed-case metrics will appear once analysts resolve cases.'
  );
  const reviewConfidenceStatus = (
    data.review_confidence_status ?? 'awaiting_reviews'
  );
  const runtimeMode = runtimeMeta?.runtime_mode
    ?? data.runtime_mode
    ?? 'unknown';
  const syntheticFeedEnabled = runtimeMeta?.synthetic_feed_enabled
    ?? data.synthetic_feed_enabled
    ?? false;
  const modeLabel = syntheticFeedEnabled
    ? 'DEMO MODE'
    : runtimeMode === 'prod'
      ? 'PRODUCTION MODE'
      : 'SHADOW MODE';
  const modeColor = syntheticFeedEnabled
    ? 'var(--warning)'
    : 'var(--success)';
  const provenance = runtimeMeta?.data_provenance
    ?? data.data_provenance
    ?? 'Database-backed operational records';
  const reviewStatusColor = {
    awaiting_reviews: 'var(--warning)',
    early_signal: 'var(--warning)',
    growing_sample: 'var(--orange)',
    decision_support: 'var(--success)',
  }[reviewConfidenceStatus] || 'var(--muted)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Operational Signal Window</div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 11, fontFamily: 'var(--font-mono)',
          color: modeColor, fontWeight: 700, letterSpacing: '0.08em',
        }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: modeColor,
            animation: syntheticFeedEnabled ? 'pulse-dot 2s infinite' : 'none',
          }} />
          {modeLabel}
        </div>
      </div>

      <div style={{
        background: syntheticFeedEnabled
          ? 'rgba(245,158,11,0.08)'
          : 'rgba(34,197,94,0.08)',
        border: `1px solid ${syntheticFeedEnabled ? 'rgba(245,158,11,0.25)' : 'rgba(34,197,94,0.22)'}`,
        borderRadius: 8,
        padding: '10px 12px',
      }}>
        <div style={{
          fontSize: 10,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: syntheticFeedEnabled ? 'var(--warning)' : 'var(--success)',
          marginBottom: 4,
        }}>
          Data Provenance
        </div>
        <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.55 }}>
          {provenance}
        </div>
        <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, lineHeight: 1.5 }}>
          Reviewed-case metrics below are the buyer-safe quality layer. Operational signal metrics remain visible as supplementary context only.
        </div>
      </div>

      <div style={{
        background: 'rgba(10,15,26,0.7)',
        border: '1px solid rgba(148,163,184,0.14)',
        borderRadius: 8,
        padding: '10px 12px',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div className="section-label" style={{ marginBottom: 0 }}>
            Reviewed Case Quality
          </div>
          <div style={{
            fontSize: 10,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: reviewStatusColor,
            fontWeight: 700,
          }}>
            {reviewConfidenceLabel}
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, lineHeight: 1.55 }}>
          {reviewConfidenceNote}
        </div>
      </div>

      <div style={{
        fontSize: 11,
        color: 'var(--muted)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        marginBottom: 12,
      }}>
        Trip Intelligence Layer &middot; Live from PostgreSQL &middot; Complements Incognia device controls
      </div>

      <div className="kpi-grid">
        <KPICard
          label="Reviewed Cases (24h)"
          value={reviewedCases}
          sub="resolved with analyst verdict"
          color="blue"
        />
        <KPICard
          label="Trip Score Precision"
          value={formatPercent(
            reviewedPrecision,
            reviewedMetricsLive,
          )}
          sub={reviewedMetricsLive
            ? 'confirmed fraud / reviewed cases'
            : 'awaiting analyst verdicts'}
          color="green"
        />
        <KPICard
          label="False Positive Rate"
          value={formatPercent(
            reviewedFalseAlarmRate,
            reviewedMetricsLive,
            2,
          )}
          sub={reviewedMetricsLive
            ? 'false alarms / reviewed cases'
            : 'awaiting analyst verdicts'}
          color="red"
        />
        <KPICard
          label="Pending Review"
          value={pendingReviewCases}
          sub="open + under review + escalated"
          color="orange"
        />
      </div>

      <div className="annual-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="annual-label">Leakage Recovered (Live)</div>
          <div className="annual-value">\u20B9{confirmedRecoverable.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="annual-label">Confirmed Fraud (24h)</div>
          <div className="annual-value" style={{ fontSize: 22 }}>{confirmedFraud}</div>
        </div>
      </div>

      <div className="comparison-card">
        <div className="section-label" style={{ marginBottom: 10 }}>
          Supplementary Signal Context
        </div>
        <div style={{ color: 'var(--text)', fontSize: 12, lineHeight: 1.8 }}>
          <div>
            Trip anomalies flagged: <strong>{actionCases}</strong> &middot; Watchlist: <strong>{watchlistCases}</strong> &middot; Trips scored today: <strong>{data.cases_today}</strong>
          </div>
          <div>
            Action score avg: <strong>{actionScoreAvg.toFixed(1)}%</strong> &middot; Net recovery per trip: <strong>\u20B9{netRecTrip.toFixed(2)}</strong> &middot; Indicative annual recovery: <strong>\u20B9{annualCrore.toFixed(1)} Crore</strong>
          </div>
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4, fontFamily: 'var(--font-mono)' }}>
          {data.all_time_cases} total cases in DB &middot; supplementary signal metrics help monitor live flow, but buyer decisions should rely on reviewed-case evidence above
        </div>
      </div>

    </div>
  );
}
