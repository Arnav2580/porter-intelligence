# Dashboard UI

Management and analyst-facing React dashboard for Porter Intelligence Platform.

## Local Development

```bash
cd dashboard-ui
npm install
npm run dev
```

Local API default:

- `dashboard-ui/.env` points to `http://localhost:8000`

## Production Hosting

The dashboard is provider-agnostic.

- Set `VITE_API_BASE_URL` when the API is hosted on a different domain.
- Leave `VITE_API_BASE_URL` blank only when your hosting setup proxies API
  requests on the same origin.

Netlify config now lives at:

- `netlify.toml`

## Build

```bash
cd dashboard-ui
npm run build
```
