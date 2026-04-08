import { useEffect, useState } from 'react';
import { apiPost } from '../utils/api';

const DEFAULT_FORM = {
  gmv_crore: 1000,
  trips_per_day: 43200,
  fraud_rate_pct: 5.9,
  platform_price_crore: 3.25,
};

function formatCrore(value) {
  return `₹${Number(value || 0).toFixed(2)} Cr`;
}

function formatLakh(value) {
  return `₹${Number(value || 0).toFixed(2)} L`;
}

function formatPct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function ScenarioCard({ scenario }) {
  return (
    <div className="comparison-card" style={{ minWidth: 0 }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
        marginBottom: 10,
      }}>
        <div className="section-label" style={{ marginBottom: 0, textTransform: 'capitalize' }}>
          {scenario.scenario}
        </div>
        <div style={{
          fontSize: 10,
          color: 'var(--muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          {scenario.realization_multiplier.toFixed(2)}x realization
        </div>
      </div>
      <div style={{ fontSize: 26, fontFamily: 'var(--font-display)', fontWeight: 800, color: 'var(--text)' }}>
        {formatCrore(scenario.annual_savings_crore)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10, marginTop: 12 }}>
        <div>
          <div className="kpi-label">Monthly Savings</div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{formatLakh(scenario.monthly_savings_lakh)}</div>
        </div>
        <div>
          <div className="kpi-label">Payback</div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{scenario.payback_months.toFixed(2)} months</div>
        </div>
        <div>
          <div className="kpi-label">ROI</div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{formatPct(scenario.roi_pct)}</div>
        </div>
        <div>
          <div className="kpi-label">Savings / GMV</div>
          <div className="kpi-sub" style={{ marginTop: 4 }}>{scenario.savings_bps_of_gmv.toFixed(1)} bps</div>
        </div>
      </div>
      <div style={{ marginTop: 12, color: 'var(--muted)', fontSize: 11, lineHeight: 1.55 }}>
        {scenario.note}
      </div>
    </div>
  );
}

export default function ROICalculator() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const calculate = async (nextForm) => {
    setSubmitting(true);
    setError('');
    try {
      const response = await apiPost('/roi/calculate', {
        gmv_crore: Number(nextForm.gmv_crore),
        trips_per_day: Number(nextForm.trips_per_day),
        fraud_rate_pct: Number(nextForm.fraud_rate_pct),
        platform_price_crore: Number(nextForm.platform_price_crore),
      });
      setData(response);
    } catch (err) {
      setError(err.message || 'ROI calculator unavailable');
    } finally {
      setLoading(false);
      setSubmitting(false);
    }
  };

  useEffect(() => {
    calculate(DEFAULT_FORM);
  }, []);

  const updateField = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    calculate(form);
  };

  const exportBrief = () => {
    if (!data) return;
    const scenarioRows = data.scenarios.map((scenario) => `
      <tr>
        <td style="padding:8px 10px;border:1px solid #d4d4d8;text-transform:capitalize;">${scenario.scenario}</td>
        <td style="padding:8px 10px;border:1px solid #d4d4d8;">₹${scenario.annual_savings_crore.toFixed(2)} Cr</td>
        <td style="padding:8px 10px;border:1px solid #d4d4d8;">${scenario.payback_months.toFixed(2)} months</td>
        <td style="padding:8px 10px;border:1px solid #d4d4d8;">${scenario.roi_pct.toFixed(1)}%</td>
      </tr>
    `).join('');

    const popup = window.open('', '_blank', 'width=920,height=720');
    if (!popup) return;
    popup.document.write(`
      <html>
        <head>
          <title>Porter Intelligence ROI Brief</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 32px; color: #111827; }
            h1 { margin-bottom: 8px; }
            p { line-height: 1.6; }
            .hero { padding: 20px; border: 1px solid #e5e7eb; border-radius: 12px; margin-bottom: 24px; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th { text-align: left; padding: 8px 10px; border: 1px solid #d4d4d8; background: #f4f4f5; }
          </style>
        </head>
        <body>
          <h1>Porter Intelligence ROI Brief</h1>
          <p>Benchmark-grounded savings model using the scored evaluation artifact and buyer-provided operating assumptions.</p>
          <div class="hero">
            <strong>Realistic Annual Savings:</strong> ₹${data.annual_savings_crore.toFixed(2)} Cr<br/>
            <strong>Payback Period:</strong> ${data.payback_months.toFixed(2)} months<br/>
            <strong>ROI:</strong> ${data.roi_pct.toFixed(1)}%<br/>
            <strong>Annual Trip Volume:</strong> ${data.annual_trip_volume.toLocaleString('en-IN')}<br/>
            <strong>Benchmark Net Recoverable / Trip:</strong> ₹${data.benchmark_net_recoverable_per_trip.toFixed(2)}<br/>
            <strong>Benchmark Fraud Rate:</strong> ${data.benchmark_fraud_rate_pct.toFixed(3)}%
          </div>
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Annual Savings</th>
                <th>Payback</th>
                <th>ROI</th>
              </tr>
            </thead>
            <tbody>${scenarioRows}</tbody>
          </table>
        </body>
      </html>
    `);
    popup.document.close();
    popup.focus();
    popup.print();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="section-label">Commercial ROI Planner</div>

      <form
        onSubmit={handleSubmit}
        className="comparison-card"
        style={{ display: 'grid', gap: 14 }}
      >
        <div style={{ color: 'var(--text)', fontSize: 12, lineHeight: 1.7 }}>
          Benchmark-grounded planning model. We scale the scored recovery-per-trip benchmark by your operating assumptions and show conservative, realistic, and aggressive realization bands.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span className="kpi-label">Annual GMV (Cr)</span>
            <input value={form.gmv_crore} onChange={(e) => updateField('gmv_crore', e.target.value)} type="number" min="1" step="0.1" />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span className="kpi-label">Trips / Day</span>
            <input value={form.trips_per_day} onChange={(e) => updateField('trips_per_day', e.target.value)} type="number" min="1" step="1" />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span className="kpi-label">Leakage Rate (%)</span>
            <input value={form.fraud_rate_pct} onChange={(e) => updateField('fraud_rate_pct', e.target.value)} type="number" min="0.1" max="100" step="0.1" />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span className="kpi-label">Platform Price (Cr)</span>
            <input value={form.platform_price_crore} onChange={(e) => updateField('platform_price_crore', e.target.value)} type="number" min="0.1" step="0.05" />
          </label>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button type="submit" disabled={submitting} style={{
            background: 'var(--orange)',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            padding: '10px 16px',
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            cursor: 'pointer',
          }}>
            {submitting ? 'Recalculating...' : 'Recalculate ROI'}
          </button>
          <button type="button" onClick={exportBrief} disabled={!data} style={{
            background: 'transparent',
            color: 'var(--text)',
            border: '1px solid rgba(148,163,184,0.2)',
            borderRadius: 8,
            padding: '10px 16px',
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            cursor: data ? 'pointer' : 'not-allowed',
          }}>
            Export ROI Brief
          </button>
        </div>
        {error && (
          <div style={{ color: 'var(--danger)', fontSize: 12 }}>
            {error}
          </div>
        )}
      </form>

      {loading && (
        <div className="loading"><div className="spinner" /> Calculating finance scenarios...</div>
      )}

      {!loading && data && (
        <>
          <div className="annual-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="annual-label">Realistic Annual Savings</div>
              <div className="annual-value">{formatCrore(data.annual_savings_crore)}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="annual-label">Payback / ROI</div>
              <div className="annual-value" style={{ fontSize: 22 }}>
                {data.payback_months.toFixed(2)} mo / {formatPct(data.roi_pct)}
              </div>
            </div>
          </div>

          <div className="comparison-card" style={{ color: 'var(--text)', fontSize: 12, lineHeight: 1.8 }}>
            <div>
              Benchmark basis: <strong>₹{data.benchmark_net_recoverable_per_trip.toFixed(2)}</strong> recoverable per trip at a benchmark leakage rate of <strong>{data.benchmark_fraud_rate_pct.toFixed(3)}%</strong>.
            </div>
            <div>
              Buyer inputs: <strong>{Number(form.trips_per_day).toLocaleString('en-IN')}</strong> trips/day, <strong>{Number(form.gmv_crore).toFixed(1)} Cr</strong> annual GMV, <strong>{Number(form.fraud_rate_pct).toFixed(1)}%</strong> leakage assumption.
            </div>
            <div>
              Realistic savings as share of GMV: <strong>{data.savings_bps_of_gmv.toFixed(1)} bps</strong>.
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            {data.scenarios.map((scenario) => (
              <ScenarioCard key={scenario.scenario} scenario={scenario} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
