import { useState } from 'react';
import { getToken, setToken, clearToken, getRole, getName, isAuthenticated } from '../utils/auth';

export function useAuth() {
  const [auth, setAuthState] = useState(() =>
    isAuthenticated()
      ? { token: getToken(), role: getRole(), name: getName() }
      : null,
  );

  const login = (token, role, name) => {
    setToken(token, role, name);
    setAuthState({ token, role, name });
  };

  const logout = () => {
    clearToken();
    setAuthState(null);
  };

  return { auth, login, logout, isAuthenticated };
}
