# 06 — Frontend And Dashboard

[Index](./README.md) | [Prev: Ingestion](./05-ingestion-and-shadow-mode.md) | [Next: Security](./07-security-and-auth.md)

This document explains the React frontend application: how it is structured, what each page does, and how it communicates with the API.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| Vite | Latest | Build tool and dev server |
| React Router | v6 | Client-side routing |
| Leaflet.js | Latest | Fraud heatmap and zone map |
| Native fetch | — | API communication (no axios) |

**Important:** This project uses native `fetch()` for all API calls. Do not install axios.

---

## Project Structure

```
dashboard-ui/
├── src/
│   ├── pages/
│   │   ├── Dashboard.jsx     # Management dashboard (home page)
│   │   └── Analyst.jsx       # Analyst case review workspace
│   ├── components/
│   │   ├── KPIPanel.jsx      # KPI cards (open cases, recoverable, fraud rate)
│   │   ├── ZoneMap.jsx       # Leaflet fraud heatmap
│   │   ├── TripScorer.jsx    # Manual trip scoring form
│   │   ├── ROICalculator.jsx # ROI scenario calculator
│   │   ├── QueryPanel.jsx    # Natural language query interface
│   │   ├── FraudFeed.jsx     # Live fraud activity feed
│   │   ├── DriverIntelligence.jsx  # Driver risk profile viewer
│   │   ├── TierSummaryBar.jsx      # Two-stage tier summary
│   │   ├── ReallocationPanel.jsx   # Fleet reallocation suggestions
│   │   └── Clock.jsx         # Live clock display
│   ├── hooks/
│   │   └── useAuth.js        # Authentication hook
│   ├── utils/
│   │   ├── api.js            # API helper functions
│   │   └── auth.js           # Auth utilities
│   └── index.css             # Global styles
├── public/
├── .env.production           # Production API URL
├── package.json
└── vite.config.js
```

---

## Pages

### Dashboard (`Dashboard.jsx`)

The management dashboard is the home page. It provides a high-level overview of platform status and fraud activity.

**Components displayed:**
1. **Health check**: Verifies API connectivity on load. Shows offline screen if API unreachable.
2. **KPI Panel**: Open cases, recoverable value, fraud rate, model status
3. **Zone Map**: Leaflet-based fraud heatmap with zone-level risk colors
4. **Tier Summary Bar**: Action/watchlist/clear distribution
5. **ROI Calculator**: Interactive ROI scenario planner
6. **Trip Scorer**: Manual trip scoring form (paste trip data, get fraud score)
7. **Fraud Feed**: Live stream of recent fraud-flagged trips
8. **Query Panel**: Natural language query interface
9. **Driver Intelligence**: Driver risk profile lookup
10. **Reallocation Panel**: Fleet efficiency suggestions

**Data flow:**
- On mount: calls `GET /health` to verify API
- If API online: renders all components, each fetching their own data
- If API offline: shows retry screen with connection instructions

### Analyst (`Analyst.jsx`)

The analyst workspace is the case review interface. This is where fraud analysts review, decide, and act on cases.

**Features:**
- **Login gate**: Requires JWT authentication before showing content
- **Case queue**: Filterable list of fraud cases (by status, tier, zone)
- **Case detail view**: Opens case with full evidence:
  - Trip information (fare, distance, zone, vehicle type)
  - Fraud signals (top 3 contributing features)
  - Driver snapshot (risk score, ring membership)
  - Case age and tier
- **Decision actions**:
  - Mark Under Review
  - Confirm Fraud
  - Mark False Alarm (requires override reason for action-tier cases)
  - Escalate
- **Driver actions** (from case context):
  - Suspend Driver
  - Flag for Review
  - Monitor Driver
  - Clear Driver
- **Case history timeline**: All status changes and driver actions with timestamps

**Zone options available for filtering:** 24 zones across Bangalore, Mumbai, and Delhi NCR.

---

## API Communication

### API helpers (`utils/api.js`)

All API calls go through helper functions in `api.js`:

| Function | HTTP Method | Content-Type | Auth |
|---|---|---|---|
| `apiGet(path)` | GET | — | Bearer token |
| `apiPost(path, body)` | POST | application/json | Bearer token |
| `apiPatch(path, body)` | PATCH | application/json | Bearer token |
| `apiFormPost(path, formData)` | POST | x-www-form-urlencoded | None |
| `apiGetRaw(path)` | GET | — | None (3s timeout) |

### Base URL resolution

```javascript
const BASE_URL = envBaseUrl || (isLocalBrowser ? 'http://localhost:8000' : '')
```

- In development: defaults to `http://localhost:8000`
- In production: uses `VITE_API_BASE_URL` from `.env.production`
- When deployed (non-localhost): uses relative URLs (same origin)

### Token management

- JWT tokens stored in `sessionStorage` (cleared on tab close)
- Token key: `porter_token`
- On 401 response: sessionStorage cleared, redirect to `/login`
- Token sent as `Authorization: Bearer <token>` header

### Error handling

All API helpers throw on non-2xx responses. Components catch errors and display inline error states. 401 errors trigger automatic logout and redirect.

---

## Authentication Flow

1. User navigates to `/analyst`
2. If no token in sessionStorage: show login form
3. User enters username + password
4. `apiFormPost('/auth/token', formData)` sends credentials
5. On success: store token in sessionStorage, show workspace
6. On failure: show error message
7. `useAuth` hook provides current user state to all components

---

## Styling

### Design system

The dashboard uses CSS custom properties defined in `index.css`:

| Variable | Purpose |
|---|---|
| `--navy` | Background color (dark navy) |
| `--text` | Primary text color |
| `--muted` | Secondary text color |
| `--orange` | Accent color (Porter orange) |
| `--danger` | Red for critical/action tier |
| `--warning` | Amber for watchlist tier |
| `--success` | Green for clear tier |
| `--border` | Border and divider color |
| `--font-display` | Heading font family |
| `--font-mono` | Monospace font for data |

### Responsive design

The dashboard is designed for desktop screens (1280px+). Components use CSS Grid and Flexbox for layout.

---

## Running The Frontend

### Development

```bash
cd dashboard-ui
npm install
npm run dev
```

Opens at `http://localhost:3000`. Hot-reloads on file changes.

### Production build

```bash
npm run build
```

Output goes to `dashboard-ui/dist/`. Can be served by any static file server or the FastAPI backend itself (configured to serve from `/` endpoint).

### Environment variables

| Variable | File | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `.env.production` | API base URL for production builds |

---

## Component Data Flow

```
Dashboard.jsx
    │
    ├── GET /health ────────────────────────→ Health status
    │
    ├── KPIPanel.jsx
    │   └── GET /kpi/live ──────────────────→ Live KPI metrics
    │
    ├── ZoneMap.jsx
    │   └── GET /fraud/heatmap ─────────────→ Zone fraud rates + coordinates
    │
    ├── TripScorer.jsx
    │   └── POST /fraud/score ──────────────→ Single trip scoring
    │
    ├── ROICalculator.jsx
    │   └── POST /roi/calculate ────────────→ ROI scenarios
    │
    ├── QueryPanel.jsx
    │   └── POST /query ────────────────────→ Natural language answer
    │
    ├── FraudFeed.jsx
    │   └── GET /fraud/live-feed ───────────→ Recent flagged trips
    │
    └── DriverIntelligence.jsx
        └── GET /driver-intelligence/{id} ──→ Driver profile

Analyst.jsx
    │
    ├── POST /auth/token ───────────────────→ JWT login
    ├── GET /cases/?status=&tier=&zone= ────→ Case queue
    ├── GET /cases/{id} ────────────────────→ Case detail
    ├── GET /cases/{id}/history ────────────→ Case timeline
    ├── PATCH /cases/{id} ──────────────────→ Status update
    └── POST /cases/{id}/driver-action ─────→ Driver enforcement
```

---

## Next

- [Security and Auth](./07-security-and-auth.md) — encryption, JWT, RBAC, audit logging
- [Deployment and Infrastructure](./08-deployment-and-infrastructure.md) — Docker, AWS, monitoring
