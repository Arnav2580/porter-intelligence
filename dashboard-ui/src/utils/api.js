/**
 * api.js — Porter Intelligence API client
 *
 * Rules (enterprise deal — no fake data):
 * 1. Viewer credential comes from VITE_VIEWER_PASSWORD env var — never hardcoded.
 * 2. API offline → components show empty state / offline banner.
 *    Never redirect to /login because of a network failure.
 * 3. 401 on a named analyst/admin session → redirect to /login.
 * 4. 401 on a viewer auto-session → re-mint viewer token, never redirect.
 * 5. 403 → throw so caller can show "access denied" state.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim() || '/api'
const VIEWER_PASSWORD = import.meta.env.VITE_VIEWER_PASSWORD || ''

const PROXY_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
}

/** Read token from sessionStorage using the canonical key. */
const getToken = () => sessionStorage.getItem('porter_token')
const getRole  = () => sessionStorage.getItem('porter_role')

// In-flight viewer token mint — prevents parallel mints
let _mintInFlight = null

/**
 * Mint a viewer token using VITE_VIEWER_PASSWORD.
 * Only called when no token exists AND the viewer password is configured.
 * Returns null if viewer password is not set (honest empty state).
 */
async function mintViewerToken() {
  if (!VIEWER_PASSWORD) return null
  if (_mintInFlight) return _mintInFlight

  _mintInFlight = (async () => {
    try {
      const form = new URLSearchParams()
      form.append('username', 'viewer')
      form.append('password', VIEWER_PASSWORD)
      const res = await fetch(`${BASE_URL}/auth/token`, {
        method: 'POST',
        headers: { ...PROXY_HEADERS, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      })
      if (!res.ok) return null
      const data = await res.json()
      if (!data.access_token) return null
      sessionStorage.setItem('porter_token', data.access_token)
      sessionStorage.setItem('porter_role', data.role || 'read_only')
      sessionStorage.setItem('porter_name', data.name || 'Viewer')
      return data.access_token
    } catch {
      return null
    } finally {
      _mintInFlight = null
    }
  })()

  return _mintInFlight
}

/**
 * Get a valid token for requests.
 * - Named session (analyst/admin/ops_manager): return stored token.
 * - No token and viewer password configured: auto-mint viewer token.
 * - No token and no viewer password: return null (caller gets 401 → throws).
 */
async function getOrEnsureToken() {
  const existing = getToken()
  if (existing) return existing
  return mintViewerToken()
}

/**
 * Handle a 401 response.
 * - Named (non-viewer) session expired → redirect to login.
 * - Viewer session → try to re-mint. If mint fails, throw.
 */
async function handle401() {
  const role = getRole()
  const isViewer = role === 'read_only' || role === 'viewer'

  sessionStorage.removeItem('porter_token')
  sessionStorage.removeItem('porter_role')
  sessionStorage.removeItem('porter_name')

  if (isViewer || !role) {
    // For viewer/anonymous sessions: try to re-mint
    const newToken = await mintViewerToken()
    if (newToken) return newToken
    // Viewer password not set or API down — just throw, don't redirect
    return null
  }

  // Named analyst/admin session: token expired → redirect to login
  window.location.href = '/login?reason=session_expired'
  return null
}

export async function apiGet(path) {
  const token = await getOrEnsureToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      ...PROXY_HEADERS,
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  })
  if (res.status === 401) {
    await handle401()
    throw new Error('API error: 401 Unauthorized')
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiPost(path, body) {
  const token = await getOrEnsureToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  if (res.status === 401) {
    await handle401()
    throw new Error('API error: 401 Unauthorized')
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiFormPost(path, formData) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `API error: ${res.status}`)
  }
  return res.json()
}

export async function apiGetRaw(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { ...PROXY_HEADERS },
    signal: AbortSignal.timeout(15000),
  })
  return res
}

export async function apiPatch(path, body) {
  const token = await getOrEnsureToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  if (res.status === 401) {
    await handle401()
    throw new Error('API error: 401 Unauthorized')
  }
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}))
    throw new Error(errBody.detail || `API error: ${res.status}`)
  }
  return res.json()
}
