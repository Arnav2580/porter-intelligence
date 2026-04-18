const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim() || '/api'

const getToken = () =>
  sessionStorage.getItem('porter_token')

const PROXY_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
}

export async function apiGet(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      ...PROXY_HEADERS,
      'Authorization': `Bearer ${getToken()}`
    }
  })
  if (res.status === 401) {
    sessionStorage.clear()
    window.location.href = '/login'
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiPost(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify(body)
  })
  if (res.status === 401) {
    sessionStorage.clear()
    window.location.href = '/login'
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiFormPost(path, formData) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/x-www-form-urlencoded'
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
    signal: AbortSignal.timeout(15000)
  })
  return res
}

export async function apiPatch(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
      ...PROXY_HEADERS,
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify(body)
  })
  if (res.status === 401) {
    sessionStorage.clear()
    window.location.href = '/login'
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `API error: ${res.status}`)
  }
  return res.json()
}
