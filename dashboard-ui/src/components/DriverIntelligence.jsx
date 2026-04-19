import React, { useState, useEffect } from 'react';
import { apiGet } from '../utils/api';

export default function DriverIntelligence() {
  const [topDrivers, setTopDrivers] = useState([]);
  const [summary, setSummary]       = useState(null);
  const [selected, setSelected]     = useState(null);
  const [profile, setProfile]       = useState(null);
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    const fetchTop = async () => {
      try {
        const data = await apiGet('/intelligence/top-risk?limit=15');
        setTopDrivers(data.drivers || []);
        setSummary(data.summary || null);
      } catch { /* fall back to last known good state */ }
    };
    fetchTop();
    const t = setInterval(fetchTop, 30000);
    return () => clearInterval(t);
  }, []);

  const loadProfile = async (driverId) => {
    setSelected(driverId);
    setLoading(true);
    setProfile(null);
    try {
      const data = await apiGet(`/intelligence/driver/${driverId}`);
      setProfile(data);
    } catch(e) {
      setProfile({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const actionColor = (action) => ({
    SUSPEND:     'var(--danger)',
    FLAG_REVIEW: 'var(--warning)',
    MONITOR:     '#60A5FA',
    CLEAR:       'var(--success)',
  }[action] || 'var(--muted)');

  const riskColor = (level) => ({
    CRITICAL: 'var(--danger)',
    HIGH:     'var(--warning)',
    MEDIUM:   '#60A5FA',
    LOW:      'var(--success)',
  }[level] || 'var(--muted)');

  return (
    <div className="col" style={{ padding: 0 }}>
      {/* Header */}
      <div className="feed-header">
        <div>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700, fontSize: 14
          }}>
            Driver Intelligence
          </div>
          {summary ? (
            <div className="feed-count" style={{ lineHeight: 1.5 }}>
              {summary.total_suspend > 0 && (
                <span style={{ color: 'var(--danger)' }}>
                  {summary.total_suspend} suspend
                </span>
              )}
              {summary.total_suspend > 0 && summary.total_flag_review > 0 && ' · '}
              {summary.total_flag_review > 0 && (
                <span style={{ color: 'var(--warning)' }}>
                  {summary.total_flag_review} review
                </span>
              )}
              {(summary.total_suspend > 0 || summary.total_flag_review > 0) && summary.total_ring_members > 0 && ' · '}
              {summary.total_ring_members > 0 && (
                <span style={{ color: 'var(--danger)' }}>
                  {summary.total_ring_members} ring
                </span>
              )}
            </div>
          ) : (
            <div className="feed-count">
              Click driver to load full profile
            </div>
          )}
        </div>
        <div style={{
          fontSize: 10,
          color: 'var(--muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          {topDrivers.length} ranked
        </div>
      </div>

      {/* Driver list */}
      <div style={{
        height: profile ? '40%' : '100%',
        overflowY: 'auto',
        transition: 'height 0.3s ease',
      }}>
        {topDrivers.map((d, i) => (
          <div
            key={d.driver_id}
            onClick={() => loadProfile(d.driver_id)}
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid rgba(46,46,74,0.5)',
              cursor: 'pointer',
              background: selected === d.driver_id
                ? 'rgba(255,107,43,0.06)'
                : 'transparent',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => {
              if (selected !== d.driver_id)
                e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
            }}
            onMouseLeave={e => {
              if (selected !== d.driver_id)
                e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
            }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{
                  fontSize: 10,
                  color: 'var(--muted)',
                  width: 16,
                  fontFamily: 'var(--font-mono)',
                }}>#{i+1}</span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text)',
                }}>
                  {d.driver_id.slice(0, 10)}...
                </span>
                {d.is_ring_member && (
                  <span style={{
                    fontSize: 9,
                    background: 'rgba(239,68,68,0.15)',
                    color: 'var(--danger)',
                    padding: '1px 5px',
                    borderRadius: 3,
                    fontWeight: 700,
                    letterSpacing: '0.05em',
                  }}>
                    RING{d.ring_role === 'leader' ? ' LEADER' : ''}
                  </span>
                )}
              </div>
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                color: actionColor(d.recommended_action),
                fontFamily: 'var(--font-display)',
              }}>
                {d.recommended_action}
              </span>
            </div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                {(d.fraud_rate * 100).toFixed(1)}% fraud
                · {d.total_trips} trips
              </span>
              <div style={{
                width: 60,
                height: 4,
                background: 'var(--border)',
                borderRadius: 2,
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${d.risk_score * 100}%`,
                  height: '100%',
                  background: riskColor(d.risk_level),
                  borderRadius: 2,
                  transition: 'width 0.8s ease',
                }} />
              </div>
            </div>
          </div>
        ))}
        {topDrivers.length === 0 && (
          <div className="loading">
            <div className="spinner" />
            Loading driver rankings...
          </div>
        )}
      </div>

      {/* Profile panel */}
      {(loading || profile) && (
        <div style={{
          height: '60%',
          overflowY: 'auto',
          borderTop: '1px solid var(--border)',
          padding: '12px 14px',
        }}>
          {loading && (
            <div className="loading">
              <div className="spinner" />
              Loading profile...
            </div>
          )}

          {profile && !profile.error && (
            <>
              {/* Risk level header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <div style={{
                    fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 13,
                    color: riskColor(profile.risk_level),
                  }}>
                    {profile.risk_level} RISK
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                    Score: {(profile.current_risk_score * 100).toFixed(1)}%
                    · {profile.fraud_trips}/{profile.total_trips} fraud
                  </div>
                </div>
                <div style={{
                  textAlign: 'right', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 11,
                  color: actionColor(profile.recommendation?.action),
                }}>
                  {profile.recommendation?.action}
                </div>
              </div>

              {/* Recommendation reason */}
              {profile.recommendation?.reason && (
                <div style={{
                  fontSize: 10, color: 'var(--muted)', lineHeight: 1.6, padding: '8px 10px', background: 'var(--navy)',
                  borderRadius: 4, marginBottom: 10, borderLeft: `2px solid ${actionColor(profile.recommendation.action)}`,
                }}>
                  {profile.recommendation.reason}
                </div>
              )}

              {/* Ring intelligence */}
              {profile.ring_intelligence?.is_ring_member && (
                <div style={{
                  padding: '8px 10px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: 4, marginBottom: 10, fontSize: 10, color: 'var(--text)', lineHeight: 1.6,
                }}>
                  <span style={{ color: 'var(--danger)', fontWeight: 700 }}>
                    RING {profile.ring_intelligence.ring_role?.toUpperCase() || 'MEMBER'}
                  </span>
                  {' · '}Ring {profile.ring_intelligence.ring_id?.slice(0, 8)}
                  {' · '}{profile.ring_intelligence.ring_size} members
                  {' · '}{profile.ring_intelligence.ring_zone_name}
                </div>
              )}

              {/* Peer comparison metrics */}
              {profile.peer_comparison?.metrics && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{
                    fontSize: 10, fontWeight: 700, color: 'var(--muted)', marginBottom: 6, fontFamily: 'var(--font-display)',
                  }}>
                    vs {profile.peer_comparison.zone_name} median
                  </div>
                  {Object.entries(profile.peer_comparison.metrics).map(([key, m]) => (
                    <div key={key} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0',
                      fontSize: 10, borderBottom: '1px solid rgba(46,46,74,0.3)',
                    }}>
                      <span style={{ color: 'var(--muted)' }}>{key.replace(/_/g, ' ')}</span>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ color: 'var(--text)' }}>
                          {typeof m.driver === 'number' && m.driver < 1 ? (m.driver * 100).toFixed(1) + '%' : m.driver}
                        </span>
                        <span style={{
                          color: m.flag ? 'var(--danger)' : 'var(--success)', fontWeight: 700, fontSize: 9,
                        }}>
                          {m.percentile.toFixed(0)}th
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Timeline (last 7 days mini) */}
              {profile.timeline && profile.timeline.length > 0 && (
                <div>
                  <div style={{
                    fontSize: 10, fontWeight: 700, color: 'var(--muted)', marginBottom: 6, fontFamily: 'var(--font-display)',
                  }}>
                    7-day risk trend
                  </div>
                  <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end', height: 32 }}>
                    {profile.timeline.slice(-7).map((day, i) => (
                      <div key={i} style={{
                        flex: 1, height: `${Math.max(4, day.risk_score * 100)}%`, background: riskColor(day.risk_level),
                        borderRadius: '2px 2px 0 0', opacity: 0.8, transition: 'height 0.5s ease',
                      }}
                        title={`${day.date}: ${day.risk_score.toFixed(3)} (${day.risk_level})`}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {profile && profile.error && (
            <div style={{ color: 'var(--danger)', fontSize: 12 }}>
              Error: {profile.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
