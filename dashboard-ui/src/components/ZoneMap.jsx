import React, { useState, useEffect, useRef } from 'react';
import { apiGet } from '../utils/api';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function ZoneMap() {
  const mapRef      = useRef(null);
  const leafletRef  = useRef(null);
  const markersRef  = useRef([]);
  const [mapMode, setMapMode] = useState('fraud');
  const [error, setError]     = useState(false);
  const [zoneCount, setZoneCount] = useState(0);

  useEffect(() => {
    if (leafletRef.current) return;

    // Start at India level — auto-fit will zoom to data
    leafletRef.current = L.map('porter-map', {
      center:             [20.5937, 78.9629],
      zoom:               5,
      zoomControl:        true,
      attributionControl: false,
    });

    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { subdomains: 'abcd', maxZoom: 19 }
    ).addTo(leafletRef.current);
  }, []);

  useEffect(() => {
    const fetchHeatmap = async () => {
      try {
        // fleet-zones has 35 zones / 12 cities vs dead-miles 24 zones / 3 cities
        const endpoint = mapMode === 'fraud'
          ? '/fraud/heatmap'
          : '/efficiency/fleet-zones';

        const data = await apiGet(endpoint);
        setError(false);

        // Clear existing markers
        markersRef.current.forEach(m => m.remove());
        markersRef.current = [];

        const map = leafletRef.current;
        if (!map || !data.zones?.length) return;

        const bounds = [];

        data.zones.forEach(zone => {
          // fleet-zones: dead_mile_pct is 0-100; dead-miles: dead_mile_rate is 0-1
          const deadMileRate = zone.dead_mile_rate ?? (zone.dead_mile_pct ?? 0) / 100;
          const zoneName     = zone.zone_name ?? zone.city ?? zone.zone_id;

          const value = mapMode === 'fraud'
            ? zone.fraud_rate
            : (1 - deadMileRate);

          const color = mapMode === 'fraud'
            ? (zone.risk_level === 'CRITICAL' ? '#EF4444' :
               zone.risk_level === 'HIGH'     ? '#F59E0B' :
               zone.risk_level === 'MEDIUM'   ? '#60A5FA' : '#22C55E')
            : (value < 0.80 ? '#EF4444' :
               value < 0.90 ? '#F59E0B' :
               value < 0.95 ? '#60A5FA' : '#22C55E');

          const radius = mapMode === 'fraud'
            ? 400 + zone.fraud_rate * 3000
            : 400 + (1 - value) * 3000;

          const circle = L.circle(
            [zone.lat, zone.lon],
            { radius, color, fillColor: color, fillOpacity: 0.25, weight: 1.5, opacity: 0.7 }
          ).addTo(map);

          const fleetDetail = zone.active_drivers != null
            ? `Active: ${zone.active_drivers} · Idle: ${zone.idle_drivers}`
            : `Cost/day: ₹${(zone.cost_inr_per_day || 0).toFixed(0)}`;

          const popupContent = mapMode === 'fraud'
            ? `Fraud rate: <span style="color:${color};font-weight:700">${(zone.fraud_rate*100).toFixed(1)}%</span><br>
               Cases: ${zone.fraud_count}<br>
               Risk: <span style="color:${color};font-weight:700">${zone.risk_level}</span>`
            : `Efficiency: <span style="color:${color};font-weight:700">${(value*100).toFixed(1)}%</span><br>
               Dead miles: ${(deadMileRate*100).toFixed(1)}%<br>
               ${fleetDetail}`;

          circle.bindPopup(`
            <div style="font-family:'DM Mono',monospace;background:#242438;color:#F0F0FF;
                        border:1px solid #2E2E4A;border-radius:8px;padding:12px;min-width:160px">
              <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:6px">
                ${zoneName}
              </div>
              <div style="font-size:11px;color:#8888AA">${popupContent}</div>
            </div>
          `, { className: 'custom-popup' });

          markersRef.current.push(circle);
          bounds.push([zone.lat, zone.lon]);
        });

        // Auto-fit map to all zones that have data — shows all cities, not just Bangalore
        if (bounds.length > 0) {
          map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 12 });
        }

        setZoneCount(bounds.length);
      } catch(e) {
        setError(true);
      }
    };

    if (leafletRef.current) {
      fetchHeatmap();
      const t = setInterval(fetchHeatmap, 30000);
      return () => clearInterval(t);
    }
  }, [mapMode]);

  const overlayTitle = mapMode === 'fraud'
    ? `Fraud Heatmap${zoneCount > 0 ? ` · ${zoneCount} zones` : ''}`
    : 'Fleet Efficiency Map';

  const legendItems = mapMode === 'fraud'
    ? [['#EF4444','Critical >12%'],['#F59E0B','High >8%'],['#60A5FA','Medium >4%'],['#22C55E','Low <4%']]
    : [['#EF4444','Poor <80%'],['#F59E0B','Fair <90%'],['#60A5FA','Good <95%'],['#22C55E','Excellent >95%']];

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      <div id="porter-map" style={{ height: '100%', width: '100%' }} />

      {error && (
        <div style={{
          position: 'absolute', top: 8, left: 8, right: 8,
          background: 'rgba(239,68,68,0.12)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 6, padding: '8px 12px',
          fontSize: 11, color: 'var(--danger)',
          fontFamily: 'var(--font-mono)', zIndex: 1000,
        }}>
          Heatmap unavailable — API offline or trip data not loaded
        </div>
      )}

      <div className="map-overlay">
        <div className="map-overlay-title">{overlayTitle}</div>
        <div className="map-legend">
          {legendItems.map(([c, l]) => (
            <div key={l} className="map-legend-item">
              <div className="map-legend-dot" style={{ background: c }} />
              {l}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
          {['fraud', 'efficiency'].map(mode => (
            <button key={mode}
              onClick={() => setMapMode(mode)}
              style={{
                flex: 1, padding: '3px 0', fontSize: 9,
                fontFamily: 'var(--font-display)', fontWeight: 700,
                letterSpacing: '0.05em', textTransform: 'uppercase',
                border: '1px solid', borderRadius: 3, cursor: 'pointer',
                background: mapMode === mode ? 'var(--orange)' : 'transparent',
                color: mapMode === mode ? 'white' : 'var(--muted)',
                borderColor: mapMode === mode ? 'var(--orange)' : 'var(--border)',
                transition: 'all 0.15s',
              }}>
              {mode === 'fraud' ? 'Fraud' : 'Fleet'}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
