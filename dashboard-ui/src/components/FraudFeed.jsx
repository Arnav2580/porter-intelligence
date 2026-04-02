import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet } from '../utils/api';

const FRAUD_TYPE_LABELS = {
  fake_trip:          'Fake Trip',
  cash_extortion:     'Cash Extortion',
  route_deviation:    'Route Deviation',
  fake_cancellation:  'Fake Cancel',
  duplicate_trip:     'Duplicate Trip',
  inflated_distance:  'Inflated Dist.',
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
};

export default function FraudFeed() {
  const [items, setItems]   = useState([]);
  const [total, setTotal]   = useState(0);
  const listRef = useRef(null);

  const fetchFeed = useCallback(async () => {
    try {
      const data = await apiGet('/fraud/live-feed?limit=40');
      setItems(data.items || []);
      setTotal(data.total_shown || 0);
    } catch(e) {}
  }, []);

  useEffect(() => {
    fetchFeed();
    const t = setInterval(fetchFeed, 10000);
    return () => clearInterval(t);
  }, [fetchFeed]);

  const riskOf = (confidence) =>
    confidence > 0.85 ? 'CRITICAL' :
    confidence > 0.75 ? 'HIGH' :
    confidence > 0.65 ? 'MEDIUM' : 'LOW';

  const tierOf = (confidence) =>
    confidence >= 0.94 ? 'action' :
    confidence >= 0.45 ? 'watchlist' : 'clear';

  const tierLabel = (t) =>
    t === 'action' ? 'ACTION' :
    t === 'watchlist' ? 'WATCH' : 'CLEAR';

  return (
    <div className="col feed-col" style={{ padding: 0 }}>
      <div className="feed-header">
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 14 }}>
            Live Fraud Feed
          </div>
          <div className="feed-count">
            Refreshes every 10s &middot; Showing {items.length} cases
          </div>
        </div>
        <div className="live-badge">
          <div className="live-dot"></div>
          LIVE
        </div>
      </div>

      <div className="feed-list" ref={listRef}>
        {items.length === 0 && (
          <div className="loading">
            <div className="spinner"></div>
            Loading fraud cases...
          </div>
        )}
        {items.map((item, i) => {
          const risk = riskOf(item.confidence);
          const tier = tierOf(item.confidence);
          return (
            <div key={item.trip_id + i} className="feed-item">
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
    </div>
  );
}
