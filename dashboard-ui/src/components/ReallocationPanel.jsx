import React, { useState, useEffect } from 'react';
import { apiGet } from '../utils/api';

export default function ReallocationPanel() {
  const [suggestions, setSuggestions] = useState([]);
  const [summary, setSummary]         = useState(null);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    const fetch_data = async () => {
      try {
        const [sugData, sumData] = await Promise.all([
          apiGet('/efficiency/reallocation?limit=5'),
          apiGet('/efficiency/summary'),
        ]);
        setSuggestions(sugData.suggestions || []);
        setSummary(sumData);
      } catch { /* keep prior data */ } finally {
        setLoading(false);
      }
    };
    fetch_data();
    const t = setInterval(fetch_data, 60000);
    return () => clearInterval(t);
  }, []);

  const urgencyColor = (u) => ({
    IMMEDIATE: 'var(--danger)',
    HIGH:      'var(--warning)',
    MEDIUM:    '#60A5FA',
  }[u] || 'var(--muted)');

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: 14,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div className="section-label" style={{margin: 0}}>
          Fleet Reallocation
        </div>
        {summary && (
          <div style={{ fontSize: 10, color: 'var(--orange)', fontFamily: 'var(--font-mono)' }}>
            {'\u20B9'}{(summary.reallocation_opportunity_inr / 1000).toFixed(0)}K opportunity
          </div>
        )}
      </div>

      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
          {[
            ['Utilisation', `${(summary.overall_utilisation*100).toFixed(1)}%`, summary.overall_utilisation > 0.6 ? 'var(--success)' : 'var(--warning)'],
            ['Dead miles', `${(summary.total_dead_mile_rate*100).toFixed(1)}%`, summary.total_dead_mile_rate < 0.15 ? 'var(--success)' : 'var(--warning)'],
            ['Idle now', `${summary.idle_vehicle_hours_now}`, 'var(--muted)'],
            ['Dead cost/day', `${'\u20B9'}${(summary.total_dead_cost_per_day/1000).toFixed(1)}K`, 'var(--danger)'],
          ].map(([label, value, color]) => (
            <div key={label} style={{ background: 'var(--navy)', borderRadius: 4, padding: '6px 8px' }}>
              <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>
                {label}
              </div>
              <div style={{ fontSize: 14, fontFamily: 'var(--font-display)', fontWeight: 700, color }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading && (
        <div className="loading" style={{padding: '8px 0'}}>
          <div className="spinner" /> Computing suggestions...
        </div>
      )}

      {!loading && suggestions.length === 0 && (
        <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center', padding: '8px 0' }}>
          No reallocation opportunities at current hour
        </div>
      )}

      {suggestions.slice(0, 3).map((s, i) => (
        <div key={s.suggestion_id} style={{
          padding: '8px 0',
          borderBottom: i < Math.min(suggestions.length, 3) - 1 ? '1px solid rgba(46,46,74,0.4)' : 'none',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 3 }}>
            <div style={{ fontSize: 11, color: 'var(--text)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
              {s.from_zone_name} {'\u2192'} {s.to_zone_name}
            </div>
            <span style={{ fontSize: 9, fontWeight: 700, color: urgencyColor(s.urgency), fontFamily: 'var(--font-display)', letterSpacing: '0.05em' }}>
              {s.urgency}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)' }}>
            <span>
              {s.idle_count}{'\u00D7'} {s.vehicle_type.replace('_',' ')} {'\u00B7'} {s.to_demand_mult.toFixed(1)}x demand {' \u00B7 '}{s.distance_km}km
            </span>
            <span style={{ color: 'var(--success)' }}>
              +{'\u20B9'}{s.expected_revenue_inr.toFixed(0)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
