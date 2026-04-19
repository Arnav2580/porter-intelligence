import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet } from '../utils/api';

const FRAUD_TYPE_LABELS = {
  fake_trip:          'Ghost Trip Detected',
  cash_extortion:     'Fare Extortion Signal',
  route_deviation:    'Route Manipulation',
  fake_cancellation:  'Cancellation Abuse',
  duplicate_trip:     'Duplicate Trip Pattern',
  inflated_distance:  'Distance Inflation',
};

const ZONE_LABELS = {
  blr_koramangala:     'Koramangala',
  blr_whitefield:      'Whitefield',
  blr_indiranagar:     'Indiranagar',
  blr_hsr:             'HSR Layout',
  blr_marathahalli:    'Marathahalli',
  blr_btm:             'BTM Layout',
  blr_hebbal:          'Hebbal',
  blr_electronic_city: 'Elec. City',
  blr_jayanagar:       'Jayanagar',
  blr_bannerghatta:    'Bannerghatta',
  blr_yeshwanthpur:    'Yeshwanthpur',
  blr_rajajinagar:     'Rajajinagar',
  mum_andheri:         'Andheri',
  mum_bandra:          'Bandra',
  del_cp:              'Connaught Pl.',
  del_gurgaon:         'Gurgaon',
};

function TripPopup({ trip, tier, onClose }) {
  const tierColor = tier === 'action' ? '#ef4444' : '#f59e0b';
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.72)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 9999,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#13141e',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 12, padding: 24, width: 460, maxWidth: '92vw',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{
              padding: '3px 9px', borderRadius: 4, fontSize: 11, fontWeight: 700,
              background: `${tierColor}22`, color: tierColor,
            }}>{tier?.toUpperCase()}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
              {(trip.fraud_type || 'Unknown').replace(/_/g, ' ')}
            </span>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: '0 4px',
          }}>×</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px', marginBottom: 16 }}>
          {[
            ['Trip ID',      trip.trip_id   || '--'],
            ['Driver',       trip.driver_id || '--'],
            ['Zone',         trip.zone_id   || '--'],
            ['Fare',         `₹${(trip.fare_inr || 0).toFixed(0)}`],
            ['Recoverable',  `+₹${(trip.recoverable || 0).toFixed(0)}`],
            ['Confidence',   `${((trip.confidence || 0) * 100).toFixed(0)}%`],
          ].map(([label, val]) => (
            <div key={label}>
              <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text)', wordBreak: 'break-all' }}>{val}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '7px 0',
            background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 5, color: '#ef4444', fontSize: 11, fontWeight: 600, cursor: 'pointer',
          }}>Confirm Fraud</button>
          <button onClick={onClose} style={{
            flex: 1, padding: '7px 0',
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 5, color: 'var(--muted)', fontSize: 11, cursor: 'pointer',
          }}>Dismiss</button>
          <button onClick={onClose} style={{
            flex: 1, padding: '7px 0',
            background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
            borderRadius: 5, color: '#f59e0b', fontSize: 11, fontWeight: 600, cursor: 'pointer',
          }}>View in Queue →</button>
        </div>
      </div>
    </div>
  );
}

export default function FraudFeed({ thresholds }) {
  const [items, setItems]             = useState([]);
  const [isBenchmark, setIsBenchmark] = useState(true);
  const [error, setError]             = useState(false);
  const [selectedTrip, setSelectedTrip] = useState(null);
  const listRef = useRef(null);

  // Read tier thresholds from props (passed from health endpoint) or fall back to
  // config defaults. Never hardcode thresholds in the frontend.
  const actionThreshold    = thresholds?.action_threshold    ?? 0.80;
  const watchlistThreshold = thresholds?.watchlist_threshold ?? 0.50;

  const fetchFeed = useCallback(async () => {
    try {
      const data = await apiGet('/fraud/live-feed?limit=40');
      setItems(data.items || []);
      setIsBenchmark(data.is_benchmark !== false);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await fetchFeed();
    };
    tick();
    const t = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [fetchFeed]);

  const tierOf = (confidence) =>
    confidence >= actionThreshold    ? 'action' :
    confidence >= watchlistThreshold ? 'watchlist' : 'clear';

  const tierLabel = (t) =>
    t === 'action' ? 'ACTION' :
    t === 'watchlist' ? 'WATCH' : 'CLEAR';

  const feedLabel     = isBenchmark ? 'BENCHMARK DATA' : 'LIVE';
  const feedLabelColor = isBenchmark ? 'var(--warning)' : 'var(--success)';
  const feedSubLabel  = isBenchmark
    ? '100k-trip evaluation set · start simulator for live feed'
    : `Refreshes every 3s · Showing ${items.length} cases`;

  return (
    <div className="col feed-col" style={{ padding: 0 }}>
      <div className="feed-header">
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 14 }}>
            Trip Anomaly Feed
          </div>
          <div className="feed-count" style={{ color: 'var(--muted)' }}>
            Real-time trip scoring &middot; Behavioral signals only &middot; Identity controls handled by upstream systems
          </div>
          <div className="feed-count" style={{ color: isBenchmark ? 'var(--warning)' : 'var(--muted)', marginTop: 4 }}>
            {feedSubLabel}
          </div>
        </div>
        <div className="live-badge" style={{ color: feedLabelColor }}>
          <div className="live-dot" style={{
            background: feedLabelColor,
            animation: isBenchmark ? 'none' : 'pulse-dot 2s infinite',
          }} />
          {feedLabel}
        </div>
      </div>

      <div className="feed-list" ref={listRef}>
        {error && (
          <div style={{
            margin: 12, padding: '10px 12px',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 6, fontSize: 11, color: 'var(--danger)',
          }}>
            Feed unavailable — check API health
          </div>
        )}
        {!error && items.length === 0 && (
          <div className="loading">
            <div className="spinner" />
            Loading fraud cases...
          </div>
        )}
        {items.map((item, i) => {
          const tier = tierOf(item.confidence);
          return (
            <div key={item.trip_id + i} className="feed-item" onClick={() => setSelectedTrip(item)} style={{ cursor: 'pointer' }}>
              <div className="feed-item-top">
                <div className="feed-fraud-type">
                  {FRAUD_TYPE_LABELS[item.fraud_type] || item.fraud_type}
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span className={`tier-badge ${tier} ${tier === 'action' ? 'pulse' : ''}`}>
                    {tierLabel(tier)}
                  </span>
                  <span className="feed-fare">
                    {'\u20B9'}{item.fare_inr?.toFixed(0)}
                  </span>
                </div>
              </div>
              <div className="feed-item-bottom">
                <span className="feed-zone">
                  {'\uD83D\uDCCD'} {ZONE_LABELS[item.zone_id] || item.zone_id}
                </span>
                <span className="feed-recoverable">
                  +{'\u20B9'}{item.recoverable?.toFixed(0)} recoverable
                </span>
                <span className="feed-confidence">
                  {(item.confidence * 100).toFixed(0)}% conf
                </span>
              </div>
            </div>
          );
        })}
      </div>
      {selectedTrip && (
        <TripPopup
          trip={selectedTrip}
          tier={tierOf(selectedTrip.confidence)}
          onClose={() => setSelectedTrip(null)}
        />
      )}
    </div>
  );
}
