const BASE_URL = import.meta.env.VITE_API_BASE_URL
                 || 'http://localhost:8000'

const getToken = () =>
  sessionStorage.getItem('porter_token')

export async function apiGet(path) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
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
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
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
    signal: AbortSignal.timeout(3000)
  })
  return res
}

export async function apiPatch(path, body) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
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
