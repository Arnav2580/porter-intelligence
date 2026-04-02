import React, { useState, useEffect, useRef } from 'react';
import { apiGet } from '../utils/api';
// Leaflet imports
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function ZoneMap() {
  const mapRef      = useRef(null);
  const leafletRef  = useRef(null);
  const markersRef  = useRef([]);
  const [mapMode, setMapMode] = useState('fraud');

  useEffect(() => {
    if (leafletRef.current) return;

    leafletRef.current = L.map('porter-map', {
      center:             [12.9716, 77.5946],
      zoom:               12,
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
        const endpoint = mapMode === 'fraud'
          ? `/fraud/heatmap`
          : `/efficiency/dead-miles`;

        const data = await apiGet(endpoint);

        // Clear existing markers
        markersRef.current.forEach(m => m.remove());
        markersRef.current = [];

        const map = leafletRef.current;
        if (!map) return;

        data.zones.forEach(zone => {
          const value = mapMode === 'fraud'
            ? zone.fraud_rate
            : (1 - (zone.dead_mile_rate || 0));

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
            {
              radius,
              color,
              fillColor:   color,
              fillOpacity: 0.25,
              weight:      1.5,
              opacity:     0.7,
            }
          ).addTo(map);

          const popupContent = mapMode === 'fraud'
            ? `Fraud rate: <span style="color: ${color}; font-weight: 700;">
                ${(zone.fraud_rate * 100).toFixed(1)}%
              </span><br>
              Cases: ${zone.fraud_count}<br>
              Risk: <span style="color: ${color}; font-weight: 700;">
                ${zone.risk_level}
              </span>`
            : `Efficiency: <span style="color: ${color}; font-weight: 700;">
                ${(value * 100).toFixed(1)}%
              </span><br>
              Dead miles: ${((1 - value) * 100).toFixed(1)}%<br>
              Cost/day: \u20B9${(zone.cost_inr_per_day || 0).toFixed(0)}`;

          circle.bindPopup(`
            <div style="
              font-family: 'DM Mono', monospace;
              background: #242438;
              color: #F0F0FF;
              border: 1px solid #2E2E4A;
              border-radius: 8px;
              padding: 12px;
              min-width: 160px;
            ">
              <div style="
                font-family: 'Syne', sans-serif;
                font-weight: 700;
                font-size: 14px;
                margin-bottom: 6px;
              ">${zone.zone_name}</div>
              <div style="font-size: 11px; color: #8888AA;">
                ${popupContent}
              </div>
            </div>
          `, { className: 'custom-popup' });

          markersRef.current.push(circle);
        });
      } catch(e) {}
    };

    if (leafletRef.current) {
      fetchHeatmap();
      const t = setInterval(fetchHeatmap, 30000);
      return () => clearInterval(t);
    }
  }, [mapMode]);

  const overlayTitle = mapMode === 'fraud'
    ? 'Bangalore Fraud Zones'
    : 'Fleet Efficiency Map';

  const legendItems = mapMode === 'fraud'
    ? [
        ['#EF4444', 'Critical  >12%'],
        ['#F59E0B', 'High      >8%'],
        ['#60A5FA', 'Medium    >4%'],
        ['#22C55E', 'Low       <4%'],
      ]
    : [
        ['#EF4444', 'Poor      <80%'],
        ['#F59E0B', 'Fair      <90%'],
        ['#60A5FA', 'Good      <95%'],
        ['#22C55E', 'Excellent >95%'],
      ];

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      <div id="porter-map" style={{ height: '100%', width: '100%' }} />
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
        <div style={{
          display: 'flex',
          gap: 4,
          marginTop: 8,
        }}>
          {['fraud', 'efficiency'].map(mode => (
            <button key={mode}
              onClick={() => setMapMode(mode)}
              style={{
                flex: 1,
                padding: '3px 0',
                fontSize: 9,
                fontFamily: 'var(--font-display)',
                fontWeight: 700,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                border: '1px solid',
                borderRadius: 3,
                cursor: 'pointer',
                background: mapMode === mode
                  ? 'var(--orange)' : 'transparent',
                color: mapMode === mode
                  ? 'white' : 'var(--muted)',
                borderColor: mapMode === mode
                  ? 'var(--orange)' : 'var(--border)',
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
