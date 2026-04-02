export const getToken = () =>
  sessionStorage.getItem('porter_token')

export const setToken = (token, role, name) => {
  sessionStorage.setItem('porter_token', token)
  sessionStorage.setItem('porter_role', role)
  sessionStorage.setItem('porter_name', name)
}

export const clearToken = () => {
  sessionStorage.removeItem('porter_token')
  sessionStorage.removeItem('porter_role')
  sessionStorage.removeItem('porter_name')
}

export const isAuthenticated = () =>
  !!sessionStorage.getItem('porter_token')

export const getRole = () =>
  sessionStorage.getItem('porter_role')

export const getName = () =>
  sessionStorage.getItem('porter_name')
