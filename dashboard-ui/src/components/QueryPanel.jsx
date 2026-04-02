import React, { useState } from 'react';
import { apiPost } from '../utils/api';

const EXAMPLE_QUERIES = [
  'Show me fraud rings in Bangalore',
  'Which drivers have highest risk?',
  'What zones have most fraud?',
  'Give me the KPI summary',
  'Break down fraud by type',
  'Show tier summary',
];

export default function QueryPanel() {
  const [query, setQuery]     = useState('');
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const runQuery = async (q) => {
    const text = q || query;
    if (!text.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await apiPost('/query', { query: text });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    runQuery();
  };

  return (
    <div style={{
      background:    'var(--surface)',
      border:        '1px solid var(--border)',
      borderRadius:  '8px',
      padding:       '20px',
    }}>
      <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '14px', marginBottom: '12px', color: 'var(--orange)' }}>
        QUERY ENGINE
      </h3>

      {/* Input form */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about fraud data..."
          style={{
            flex:         1,
            padding:      '8px 12px',
            background:   'var(--navy)',
            border:       '1px solid var(--border)',
            borderRadius: '4px',
            color:        'var(--text)',
            fontFamily:   'var(--font-mono)',
            fontSize:     '12px',
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding:      '8px 16px',
            background:   'var(--orange)',
            border:       'none',
            borderRadius: '4px',
            color:        '#fff',
            fontFamily:   'var(--font-mono)',
            fontSize:     '12px',
            cursor:       'pointer',
            opacity:      loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Querying...' : 'Ask'}
        </button>
      </form>

      {/* Example queries */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
        {EXAMPLE_QUERIES.map(q => (
          <button
            key={q}
            onClick={() => { setQuery(q); runQuery(q); }}
            style={{
              padding:      '4px 8px',
              background:   'transparent',
              border:       '1px solid var(--border)',
              borderRadius: '4px',
              color:        'var(--muted)',
              fontFamily:   'var(--font-mono)',
              fontSize:     '10px',
              cursor:       'pointer',
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Result */}
      {error && (
        <div style={{ color: 'var(--danger)', fontSize: '12px' }}>
          Error: {error}
        </div>
      )}

      {result && (
        <div style={{
          background:   'var(--navy)',
          border:       '1px solid var(--border)',
          borderRadius: '4px',
          padding:      '12px',
          fontSize:     '12px',
          lineHeight:   1.6,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', color: 'var(--muted)', fontSize: '10px' }}>
            <span>Source: {result.source}</span>
            <span>{result.response_ms}ms</span>
          </div>
          <div
            style={{ whiteSpace: 'pre-wrap', color: 'var(--text)' }}
            dangerouslySetInnerHTML={{
              __html: result.answer.replace(/\*\*(.*?)\*\*/g, '<strong style="color:var(--orange)">$1</strong>').replace(/\n/g, '<br>')
            }}
          />
        </div>
      )}
    </div>
  );
}
