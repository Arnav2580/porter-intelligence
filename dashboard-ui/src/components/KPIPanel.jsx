import React from 'react';
import { useCountUp } from '../hooks/useCountUp';

export default function KPIPanel({ kpi }) {
  const fraudCaught    = useCountUp(kpi?.fraud_detected || 0);
  const improvement    = useCountUp(Math.round(kpi?.improvement_pct || 0));
  const fprVal         = kpi?.fpr_pct || 0;
  const recPerTrip     = kpi?.net_recoverable_per_trip || 0;
  const annualCrore    = kpi?.annual_recovery_crore || 0;
  const baselineCaught = kpi?.baseline_caught || 0;
  const xgbCaught      = kpi?.xgboost_caught || 0;
  const maxBar         = xgbCaught || 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      <div className="section-label">Pilot KPI Dashboard</div>

      <div className="kpi-grid">
        <div className="kpi-card orange">
          <div className="kpi-label">Fraud Caught</div>
          <div className="kpi-value">{fraudCaught}</div>
          <div className="kpi-sub">live eval window</div>
        </div>
        <div className="kpi-card green">
          <div className="kpi-label">Improvement</div>
          <div className="kpi-value">+{improvement}%</div>
          <div className="kpi-sub">vs rule baseline</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-label">False Positive</div>
          <div className="kpi-value">{fprVal.toFixed(2)}%</div>
          <div className="kpi-sub">target &le; 8%</div>
        </div>
        <div className="kpi-card blue">
          <div className="kpi-label">Net Rec/Trip</div>
          <div className="kpi-value">
            {'\u20B9'}{recPerTrip.toFixed(2)}
          </div>
          <div className="kpi-sub">target &ge; {'\u20B9'}0.50</div>
        </div>
      </div>

      {kpi?.pilot_criteria_pass && (
        <div className="pilot-banner">
          <div className="pilot-check">{'\u2705'}</div>
          <div>
            <div className="pilot-text">All Pilot Criteria Passed</div>
            <div className="pilot-sub">
              FPR &le; 8% &middot; Recovery &ge; {'\u20B9'}0.50/trip &middot; Detection &ge; 25%
            </div>
          </div>
        </div>
      )}

      <div className="comparison-card">
        <div className="section-label" style={{marginBottom: 10}}>
          Baseline vs XGBoost — Fraud Caught
        </div>
        <div className="comparison-row">
          <div className="comparison-label">Baseline</div>
          <div className="comparison-bar-wrap">
            <div className="comparison-bar"
              style={{
                width: `${(baselineCaught / maxBar) * 100}%`,
                background: '#8888AA'
              }}
            />
          </div>
          <div className="comparison-val">{baselineCaught}</div>
        </div>
        <div className="comparison-row">
          <div className="comparison-label">XGBoost</div>
          <div className="comparison-bar-wrap">
            <div className="comparison-bar"
              style={{ width: '100%', background: '#FF6B2B' }}
            />
          </div>
          <div className="comparison-val"
            style={{ color: '#FF6B2B', fontWeight: 700 }}>
            {xgbCaught}
          </div>
        </div>
      </div>

      <div className="annual-card">
        <div>
          <div className="annual-label">Annual Recovery (Porter scale)</div>
          <div className="annual-value">
            {'\u20B9'}{annualCrore.toFixed(1)} Crore
          </div>
        </div>
      </div>

    </div>
  );
}
