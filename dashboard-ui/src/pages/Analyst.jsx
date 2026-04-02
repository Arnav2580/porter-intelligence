import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet, apiPatch, apiPost } from '../utils/api';
import { useAuth } from '../hooks/useAuth';
import { useNavigate, Link } from 'react-router-dom';

const ZONE_OPTIONS = [
  { id: 'blr_whitefield',      name: 'Whitefield' },
  { id: 'blr_koramangala',     name: 'Koramangala' },
  { id: 'blr_hsr',             name: 'HSR Layout' },
  { id: 'blr_indiranagar',     name: 'Indiranagar' },
  { id: 'blr_jayanagar',       name: 'Jayanagar' },
  { id: 'blr_hebbal',          name: 'Hebbal' },
  { id: 'blr_yeshwanthpur',    name: 'Yeshwanthpur' },
  { id: 'blr_electronic_city', name: 'Electronic City' },
  { id: 'blr_bannerghatta',    name: 'Bannerghatta Rd' },
  { id: 'blr_marathahalli',    name: 'Marathahalli' },
  { id: 'blr_btm',             name: 'BTM Layout' },
  { id: 'blr_rajajinagar',     name: 'Rajajinagar' },
  { id: 'mum_andheri',         name: 'Andheri' },
  { id: 'mum_bandra',          name: 'Bandra' },
  { id: 'mum_worli',           name: 'Worli' },
  { id: 'mum_kurla',           name: 'Kurla' },
  { id: 'mum_thane',           name: 'Thane' },
  { id: 'mum_navi_mumbai',     name: 'Navi Mumbai' },
  { id: 'del_cp',              name: 'Connaught Place' },
  { id: 'del_lajpat',          name: 'Lajpat Nagar' },
  { id: 'del_dwarka',          name: 'Dwarka' },
  { id: 'del_noida',           name: 'Noida Sec-62' },
  { id: 'del_gurgaon',         name: 'Gurgaon' },
  { id: 'del_rohini',          name: 'Rohini' },
];

function relativeTime(isoStr) {
  if (!isoStr) return '—';
  const diff = Date.now() - new Date(isoStr).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function probColor(p) {
  if (p > 0.94) return 'var(--danger)';
  if (p > 0.45) return 'var(--warning)';
  return 'var(--success)';
}

function probClass(p) {
  if (p > 0.94) return 'high';
  if (p > 0.45) return 'medium';
  return 'low';
}

function truncate(str, n) {
  if (!str) return '—';
  return str.length > n ? str.slice(0, n) + '…' : str;
}

function zoneLabel(zid) {
  const z = ZONE_OPTIONS.find(z => z.id === zid);
  return z ? z.name : zid;
}

function Header({ activeTab, setActiveTab, user, onLogout }) {
  const TABS = [
    { id: 'queue',   label: 'Case Queue' },
    { id: 'detail',  label: 'Case Detail' },
    { id: 'driver',  label: 'Driver Profile' },
  ];

  return (
    <div className="header">
      <div className="header-logo">
        <Link to="/" style={{ textDecoration: 'none' }}><div className="header-logo-mark">P</div></Link>
        <div>
          <div className="header-title">Porter Intelligence</div>
          <div className="header-subtitle">Analyst Workstation</div>
        </div>
      </div>

      <div className="nav-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`nav-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="header-right">
        <div className="user-info">
          <span className="user-name">{user.name}</span>
          <span className="role-badge">{user.role?.replace(/_/g, ' ')}</span>
        </div>
        <button className="logout-btn" onClick={onLogout}>Logout</button>
      </div>
    </div>
  );
}

function CaseCard({ caseItem: c, onClick }) {
  const prob = c.fraud_probability || 0;
  const signals = c.top_signals || [];
  return (
    <div className="case-card" onClick={onClick}>
      <div className="case-left">
        <span className={`tier-badge ${c.tier}`}>{c.tier}</span>
        {c.auto_escalated && (
          <span className="auto-escalate-icon" title="Auto-escalated">⚡</span>
        )}
      </div>
      <div className="case-center">
        <div className="case-trip-id">{truncate(c.trip_id, 36)}</div>
        <div className="case-meta">
          Driver: {truncate(c.driver_id, 20)} &nbsp;·&nbsp; {zoneLabel(c.zone_id)} &nbsp;·&nbsp; {relativeTime(c.created_at)}
        </div>
      </div>
      <div className="case-right">
        <div className="prob-bar-wrap">
          <div className="prob-bar-label">
            <span>Fraud probability</span>
            <span style={{ color: probColor(prob) }}>{(prob * 100).toFixed(1)}%</span>
          </div>
          <div className="prob-bar">
            <div
              className="prob-bar-fill"
              style={{ width: `${prob * 100}%`, background: probColor(prob) }}
            />
          </div>
        </div>
        {signals[0] && (
          <div className="signal-text" title={signals[0]}>{signals[0]}</div>
        )}
        <span className={`status-badge ${c.status}`}>{c.status.replace(/_/g, ' ')}</span>
      </div>
    </div>
  );
}

function CaseQueue({ onSelectCase }) {
  const [cases,     setCases]     = useState([]);
  const [counts,    setCounts]    = useState({});
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');
  const [filterTier,    setFilterTier]    = useState('');
  const [filterStatus,  setFilterStatus]  = useState('');
  const [filterZone,    setFilterZone]    = useState('');
  const [filterSearch,  setFilterSearch]  = useState('');
  const refreshRef = useRef(null);

  const fetchCases = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterTier)   params.set('tier',    filterTier);
      if (filterStatus) params.set('status',  filterStatus);
      if (filterZone)   params.set('zone_id', filterZone);

      const [data, countData] = await Promise.all([
        apiGet(`/cases/?${params}`),
        apiGet('/cases/summary/counts').catch(() => ({})),
      ]);
      setCases(data.cases || []);
      setCounts(countData || {});
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filterTier, filterStatus, filterZone]);

  useEffect(() => {
    setLoading(true);
    fetchCases();
    refreshRef.current = setInterval(fetchCases, 30000);
    return () => clearInterval(refreshRef.current);
  }, [fetchCases]);

  const displayed = cases.filter(c => {
    if (!filterSearch) return true;
    const q = filterSearch.toLowerCase();
    return (
      (c.trip_id   || '').toLowerCase().includes(q) ||
      (c.driver_id || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="fade-in">
      <div className="page-header">
        <div><div className="page-title">Fraud Case Queue</div></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="count-badges">
            <span className="count-badge open">{counts.open ?? '—'} Open</span>
            <span className="count-badge review">{counts.under_review ?? '—'} Under Review</span>
            <span className="count-badge escalated">{counts.escalated ?? '—'} Escalated</span>
          </div>
          <button className="refresh-btn" onClick={() => { setLoading(true); fetchCases(); }}>
            <span>↻</span> Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar">
        <select className="filter-select" value={filterTier} onChange={e => setFilterTier(e.target.value)}>
          <option value="">All Tiers</option><option value="action">Action</option><option value="watchlist">Watchlist</option>
        </select>
        <select className="filter-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">All Status</option><option value="open">Open</option><option value="under_review">Under Review</option><option value="escalated">Escalated</option>
        </select>
        <select className="filter-select" value={filterZone} onChange={e => setFilterZone(e.target.value)}>
          <option value="">All Zones</option>
          {ZONE_OPTIONS.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}
        </select>
        <input className="filter-input" type="text" placeholder="Search ID…" value={filterSearch} onChange={e => setFilterSearch(e.target.value)} />
      </div>

      {error && <div className="error-banner"><span>⚠</span> {error}</div>}

      {loading ? (
        <div className="loading"><span className="spinner" /> Loading cases…</div>
      ) : displayed.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📭</div>
          <div className="empty-state-title">No cases found.</div>
        </div>
      ) : (
        <div className="case-list">
          {displayed.map(c => <CaseCard key={c.id} caseItem={c} onClick={() => onSelectCase(c)} />)}
        </div>
      )}
    </div>
  );
}

function CaseDetail({ selectedCase, onBack }) {
  const [caseData,   setCaseData]   = useState(selectedCase);
  const [status,     setStatus]     = useState('');
  const [notes,      setNotes]      = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [flash,      setFlash]      = useState(null);
  const [drvAction,  setDrvAction]  = useState('');
  const [drvReason,  setDrvReason]  = useState('');
  const [drvSubmit,  setDrvSubmit]  = useState(false);
  const [drvFlash,   setDrvFlash]   = useState(null);

  if (!caseData) return <div className="loading">No case selected</div>;

  const prob = caseData.fraud_probability || 0;
  const signals = caseData.top_signals || [];

  const submitStatus = async () => {
    if (!status) return;
    setSubmitting(true);
    try {
      const updated = await apiPatch(`/cases/${caseData.id}`, { status, analyst_notes: notes });
      setCaseData(updated);
      setFlash({ type: 'success', msg: 'Case updated successfully.' });
      setStatus(''); setNotes('');
    } catch (err) {
      setFlash({ type: 'error', msg: err.message });
    } finally { setSubmitting(false); }
  };

  const submitDriverAction = async () => {
    if (!drvAction || !drvReason.trim()) return;
    setDrvSubmit(true);
    try {
      await apiPost(`/cases/${caseData.id}/driver-action`, { action_type: drvAction, reason: drvReason });
      setDrvFlash({ type: 'success', msg: `Driver action recorded.` });
      setDrvAction(''); setDrvReason('');
    } catch (err) {
      setDrvFlash({ type: 'error', msg: err.message });
    } finally { setDrvSubmit(false); }
  };

  return (
    <div className="fade-in">
      <div className="breadcrumb">
        <span className="breadcrumb-link" onClick={onBack}>Case Queue</span> › <span>Case {caseData.id}</span>
      </div>
      <div className="detail-header">
        <div className="detail-header-left">
          <div className="detail-case-id">Case ID: {caseData.id}</div>
          <div className="detail-badges">
            <span className={`tier-badge ${caseData.tier}`}>{caseData.tier}</span>
            <span className={`status-badge ${caseData.status}`}>{caseData.status.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <div className="detail-prob-wrap">
          <div className={`detail-prob-number ${probClass(prob)}`}>{(prob * 100).toFixed(1)}%</div>
        </div>
      </div>
      <div className="detail-cols">
        <div>
          <div className="detail-section">
            <div className="detail-section-title">Trip Details</div>
            {/* Omitted for brevity: rendering trip rows */}
            <div>Driver: {caseData.driver_id}</div>
            <div>Fare: {'\u20B9'}{caseData.fare_inr}</div>
          </div>
          <div className="detail-section">
            <div className="detail-section-title">Case Action</div>
            <textarea className="notes-textarea" placeholder="Add notes…" value={notes} onChange={e => setNotes(e.target.value)} />
            <select style={{width: '100%', marginBottom: 12, padding: 8}} value={status} onChange={e=>setStatus(e.target.value)}>
              <option value="">Select Action</option>
              <option value="confirmed_fraud">Confirm Fraud</option>
              <option value="false_alarm">Mark False Alarm</option>
              <option value="escalated">Escalate</option>
            </select>
            <button className="submit-btn" onClick={submitStatus} disabled={!status || submitting}>Update Case</button>
            {flash && <div className={`flash ${flash.type}`}>{flash.msg}</div>}
          </div>
        </div>
        <div>
           <div className="detail-section">
            <div className="detail-section-title">Driver Action</div>
            <textarea className="reason-textarea" placeholder="Reason…" value={drvReason} onChange={e=>setDrvReason(e.target.value)} />
             <select style={{width: '100%', marginBottom: 12, padding: 8}} value={drvAction} onChange={e=>setDrvAction(e.target.value)}>
              <option value="">Select Action</option>
              <option value="suspend">Suspend</option>
              <option value="flag_review">Flag for Review</option>
            </select>
            <button className="submit-btn" onClick={submitDriverAction} disabled={!drvAction || drvSubmit}>Take Action</button>
             {drvFlash && <div className={`flash ${drvFlash.type}`}>{drvFlash.msg}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function DriverProfile() {
  const [driverId,  setDriverId]  = useState('');
  const [profile,   setProfile]   = useState(null);
  const [loading,   setLoading]   = useState(false);

  const loadProfile = async () => {
    if(!driverId) return;
    setLoading(true);
    try {
      const data = await apiGet(`/intelligence/driver/${encodeURIComponent(driverId.trim())}`);
      setProfile(data);
    } catch(err) {
      setProfile({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fade-in">
       <div className="driver-search-bar">
        <input className="driver-id-input" value={driverId} onChange={e=>setDriverId(e.target.value)} placeholder="Enter driver ID…" />
        <button className="load-btn" onClick={loadProfile}>Load Profile</button>
      </div>
      {profile && (
        <div style={{background: 'var(--surface)', padding: 20, borderRadius: 8}}>
          {profile.error ? (
            <div style={{color: 'red'}}>{profile.error}</div>
          ) : (
            <div>
              <h3>Driver {profile.driver_id}</h3>
              <p>Risk Score: {(profile.risk_score * 100).toFixed(1)}%</p>
              <p>Fraud Rate: {(profile.fraud_rate * 100).toFixed(1)}%</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Analyst() {
  const { auth, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('queue');
  const [selectedCase, setSelectedCase] = useState(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={auth || { name: 'Analyst', role: 'ops_analyst' }}
        onLogout={handleLogout}
      />
      <div className="main-content">
        {activeTab === 'queue' && <CaseQueue onSelectCase={(c) => { setSelectedCase(c); setActiveTab('detail'); }} />}
        {activeTab === 'detail' && <CaseDetail selectedCase={selectedCase} onBack={() => setActiveTab('queue')} />}
        {activeTab === 'driver' && <DriverProfile />}
      </div>
    </>
  );
}
