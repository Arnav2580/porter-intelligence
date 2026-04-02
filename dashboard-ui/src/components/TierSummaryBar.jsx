import React, { useState, useEffect } from 'react';
import { apiGet } from '../utils/api';

export default function TierSummaryBar() {
  const [tierData, setTierData] = useState(null);

  useEffect(() => {
    const fetchTiers = async () => {
      try {
        const data = await apiGet('/fraud/tier-summary');
        setTierData(data);
      } catch(e) {}
    };
    fetchTiers();
    const t = setInterval(fetchTiers, 60000);
    return () => clearInterval(t);
  }, []);

  if (!tierData?.evaluation) return null;

  const ev = tierData.evaluation;

  return (
    <div>
      <div className="section-label">Two-Stage Scoring</div>
      <div className="tier-bar">
        <div className="tier-bar-item" style={{ borderBottom: '2px solid #EF4444' }}>
          <div className="tier-bar-count" style={{ color: '#EF4444' }}>
            {(ev.action_tier_caught || 0).toLocaleString()}
          </div>
          <div className="tier-bar-label">Action</div>
          <div style={{ fontSize: 9, color: '#EF4444', marginTop: 2 }}>
            {((ev.action_precision || 0) * 100).toFixed(0)}% prec
          </div>
        </div>
        <div className="tier-bar-item" style={{ borderBottom: '2px solid #F59E0B' }}>
          <div className="tier-bar-count" style={{ color: '#F59E0B' }}>
            {(ev.watchlist_caught || 0).toLocaleString()}
          </div>
          <div className="tier-bar-label">Watchlist</div>
          <div style={{ fontSize: 9, color: '#F59E0B', marginTop: 2 }}>
            monitoring
          </div>
        </div>
        <div className="tier-bar-item" style={{ borderBottom: '2px solid #22C55E' }}>
          <div className="tier-bar-count" style={{ color: '#22C55E' }}>
            {((ev.total_trips || 0) - (ev.action_tier_caught || 0) - (ev.watchlist_caught || 0)).toLocaleString()}
          </div>
          <div className="tier-bar-label">Clear</div>
          <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>
            no action
          </div>
        </div>
      </div>
    </div>
  );
}
