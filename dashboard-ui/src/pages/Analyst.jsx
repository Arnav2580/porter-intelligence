import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { apiGet, apiPatch, apiPost } from '../utils/api';
import { useAuth } from '../hooks/useAuth';

const ZONE_OPTIONS = [
  { id: 'blr_whitefield', name: 'Whitefield' },
  { id: 'blr_koramangala', name: 'Koramangala' },
  { id: 'blr_hsr', name: 'HSR Layout' },
  { id: 'blr_indiranagar', name: 'Indiranagar' },
  { id: 'blr_jayanagar', name: 'Jayanagar' },
  { id: 'blr_hebbal', name: 'Hebbal' },
  { id: 'blr_yeshwanthpur', name: 'Yeshwanthpur' },
  { id: 'blr_electronic_city', name: 'Electronic City' },
  { id: 'blr_bannerghatta', name: 'Bannerghatta Rd' },
  { id: 'blr_marathahalli', name: 'Marathahalli' },
  { id: 'blr_btm', name: 'BTM Layout' },
  { id: 'blr_rajajinagar', name: 'Rajajinagar' },
  { id: 'mum_andheri', name: 'Andheri' },
  { id: 'mum_bandra', name: 'Bandra' },
  { id: 'mum_worli', name: 'Worli' },
  { id: 'mum_kurla', name: 'Kurla' },
  { id: 'mum_thane', name: 'Thane' },
  { id: 'mum_navi_mumbai', name: 'Navi Mumbai' },
  { id: 'del_cp', name: 'Connaught Place' },
  { id: 'del_lajpat', name: 'Lajpat Nagar' },
  { id: 'del_dwarka', name: 'Dwarka' },
  { id: 'del_noida', name: 'Noida Sec-62' },
  { id: 'del_gurgaon', name: 'Gurgaon' },
  { id: 'del_rohini', name: 'Rohini' },
];

const CASE_ACTIONS = [
  { value: 'under_review', label: 'Mark Under Review', className: 'under-review' },
  { value: 'confirmed_fraud', label: 'Confirm Fraud', className: 'confirm-fraud' },
  { value: 'false_alarm', label: 'Mark False Alarm', className: 'false-alarm' },
  { value: 'escalated', label: 'Escalate', className: 'escalate' },
];

const DRIVER_ACTIONS = [
  { value: 'suspend', label: 'Suspend Driver' },
  { value: 'flag_review', label: 'Flag for Review' },
  { value: 'monitor', label: 'Monitor Driver' },
  { value: 'clear', label: 'Clear Driver' },
];

function relativeTime(isoStr) {
  if (!isoStr) return '--';
  const diff = Date.now() - new Date(isoStr).getTime();
  const seconds = Math.max(Math.floor(diff / 1000), 0);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatTimestamp(isoStr) {
  if (!isoStr) return '--';
  return new Date(isoStr).toLocaleString();
}

function formatStatus(value) {
  return (value || 'unknown').replace(/_/g, ' ');
}

function formatInr(value) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function zoneLabel(zid) {
  const zone = ZONE_OPTIONS.find((item) => item.id === zid);
  return zone ? zone.name : zid || 'Unknown';
}

function truncate(str, length) {
  if (!str) return '--';
  return str.length > length ? `${str.slice(0, length)}...` : str;
}

function probColor(probability) {
  if (probability > 0.94) return 'var(--danger)';
  if (probability > 0.45) return 'var(--warning)';
  return 'var(--success)';
}

function probClass(probability) {
  if (probability > 0.94) return 'high';
  if (probability > 0.45) return 'medium';
  return 'low';
}

function ageTone(hours) {
  if (hours >= 8) return 'critical';
  if (hours >= 2) return 'elevated';
  return 'healthy';
}

function scoreWeight(index) {
  const weights = [1, 0.82, 0.65, 0.52, 0.4];
  return weights[index] || 0.28;
}

function Header({
  activeTab,
  setActiveTab,
  user,
  runtimeMeta,
  resetState,
  onResetDemo,
  onLogout,
}) {
  const tabs = [
    { id: 'queue', label: 'Case Queue' },
    { id: 'detail', label: 'Case Detail' },
    { id: 'driver', label: 'Driver Profile' },
    { id: 'manager', label: 'Manager View' },
  ];
  const modeLabel = runtimeMeta?.synthetic_feed_enabled
    ? 'DEMO MODE'
    : runtimeMeta?.runtime_mode === 'prod'
      ? 'PRODUCTION MODE'
      : 'SHADOW MODE';
  const modeColor = runtimeMeta?.synthetic_feed_enabled
    ? 'var(--warning)'
    : 'var(--success)';
  const canResetDemo = (
    runtimeMeta?.runtime_mode !== 'prod'
    && ['admin', 'ops_manager'].includes(user.role)
  );

  return (
    <div className="header">
      <div className="header-logo">
        <Link to="/" style={{ textDecoration: 'none' }}>
          <div className="header-logo-mark">P</div>
        </Link>
        <div>
          <div className="header-title">Porter Intelligence</div>
          <div className="header-subtitle">Analyst Workstation</div>
        </div>
      </div>

      <div className="nav-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="header-right">
        {runtimeMeta ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, marginRight: 12 }}>
            <div className="live-badge" style={{ color: modeColor }}>
              <div className="live-dot" style={{ background: modeColor, animation: runtimeMeta.synthetic_feed_enabled ? 'pulse-dot 2s infinite' : 'none' }} />
              {modeLabel}
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted)', maxWidth: 220, textAlign: 'right', lineHeight: 1.4 }}>
              {runtimeMeta.data_provenance}
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted)', maxWidth: 220, textAlign: 'right', lineHeight: 1.4 }}>
              Mapping proof: <span style={{ color: 'var(--orange)' }}>/ingest/schema-map/default</span>
            </div>
          </div>
        ) : null}
        {canResetDemo ? (
          <button
            className="logout-btn"
            onClick={onResetDemo}
            disabled={resetState?.busy}
            style={{ marginRight: 12, opacity: resetState?.busy ? 0.75 : 1 }}
          >
            {resetState?.busy ? 'Resetting...' : 'Reset Demo'}
          </button>
        ) : null}
        <div className="user-info">
          <span className="user-name">{user.name}</span>
          <span className="role-badge">{formatStatus(user.role)}</span>
        </div>
        <button className="logout-btn" onClick={onLogout}>Logout</button>
      </div>
    </div>
  );
}

function QueueMetric({ label, value, tone = 'neutral', subtext }) {
  return (
    <div className={`queue-metric-card ${tone}`}>
      <div className="queue-metric-label">{label}</div>
      <div className="queue-metric-value">{value}</div>
      {subtext ? <div className="queue-metric-sub">{subtext}</div> : null}
    </div>
  );
}

function CaseCard({
  caseItem,
  selected,
  onToggleSelect,
  onOpen,
}) {
  const probability = caseItem.fraud_probability || 0;
  const signals = caseItem.top_signals || [];
  const ageHours = Number(caseItem.case_age_hours || 0);

  return (
    <div className="case-card" onClick={onOpen}>
      <div className="case-select-col" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelect(caseItem.id)}
          aria-label={`Select case ${caseItem.id}`}
        />
      </div>

      <div className="case-left">
        <span className={`tier-badge ${caseItem.tier}`}>{caseItem.tier}</span>
        <span className={`age-pill ${ageTone(ageHours)}`}>
          {ageHours.toFixed(1)}h old
        </span>
        {caseItem.auto_escalated ? (
          <span className="auto-escalate-icon" title="Auto-escalated">AUTO</span>
        ) : null}
      </div>

      <div className="case-center">
        <div className="case-trip-id">{truncate(caseItem.trip_id, 42)}</div>
        <div className="case-meta">
          Driver {truncate(caseItem.driver_id, 18)} / {zoneLabel(caseItem.zone_id)} / {relativeTime(caseItem.created_at)}
        </div>
        {signals.length > 0 ? (
          <div className="signal-chip-row">
            {signals.slice(0, 3).map((signal) => (
              <span key={signal} className="signal-chip">{signal}</span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="case-right">
        <div className="prob-bar-wrap">
          <div className="prob-bar-label">
            <span>Fraud probability</span>
            <span style={{ color: probColor(probability) }}>
              {(probability * 100).toFixed(1)}%
            </span>
          </div>
          <div className="prob-bar">
            <div
              className="prob-bar-fill"
              style={{
                width: `${probability * 100}%`,
                background: probColor(probability),
              }}
            />
          </div>
        </div>
        <div className="case-assignee">
          {caseItem.assigned_to ? `Assigned: ${caseItem.assigned_to}` : 'Unassigned'}
        </div>
        <span className={`status-badge ${caseItem.status}`}>{formatStatus(caseItem.status)}</span>
      </div>
    </div>
  );
}

function BulkReviewPanel({
  selectedCount,
  bulkStatus,
  setBulkStatus,
  bulkNotes,
  setBulkNotes,
  bulkOverrideReason,
  setBulkOverrideReason,
  requiresOverrideReason,
  onSubmit,
  submitting,
  onClearSelection,
}) {
  return (
    <div className="bulk-panel">
      <div className="bulk-panel-top">
        <div>
          <div className="bulk-panel-title">{selectedCount} cases selected</div>
          <div className="bulk-panel-sub">
            Apply the same analyst verdict to the selected queue slice.
          </div>
        </div>
        <button className="clear-btn" onClick={onClearSelection}>Clear selection</button>
      </div>

      <div className="bulk-panel-grid">
        <select
          className="filter-select"
          value={bulkStatus}
          onChange={(event) => setBulkStatus(event.target.value)}
        >
          <option value="">Select bulk action</option>
          {CASE_ACTIONS.map((action) => (
            <option key={action.value} value={action.value}>{action.label}</option>
          ))}
        </select>

        <textarea
          className="notes-textarea"
          value={bulkNotes}
          onChange={(event) => setBulkNotes(event.target.value)}
          placeholder="Batch review notes for the analyst trail..."
        />

        {requiresOverrideReason ? (
          <textarea
            className="reason-textarea"
            value={bulkOverrideReason}
            onChange={(event) => setBulkOverrideReason(event.target.value)}
            placeholder="Override reason is required for action-tier false alarms..."
          />
        ) : null}
      </div>

      <button
        className="submit-btn"
        onClick={onSubmit}
        disabled={!bulkStatus || submitting || (requiresOverrideReason && !bulkOverrideReason.trim())}
      >
        {submitting ? 'Applying review...' : 'Apply bulk review'}
      </button>
    </div>
  );
}

function CaseQueue({ onSelectCase }) {
  const [cases, setCases] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [flash, setFlash] = useState(null);
  const [filterTier, setFilterTier] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterZone, setFilterZone] = useState('');
  const [filterSearch, setFilterSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkStatus, setBulkStatus] = useState('');
  const [bulkNotes, setBulkNotes] = useState('');
  const [bulkOverrideReason, setBulkOverrideReason] = useState('');
  const [bulkSubmitting, setBulkSubmitting] = useState(false);

  const fetchCases = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterTier) params.set('tier', filterTier);
      if (filterStatus) params.set('status', filterStatus);
      if (filterZone) params.set('zone_id', filterZone);

      const [caseData, countData] = await Promise.all([
        apiGet(`/cases/?${params}`),
        apiGet('/cases/summary/counts').catch(() => ({})),
      ]);

      setCases(caseData.cases || []);
      setCounts(countData || {});
      setError('');
    } catch (fetchError) {
      setError(fetchError.message);
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterTier, filterZone]);

  useEffect(() => {
    setLoading(true);
    fetchCases();
    const timer = setInterval(fetchCases, 30000);
    return () => clearInterval(timer);
  }, [fetchCases]);

  useEffect(() => {
    setSelectedIds((current) => current.filter((id) => cases.some((caseItem) => caseItem.id === id)));
  }, [cases]);

  const displayed = useMemo(() => {
    if (!filterSearch.trim()) return cases;
    const query = filterSearch.trim().toLowerCase();
    return cases.filter((caseItem) => (
      (caseItem.trip_id || '').toLowerCase().includes(query)
      || (caseItem.driver_id || '').toLowerCase().includes(query)
      || (caseItem.assigned_to || '').toLowerCase().includes(query)
    ));
  }, [cases, filterSearch]);

  const selectedCases = useMemo(
    () => cases.filter((caseItem) => selectedIds.includes(caseItem.id)),
    [cases, selectedIds],
  );

  const requiresOverrideReason = (
    bulkStatus === 'false_alarm'
    && selectedCases.some((caseItem) => caseItem.tier === 'action')
  );

  const toggleSelection = (caseId) => {
    setSelectedIds((current) => (
      current.includes(caseId)
        ? current.filter((id) => id !== caseId)
        : [...current, caseId]
    ));
  };

  const toggleAllVisible = () => {
    const visibleIds = displayed.map((caseItem) => caseItem.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    if (allSelected) {
      setSelectedIds((current) => current.filter((id) => !visibleIds.includes(id)));
      return;
    }
    setSelectedIds((current) => Array.from(new Set([...current, ...visibleIds])));
  };

  const submitBulkReview = async () => {
    if (!bulkStatus || selectedIds.length === 0) return;
    setBulkSubmitting(true);
    try {
      const payload = await apiPost('/cases/batch-review', {
        case_ids: selectedIds,
        status: bulkStatus,
        analyst_notes: bulkNotes,
        override_reason: requiresOverrideReason ? bulkOverrideReason : undefined,
      });

      setFlash({
        type: 'success',
        msg: `Updated ${payload.updated_count} cases to ${formatStatus(payload.status)}.`,
      });
      setSelectedIds([]);
      setBulkStatus('');
      setBulkNotes('');
      setBulkOverrideReason('');
      await fetchCases();
    } catch (submitError) {
      setFlash({ type: 'error', msg: submitError.message });
    } finally {
      setBulkSubmitting(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Fraud Case Queue</div>
          <div className="page-subtitle">
            Action-tier and watchlist cases waiting for analyst judgement.
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="count-badges">
            <span className="count-badge open">{counts.open ?? '--'} Open</span>
            <span className="count-badge review">{counts.under_review ?? '--'} Under Review</span>
            <span className="count-badge escalated">{counts.escalated ?? '--'} Escalated</span>
          </div>
          <button className="refresh-btn" onClick={() => { setLoading(true); fetchCases(); }}>
            <span>R</span> Refresh
          </button>
        </div>
      </div>

      <div className="queue-metrics-grid">
        <QueueMetric label="Queue Size" value={cases.length} tone="neutral" subtext="Visible cases in current analyst scope" />
        <QueueMetric label="Selected" value={selectedIds.length} tone="warning" subtext="Ready for batch action" />
        <QueueMetric
          label="Oldest Pending"
          value={displayed.length ? `${Math.max(...displayed.map((caseItem) => caseItem.case_age_hours || 0)).toFixed(1)}h` : '0h'}
          tone="danger"
          subtext="Use this to keep SLAs honest"
        />
      </div>

      <div className="filter-bar">
        <button className="refresh-btn" onClick={toggleAllVisible}>
          {displayed.length > 0 && displayed.every((caseItem) => selectedIds.includes(caseItem.id))
            ? 'Clear visible'
            : 'Select visible'}
        </button>
        <select className="filter-select" value={filterTier} onChange={(event) => setFilterTier(event.target.value)}>
          <option value="">All tiers</option>
          <option value="action">Action</option>
          <option value="watchlist">Watchlist</option>
        </select>
        <select className="filter-select" value={filterStatus} onChange={(event) => setFilterStatus(event.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under Review</option>
          <option value="escalated">Escalated</option>
          <option value="confirmed_fraud">Confirmed Fraud</option>
          <option value="false_alarm">False Alarm</option>
        </select>
        <select className="filter-select" value={filterZone} onChange={(event) => setFilterZone(event.target.value)}>
          <option value="">All zones</option>
          {ZONE_OPTIONS.map((zone) => (
            <option key={zone.id} value={zone.id}>{zone.name}</option>
          ))}
        </select>
        <input
          className="filter-input"
          type="text"
          placeholder="Search trip / driver / analyst..."
          value={filterSearch}
          onChange={(event) => setFilterSearch(event.target.value)}
        />
      </div>

      {selectedIds.length > 0 ? (
        <BulkReviewPanel
          selectedCount={selectedIds.length}
          bulkStatus={bulkStatus}
          setBulkStatus={setBulkStatus}
          bulkNotes={bulkNotes}
          setBulkNotes={setBulkNotes}
          bulkOverrideReason={bulkOverrideReason}
          setBulkOverrideReason={setBulkOverrideReason}
          requiresOverrideReason={requiresOverrideReason}
          onSubmit={submitBulkReview}
          submitting={bulkSubmitting}
          onClearSelection={() => setSelectedIds([])}
        />
      ) : null}

      {flash ? <div className={`flash ${flash.type}`}>{flash.msg}</div> : null}
      {error ? <div className="error-banner"><span>!</span> {error}</div> : null}

      {loading ? (
        <div className="loading"><span className="spinner" /> Loading cases...</div>
      ) : displayed.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">[ ]</div>
          <div className="empty-state-title">No cases found.</div>
          <div className="empty-state-sub">Adjust the filters or wait for new flagged trips.</div>
        </div>
      ) : (
        <div className="case-list">
          {displayed.map((caseItem) => (
            <CaseCard
              key={caseItem.id}
              caseItem={caseItem}
              selected={selectedIds.includes(caseItem.id)}
              onToggleSelect={toggleSelection}
              onOpen={() => onSelectCase(caseItem)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RelatedCaseCard({ caseItem, onOpen }) {
  return (
    <button className="related-case-card" onClick={() => onOpen(caseItem)}>
      <div className="related-case-top">
        <span className={`tier-badge ${caseItem.tier}`}>{caseItem.tier}</span>
        <span className={`status-badge ${caseItem.status}`}>{formatStatus(caseItem.status)}</span>
      </div>
      <div className="related-case-id">{truncate(caseItem.trip_id, 22)}</div>
      <div className="related-case-meta">
        {zoneLabel(caseItem.zone_id)} / {(caseItem.fraud_probability * 100).toFixed(1)}%
      </div>
    </button>
  );
}

function Timeline({ history }) {
  if (!history.length) {
    return <div className="history-placeholder">No actions have been logged for this case yet.</div>;
  }

  return (
    <div className="timeline-list">
      {history.map((event) => (
        <div key={`${event.timestamp}-${event.category}-${event.title}`} className="timeline-item">
          <div className={`timeline-dot ${event.tone || 'neutral'}`} />
          <div className="timeline-body">
            <div className="timeline-top">
              <div className="timeline-title">{event.title}</div>
              <div className="timeline-time">{relativeTime(event.timestamp)}</div>
            </div>
            <div className="timeline-desc">{event.description}</div>
            <div className="timeline-meta">
              <span>{formatTimestamp(event.timestamp)}</span>
              {event.actor ? <span>by {event.actor}</span> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function DriverSnapshot({ profile, onOpenFullProfile }) {
  if (!profile) {
    return <div className="history-placeholder">Driver profile loading...</div>;
  }
  if (profile.error) {
    return <div className="flash error">{profile.error}</div>;
  }

  const recommendation = profile.recommendation || {};
  const ringInfo = profile.ring_intelligence || {};
  const peerMetrics = Object.entries(profile.peer_comparison?.metrics || {});

  return (
    <div className="driver-snapshot">
      <div className={`risk-level-header ${profile.risk_level}`}>
        <div>
          <div className={`risk-level-text ${profile.risk_level}`}>{profile.risk_level}</div>
          <div className="page-subtitle">Driver intelligence score</div>
        </div>
        <div className="risk-score-pct">{(profile.current_risk_score * 100).toFixed(1)}%</div>
      </div>

      <div className="detail-row">
        <span className="detail-row-label">Total Trips</span>
        <span className="detail-row-value">{profile.total_trips}</span>
      </div>
      <div className="detail-row">
        <span className="detail-row-label">Fraud Trips</span>
        <span className="detail-row-value">{profile.fraud_trips}</span>
      </div>
      <div className="detail-row">
        <span className="detail-row-label">Fraud Rate</span>
        <span className="detail-row-value">{(profile.fraud_rate * 100).toFixed(1)}%</span>
      </div>

      {recommendation.action ? (
        <div className="recommendation-box">
          <div className="recommendation-title">{recommendation.action}</div>
          <div className="recommendation-copy">{recommendation.reason}</div>
        </div>
      ) : null}

      {ringInfo.is_ring_member ? (
        <div className="signal-item">
          <span className="signal-arrow">-&gt;</span>
          <div>
            Ring {truncate(ringInfo.ring_id, 10)} / {ringInfo.ring_role} / {ringInfo.ring_size} members
          </div>
        </div>
      ) : ringInfo.suspected_ring ? (
        <div className="signal-item">
          <span className="signal-arrow">-&gt;</span>
          <div>Behaviour pattern suggests possible undiscovered ring coordination.</div>
        </div>
      ) : null}

      {peerMetrics.length > 0 ? (
        <div className="mini-metric-list">
          {peerMetrics.slice(0, 4).map(([metric, values]) => (
            <div key={metric} className="mini-metric-row">
              <span>{metric.replace(/_/g, ' ')}</span>
              <span className={values.flag ? 'text-danger' : ''}>{values.percentile.toFixed(0)}th pct</span>
            </div>
          ))}
        </div>
      ) : null}

      <button className="load-btn" style={{ marginTop: 12 }} onClick={onOpenFullProfile}>
        Open full driver profile
      </button>
    </div>
  );
}

function CaseDetail({ selectedCase, onBack, onOpenDriver, onOpenCase }) {
  const [caseData, setCaseData] = useState(selectedCase);
  const [history, setHistory] = useState([]);
  const [driverProfile, setDriverProfile] = useState(null);
  const [relatedCases, setRelatedCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [flash, setFlash] = useState(null);
  const [driverAction, setDriverAction] = useState('');
  const [driverReason, setDriverReason] = useState('');
  const [driverSubmitting, setDriverSubmitting] = useState(false);
  const [driverFlash, setDriverFlash] = useState(null);

  const loadDetail = useCallback(async () => {
    if (!selectedCase?.id) return;

    setLoading(true);
    setError('');
    try {
      const detailPromise = apiGet(`/cases/${selectedCase.id}`);
      const historyPromise = apiGet(`/cases/${selectedCase.id}/history`).catch(() => ({ history: [] }));
      const relatedPromise = apiGet(
        `/cases/?tier=${encodeURIComponent(selectedCase.tier)}&zone_id=${encodeURIComponent(selectedCase.zone_id)}&limit=6`,
      ).catch(() => ({ cases: [] }));
      const driverPromise = selectedCase.driver_id
        ? apiGet(`/intelligence/driver/${encodeURIComponent(selectedCase.driver_id)}`).catch((driverError) => ({
          error: driverError.message,
        }))
        : Promise.resolve(null);

      const [detail, historyPayload, relatedPayload, driverPayload] = await Promise.all([
        detailPromise,
        historyPromise,
        relatedPromise,
        driverPromise,
      ]);

      setCaseData(detail);
      setHistory(historyPayload.history || []);
      setDriverProfile(driverPayload);
      setRelatedCases(
        (relatedPayload.cases || []).filter((caseItem) => caseItem.id !== selectedCase.id).slice(0, 3),
      );
      setNotes(detail.analyst_notes || '');
      setOverrideReason(detail.override_reason || '');
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [selectedCase]);

  useEffect(() => {
    setCaseData(selectedCase);
    setStatus('');
    setFlash(null);
    setDriverFlash(null);
    loadDetail();
  }, [loadDetail, selectedCase]);

  if (!selectedCase) {
    return (
      <div className="empty-state">
          <div className="empty-state-icon">[?]</div>
        <div className="empty-state-title">Select a case from the queue.</div>
        <div className="empty-state-sub">The detail workspace unlocks once a case is opened.</div>
      </div>
    );
  }

  if (!caseData) {
    return <div className="loading"><span className="spinner" /> Loading case...</div>;
  }

  const probability = caseData.fraud_probability || 0;
  const statusNeedsOverride = caseData.tier === 'action' && status === 'false_alarm';

  const submitStatus = async () => {
    if (!status) return;
    setSubmitting(true);
    try {
      await apiPatch(`/cases/${caseData.id}`, {
        status,
        analyst_notes: notes,
        override_reason: statusNeedsOverride ? overrideReason : undefined,
      });
      setFlash({ type: 'success', msg: 'Case status updated and audit trail recorded.' });
      setStatus('');
      await loadDetail();
    } catch (submitError) {
      setFlash({ type: 'error', msg: submitError.message });
    } finally {
      setSubmitting(false);
    }
  };

  const submitDriverAction = async () => {
    if (!driverAction || !driverReason.trim()) return;
    setDriverSubmitting(true);
    try {
      await apiPost(`/cases/${caseData.id}/driver-action`, {
        action_type: driverAction,
        reason: driverReason,
      });
      setDriverFlash({ type: 'success', msg: 'Driver action recorded in the case trail.' });
      setDriverAction('');
      setDriverReason('');
      await loadDetail();
    } catch (submitError) {
      setDriverFlash({ type: 'error', msg: submitError.message });
    } finally {
      setDriverSubmitting(false);
    }
  };

  return (
    <div className="fade-in">
      <div className="breadcrumb">
        <span className="breadcrumb-link" onClick={onBack}>Case Queue</span>
        <span>&gt;</span>
        <span>Case {caseData.id}</span>
      </div>

      {error ? <div className="error-banner"><span>!</span> {error}</div> : null}
      {loading ? <div className="loading"><span className="spinner" /> Refreshing case workspace...</div> : null}

      <div className="detail-header">
        <div className="detail-header-left">
          <div className="detail-case-id">Case ID: {caseData.id}</div>
          <div className="detail-badges">
            <span className={`tier-badge ${caseData.tier}`}>{caseData.tier}</span>
            <span className={`status-badge ${caseData.status}`}>{formatStatus(caseData.status)}</span>
            <span className={`age-pill ${ageTone(caseData.case_age_hours || 0)}`}>
              {(caseData.case_age_hours || 0).toFixed(1)}h open
            </span>
          </div>
          <div className="detail-timestamp">
            Created {formatTimestamp(caseData.created_at)} / Last seen {relativeTime(caseData.created_at)}
          </div>
        </div>
        <div className="detail-prob-wrap">
          <div className={`detail-prob-number ${probClass(probability)}`}>{(probability * 100).toFixed(1)}%</div>
          <div className="detail-prob-label">Fraud probability</div>
        </div>
      </div>

      <div className="detail-cols">
        <div>
          <div className="detail-section">
            <div className="detail-section-title">Trip & Queue Context</div>
            <div className="detail-row"><span className="detail-row-label">Trip ID</span><span className="detail-row-value">{caseData.trip_id}</span></div>
            <div className="detail-row"><span className="detail-row-label">Driver ID</span><span className="detail-row-value">{caseData.driver_id}</span></div>
            <div className="detail-row"><span className="detail-row-label">Zone</span><span className="detail-row-value">{zoneLabel(caseData.zone_id)}</span></div>
            <div className="detail-row"><span className="detail-row-label">City</span><span className="detail-row-value">{caseData.city || 'Unknown'}</span></div>
            <div className="detail-row"><span className="detail-row-label">Fare</span><span className="detail-row-value">{formatInr(caseData.fare_inr)}</span></div>
            <div className="detail-row"><span className="detail-row-label">Recoverable estimate</span><span className="detail-row-value">{formatInr(caseData.recoverable_inr)}</span></div>
            <div className="detail-row"><span className="detail-row-label">Assigned analyst</span><span className="detail-row-value">{caseData.assigned_to || 'Unassigned'}</span></div>
            <div className="detail-row"><span className="detail-row-label">Override reason</span><span className="detail-row-value">{caseData.override_reason || 'Not supplied'}</span></div>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Model Explanation</div>
            <div className="prob-gauge">
              <div className="prob-bar-label">
                <span>Confidence ladder</span>
                <span style={{ color: probColor(probability) }}>{(probability * 100).toFixed(1)}%</span>
              </div>
              <div className="prob-gauge-bar">
                <div
                  className="prob-gauge-fill"
                  style={{
                    width: `${probability * 100}%`,
                    background: probColor(probability),
                  }}
                />
              </div>
              <div className="prob-gauge-labels">
                <span>0%</span>
                <span>Watchlist 45%</span>
                <span>Action 94%</span>
              </div>
            </div>

            <div className="signal-list">
              {(caseData.top_signals || []).length > 0 ? (
                caseData.top_signals.slice(0, 5).map((signal, index) => (
                  <div key={signal} className="explanation-row">
                    <div className="explanation-copy">
                      <span className="signal-arrow">-&gt;</span>
                      <span>{signal}</span>
                    </div>
                    <div className="explanation-bar">
                      <div
                        className="explanation-bar-fill"
                        style={{ width: `${scoreWeight(index) * 100}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="history-placeholder">No model signals available for this case.</div>
              )}
            </div>

            <div className="subsection-label">Similar recent cases</div>
            {relatedCases.length > 0 ? (
              <div className="related-case-grid">
                {relatedCases.map((relatedCase) => (
                  <RelatedCaseCard key={relatedCase.id} caseItem={relatedCase} onOpen={onOpenCase} />
                ))}
              </div>
            ) : (
              <div className="history-placeholder">
                No comparable cases found yet for this tier and zone slice.
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="detail-section">
            <div className="detail-section-title">Case Action</div>
            <div className="action-btn-group">
              {CASE_ACTIONS.map((action) => (
                <button
                  key={action.value}
                  className={`action-btn ${action.className} ${status === action.value ? 'selected' : ''}`}
                  onClick={() => setStatus(action.value)}
                >
                  {action.label}
                </button>
              ))}
            </div>

            <textarea
              className="notes-textarea"
              placeholder="Analyst notes, investigation context, or case rationale..."
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />

            {statusNeedsOverride ? (
              <textarea
                className="reason-textarea"
                placeholder="Override reason is required for action-tier false alarms..."
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            ) : null}

            <button
              className="submit-btn"
              onClick={submitStatus}
              disabled={!status || submitting || (statusNeedsOverride && !overrideReason.trim())}
            >
              {submitting ? 'Updating case...' : 'Update case'}
            </button>
            {flash ? <div className={`flash ${flash.type}`}>{flash.msg}</div> : null}
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Driver Action</div>
            <div className="action-btn-group">
              {DRIVER_ACTIONS.map((action) => (
                <button
                  key={action.value}
                  className={`driver-action-btn ${driverAction === action.value ? 'selected' : ''}`}
                  onClick={() => setDriverAction(action.value)}
                >
                  {action.label}
                </button>
              ))}
            </div>

            <textarea
              className="reason-textarea"
              placeholder="Operational reason for the driver action..."
              value={driverReason}
              onChange={(event) => setDriverReason(event.target.value)}
            />
            <button
              className="submit-btn"
              onClick={submitDriverAction}
              disabled={!driverAction || !driverReason.trim() || driverSubmitting}
            >
              {driverSubmitting ? 'Recording action...' : 'Record driver action'}
            </button>
            {driverFlash ? <div className={`flash ${driverFlash.type}`}>{driverFlash.msg}</div> : null}
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Driver Intelligence Snapshot</div>
            <DriverSnapshot
              profile={driverProfile}
              onOpenFullProfile={() => onOpenDriver(caseData.driver_id)}
            />
          </div>
        </div>
      </div>

      <div className="detail-section">
        <div className="detail-section-title">Case History</div>
        <Timeline history={history} />
      </div>
    </div>
  );
}

function DriverProfile({ initialDriverId }) {
  const [driverId, setDriverId] = useState(initialDriverId || '');
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadProfile = useCallback(async (idToLoad) => {
    if (!idToLoad) return;
    setLoading(true);
    try {
      const payload = await apiGet(`/intelligence/driver/${encodeURIComponent(idToLoad.trim())}`);
      setProfile(payload);
    } catch (loadError) {
      setProfile({ error: loadError.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialDriverId) {
      setDriverId(initialDriverId);
      loadProfile(initialDriverId);
    }
  }, [initialDriverId, loadProfile]);

  const peerMetrics = Object.entries(profile?.peer_comparison?.metrics || {});

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Driver Profile</div>
          <div className="page-subtitle">Review a driver outside the case queue.</div>
        </div>
      </div>

      <div className="driver-search-bar">
        <input
          className="driver-id-input"
          value={driverId}
          onChange={(event) => setDriverId(event.target.value)}
          placeholder="Enter driver ID..."
        />
        <button className="load-btn" onClick={() => loadProfile(driverId)} disabled={!driverId.trim() || loading}>
          {loading ? 'Loading...' : 'Load profile'}
        </button>
      </div>

      {profile ? (
        profile.error ? (
          <div className="flash error">{profile.error}</div>
        ) : (
          <>
            <div className={`risk-level-header ${profile.risk_level}`}>
              <div>
                <div className={`risk-level-text ${profile.risk_level}`}>{profile.risk_level}</div>
                <div className="page-subtitle">Risk profile for {profile.driver_id}</div>
              </div>
              <div className="risk-score-pct">{(profile.current_risk_score * 100).toFixed(1)}%</div>
            </div>

            <div className="detail-cols">
              <div>
                <div className="detail-section">
                  <div className="detail-section-title">Driver Summary</div>
                  <div className="detail-row"><span className="detail-row-label">Total trips</span><span className="detail-row-value">{profile.total_trips}</span></div>
                  <div className="detail-row"><span className="detail-row-label">Fraud trips</span><span className="detail-row-value">{profile.fraud_trips}</span></div>
                  <div className="detail-row"><span className="detail-row-label">Fraud rate</span><span className="detail-row-value">{(profile.fraud_rate * 100).toFixed(1)}%</span></div>
                  {profile.recommendation ? (
                    <div className="recommendation-box">
                      <div className="recommendation-title">
                        {profile.recommendation.action} / {profile.recommendation.priority}
                      </div>
                      <div className="recommendation-copy">{profile.recommendation.reason}</div>
                    </div>
                  ) : null}
                </div>

                <div className="detail-section">
                  <div className="detail-section-title">Ring Intelligence</div>
                  {profile.ring_intelligence?.is_ring_member ? (
                    <>
                      <div className="detail-row"><span className="detail-row-label">Ring ID</span><span className="detail-row-value">{truncate(profile.ring_intelligence.ring_id, 12)}</span></div>
                      <div className="detail-row"><span className="detail-row-label">Role</span><span className="detail-row-value">{profile.ring_intelligence.ring_role}</span></div>
                      <div className="detail-row"><span className="detail-row-label">Members</span><span className="detail-row-value">{profile.ring_intelligence.ring_size}</span></div>
                      <div className="detail-row"><span className="detail-row-label">Zone</span><span className="detail-row-value">{profile.ring_intelligence.ring_zone_name}</span></div>
                    </>
                  ) : profile.ring_intelligence?.suspected_ring ? (
                    <div className="signal-item">
                      <span className="signal-arrow">-&gt;</span>
                      <div>This driver is not mapped to a known ring yet, but the pattern looks coordinated.</div>
                    </div>
                  ) : (
                    <div className="history-placeholder">No known ring membership detected.</div>
                  )}
                </div>
              </div>

              <div>
                <div className="detail-section">
                  <div className="detail-section-title">Peer Comparison</div>
                  {peerMetrics.length > 0 ? (
                    peerMetrics.map(([metric, values]) => (
                      <div key={metric} className="mini-metric-row">
                        <span>{metric.replace(/_/g, ' ')}</span>
                        <span className={values.flag ? 'text-danger' : ''}>
                          {values.percentile.toFixed(0)}th percentile
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="history-placeholder">Peer comparison is not available for this driver yet.</div>
                  )}
                </div>

                <div className="detail-section">
                  <div className="detail-section-title">30-Day Risk Trend</div>
                  {profile.timeline?.length > 0 ? (
                    <div className="timeline-bars">
                      {profile.timeline.slice(-14).map((day) => (
                        <div key={day.date} className="timeline-bar-col" title={`${day.date}: ${(day.risk_score * 100).toFixed(1)}%`}>
                          <div
                            className={`timeline-bar-fill ${day.risk_level.toLowerCase()}`}
                            style={{ height: `${Math.max(day.risk_score * 100, 6)}%` }}
                          />
                          <span>{day.date.slice(5)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="history-placeholder">No historical trend is available for this driver yet.</div>
                  )}
                </div>
              </div>
            </div>
          </>
        )
      ) : (
        <div className="empty-state">
          <div className="empty-state-icon">ID</div>
          <div className="empty-state-title">Load a driver profile to inspect risk and ring behaviour.</div>
        </div>
      )}
    </div>
  );
}

function ManagerView() {
  const [summary, setSummary] = useState(null);
  const [liveKpi, setLiveKpi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadManagerView = useCallback(async () => {
    try {
      const [dashboardSummary, livePayload] = await Promise.all([
        apiGet('/cases/summary/dashboard'),
        apiGet('/kpi/live'),
      ]);
      setSummary(dashboardSummary);
      setLiveKpi(livePayload);
      setError('');
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadManagerView();
  }, [loadManagerView]);

  if (loading) {
    return <div className="loading"><span className="spinner" /> Loading manager summary...</div>;
  }

  if (error) {
    return <div className="error-banner"><span>!</span> {error}</div>;
  }

  const queue = summary?.queue || {};
  const throughput = summary?.throughput_24h || {};
  const trend = summary?.precision_trend_7d || [];

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <div className="page-title">Manager View</div>
          <div className="page-subtitle">
            Daily operating picture for analyst load, review quality, and city pressure.
          </div>
        </div>
        <button className="refresh-btn" onClick={loadManagerView}>R Refresh summary</button>
      </div>

      <div className="manager-grid">
        <QueueMetric label="Open Queue" value={queue.open_cases ?? 0} tone="neutral" subtext="Cases awaiting first analyst decision" />
        <QueueMetric label="Reviewed 24h" value={throughput.reviewed_cases ?? 0} tone="warning" subtext="Confirmed + false alarm outcomes" />
        <QueueMetric label="Precision 24h" value={`${((throughput.reviewed_case_precision || 0) * 100).toFixed(1)}%`} tone="success" subtext="Reviewed-case precision only" />
        <QueueMetric label="Confirmed Recovery" value={formatInr(liveKpi?.confirmed_recoverable_inr_24h)} tone="danger" subtext={liveKpi?.review_confidence_label || 'Awaiting review depth'} />
      </div>

      <div className="detail-cols">
        <div>
          <div className="detail-section">
            <div className="detail-section-title">Queue Pressure</div>
            <div className="detail-row"><span className="detail-row-label">Average pending age</span><span className="detail-row-value">{(queue.avg_pending_hours || 0).toFixed(2)}h</span></div>
            <div className="detail-row"><span className="detail-row-label">Oldest pending case</span><span className="detail-row-value">{(queue.oldest_pending_hours || 0).toFixed(2)}h</span></div>
            <div className="detail-row"><span className="detail-row-label">Cases older than 2h</span><span className="detail-row-value">{queue.cases_older_than_2h || 0}</span></div>
            <div className="detail-row"><span className="detail-row-label">Confirmed cases</span><span className="detail-row-value">{queue.confirmed_cases || 0}</span></div>
            <div className="detail-row"><span className="detail-row-label">False alarms</span><span className="detail-row-value">{queue.false_alarm_cases || 0}</span></div>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Precision Trend</div>
            <div className="trend-list">
              {trend.map((point) => (
                <div key={point.date} className="trend-row">
                  <span>{point.date}</span>
                  <span>{point.reviewed_cases} reviews</span>
                  <strong>{(point.reviewed_case_precision * 100).toFixed(1)}%</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="detail-section">
            <div className="detail-section-title">City Breakdown</div>
            <div className="trend-list">
              {(summary?.city_breakdown || []).map((cityItem) => (
                <div key={cityItem.city} className="trend-row">
                  <span>{cityItem.city}</span>
                  <span>{cityItem.total_cases} queued</span>
                  <strong>{cityItem.action_cases} action</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Analyst Load</div>
            <div className="trend-list">
              {(summary?.analyst_load || []).map((analystItem) => (
                <div key={analystItem.analyst} className="trend-row">
                  <span>{analystItem.analyst}</span>
                  <span>{analystItem.assigned_cases} assigned</span>
                  <strong>{analystItem.under_review_cases} in review</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Analyst() {
  const { auth, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('queue');
  const [selectedCase, setSelectedCase] = useState(null);
  const [selectedDriverId, setSelectedDriverId] = useState('');
  const [runtimeMeta, setRuntimeMeta] = useState(null);
  const [resetState, setResetState] = useState({ busy: false, message: '', tone: 'success' });

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const health = await apiGet('/health');
        setRuntimeMeta(health);
      } catch (_error) {
        setRuntimeMeta(null);
      }
    };
    fetchHealth();
    const timer = setInterval(fetchHealth, 30000);
    return () => clearInterval(timer);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleResetDemo = async () => {
    setResetState({ busy: true, message: '', tone: 'success' });
    try {
      const response = await apiPost('/demo/reset', {});
      setSelectedCase(null);
      setSelectedDriverId('');
      setActiveTab('queue');
      setResetState({
        busy: false,
        message: `Workspace reset. Cleared ${Object.values(response.deleted || {}).reduce((sum, count) => sum + count, 0)} records.`,
        tone: 'success',
      });
    } catch (error) {
      setResetState({
        busy: false,
        message: error.message || 'Demo reset failed.',
        tone: 'error',
      });
    }
  };

  const openCase = (caseItem) => {
    setSelectedCase(caseItem);
    setSelectedDriverId(caseItem.driver_id || '');
    setActiveTab('detail');
  };

  const openDriver = (driverId) => {
    setSelectedDriverId(driverId || '');
    setActiveTab('driver');
  };

  return (
    <>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={auth || { name: 'Analyst', role: 'ops_analyst' }}
        runtimeMeta={runtimeMeta}
        resetState={resetState}
        onResetDemo={handleResetDemo}
        onLogout={handleLogout}
      />

      {resetState.message ? (
        <div className={`flash ${resetState.tone}`} style={{ margin: '16px 24px 0' }}>
          {resetState.message}
        </div>
      ) : null}

      <div className="main-content">
        {activeTab === 'queue' ? <CaseQueue onSelectCase={openCase} /> : null}
        {activeTab === 'detail' ? (
          <CaseDetail
            selectedCase={selectedCase}
            onBack={() => setActiveTab('queue')}
            onOpenDriver={openDriver}
            onOpenCase={openCase}
          />
        ) : null}
        {activeTab === 'driver' ? <DriverProfile initialDriverId={selectedDriverId} /> : null}
        {activeTab === 'manager' ? <ManagerView /> : null}
      </div>
    </>
  );
}
