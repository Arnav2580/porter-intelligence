import React, { useState } from 'react';
import { apiPost } from '../utils/api';

const ZONE_OPTIONS = [
  { id: 'blr_koramangala',     label: 'Koramangala' },
  { id: 'blr_indiranagar',     label: 'Indiranagar' },
  { id: 'blr_whitefield',      label: 'Whitefield' },
  { id: 'blr_hsr',             label: 'HSR Layout' },
  { id: 'blr_btm',             label: 'BTM Layout' },
  { id: 'blr_marathahalli',    label: 'Marathahalli' },
  { id: 'blr_hebbal',          label: 'Hebbal' },
  { id: 'blr_electronic_city', label: 'Electronic City' },
  { id: 'blr_jayanagar',       label: 'Jayanagar' },
  { id: 'blr_bannerghatta',    label: 'Bannerghatta Rd' },
  { id: 'blr_yeshwanthpur',    label: 'Yeshwanthpur' },
  { id: 'blr_rajajinagar',     label: 'Rajajinagar' },
];

const VEHICLE_OPTIONS = [
  'two_wheeler', 'three_wheeler', 'mini_truck', 'truck_14ft', 'truck_17ft'
];

const ZONE_COORDINATES = {
  blr_whitefield:      { lat: 12.9698, lon: 77.7500 },
  blr_koramangala:     { lat: 12.9352, lon: 77.6245 },
  blr_hsr:             { lat: 12.9116, lon: 77.6389 },
  blr_indiranagar:     { lat: 12.9784, lon: 77.6408 },
  blr_jayanagar:       { lat: 12.9299, lon: 77.5833 },
  blr_hebbal:          { lat: 13.0358, lon: 77.5970 },
  blr_yeshwanthpur:    { lat: 13.0210, lon: 77.5540 },
  blr_electronic_city: { lat: 12.8458, lon: 77.6603 },
  blr_bannerghatta:    { lat: 12.8934, lon: 77.5976 },
  blr_marathahalli:    { lat: 12.9591, lon: 77.7009 },
  blr_btm:             { lat: 12.9166, lon: 77.6101 },
  blr_rajajinagar:     { lat: 12.9913, lon: 77.5527 },
  mum_andheri:         { lat: 19.1136, lon: 72.8697 },
  mum_bandra:          { lat: 19.0544, lon: 72.8405 },
  del_cp:              { lat: 28.6315, lon: 77.2167 },
  del_gurgaon:         { lat: 28.4595, lon: 77.0266 },
};

export default function TripScorer() {
  const [form, setForm] = useState({
    payment_mode:         'cash',
    vehicle_type:         'two_wheeler',
    pickup_zone_id:       'blr_koramangala',
    dropoff_zone_id:      'blr_whitefield',
    declared_distance_km: 8.5,
    declared_duration_min: 4.0,
    fare_inr:             450,
    surge_multiplier:     1.8,
    is_night:             true,
    hour_of_day:          22,
    day_of_week:          4,
    is_peak_hour:         false,
    zone_demand_at_time:  2.1,
  });
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);

  const update = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const score = async () => {
    setLoading(true);
    setResult(null);
    try {
      const pickupCoords  = ZONE_COORDINATES[form.pickup_zone_id]
        || { lat: 12.9352, lon: 77.6245 };
      const dropoffCoords = ZONE_COORDINATES[form.dropoff_zone_id]
        || { lat: 12.9698, lon: 77.7500 };

      const payload = {
        trip_id:               `DEMO_${Date.now()}`,
        driver_id:             'DEMO_DRIVER_001',
        customer_id:           'DEMO_CUST_001',
        pickup_lat:            pickupCoords.lat,
        pickup_lon:            pickupCoords.lon,
        dropoff_lat:           dropoffCoords.lat,
        dropoff_lon:           dropoffCoords.lon,
        status:                'completed',
        customer_complaint_flag: false,
        ...form,
        declared_distance_km:  parseFloat(form.declared_distance_km),
        declared_duration_min: parseFloat(form.declared_duration_min),
        fare_inr:              parseFloat(form.fare_inr),
        surge_multiplier:      parseFloat(form.surge_multiplier),
        zone_demand_at_time:   parseFloat(form.zone_demand_at_time),
        hour_of_day:           parseInt(form.hour_of_day),
        day_of_week:           parseInt(form.day_of_week),
        requested_at:          new Date().toISOString(),
      };
      
      const data = await apiPost('/fraud/score', payload);
      setResult(data);
    } catch(e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const resultClass =
    !result ? '' :
    result.tier === 'action' ? 'fraud' :
    result.tier === 'watchlist' ? 'medium' : 'clean';

  return (
    <div className="scorer-card">
      <div className="section-label" style={{marginBottom: 12}}>
        Live Trip Scorer
      </div>

      <div className="scorer-form">
        <div className="form-group">
          <div className="form-label">Payment</div>
          <select className="form-select"
            value={form.payment_mode}
            onChange={e => update('payment_mode', e.target.value)}>
            <option value="cash">Cash</option>
            <option value="upi">UPI</option>
            <option value="credit">Credit</option>
          </select>
        </div>
        <div className="form-group">
          <div className="form-label">Vehicle</div>
          <select className="form-select"
            value={form.vehicle_type}
            onChange={e => update('vehicle_type', e.target.value)}>
            {VEHICLE_OPTIONS.map(v => (
              <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <div className="form-label">Pickup Zone</div>
          <select className="form-select"
            value={form.pickup_zone_id}
            onChange={e => update('pickup_zone_id', e.target.value)}>
            {ZONE_OPTIONS.map(z => (
              <option key={z.id} value={z.id}>{z.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <div className="form-label">Dropoff Zone</div>
          <select className="form-select"
            value={form.dropoff_zone_id}
            onChange={e => update('dropoff_zone_id', e.target.value)}>
            {ZONE_OPTIONS.map(z => (
              <option key={z.id} value={z.id}>{z.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <div className="form-label">Fare ({'\u20B9'})</div>
          <input className="form-input" type="number"
            value={form.fare_inr}
            onChange={e => update('fare_inr', e.target.value)} />
        </div>
        <div className="form-group">
          <div className="form-label">Distance (km)</div>
          <input className="form-input" type="number"
            step="0.1"
            value={form.declared_distance_km}
            onChange={e => update('declared_distance_km', e.target.value)} />
        </div>
        <div className="form-group">
          <div className="form-label">Duration (min)</div>
          <input className="form-input" type="number"
            step="0.5"
            value={form.declared_duration_min}
            onChange={e => update('declared_duration_min', e.target.value)} />
        </div>
      </div>

      <button className="score-btn"
        onClick={score} disabled={loading}>
        {loading ? 'Scoring...' : '\u26A1 Score This Trip'}
      </button>

      {result && !result.error && (
        <div className={`score-result ${resultClass}`}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start'
          }}>
            <div>
              <div className="score-prob">
                {(result.fraud_probability * 100).toFixed(1)}%
              </div>
              <div className="score-label">
                fraud probability
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className={`tier-badge ${result.tier || ''} ${result.tier === 'action' ? 'pulse' : ''}`}>
                {result.tier_label || result.fraud_risk_level}
              </div>
              <div style={{
                fontSize: 10, color: 'var(--muted)', marginTop: 4,
                maxWidth: 140, lineHeight: 1.4,
              }}>
                {result.action_required || (result.is_fraud_predicted
                  ? '\uD83D\uDEA8 FLAG FOR REVIEW'
                  : '\u2705 CLEAR')}
              </div>
            </div>
          </div>
          {result.top_signals?.length > 0 && (
            <div className="score-signals">
              {result.top_signals.map((s, i) => (
                <div key={i} className="score-signal">{s}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <div style={{
          marginTop: 12, padding: 10,
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 6,
          fontSize: 11, color: 'var(--danger)'
        }}>
          {result.error}
        </div>
      )}
    </div>
  );
}
