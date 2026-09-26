import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, tokenStore } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    const onExpired = () => {
      setSessionExpired(true);
      setUser(null);
    };
    window.addEventListener('acm:session-expired', onExpired);
    return () => window.removeEventListener('acm:session-expired', onExpired);
  }, []);

  useEffect(() => {
    let active = true;
    const token = tokenStore.get();
    if (!token) {
      setLoading(false);
      return () => { active = false; };
    }
    api.me().then((profile) => {
      if (active) setUser(profile);
    }).catch(() => {
      if (active) {
        tokenStore.clear();
        setUser(null);
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const login = useCallback(async (email, password) => {
    const response = await api.login({ email, password });
    if (!response.access_token || !response.user) throw new Error('Sign in could not be completed.');
    tokenStore.set(response.access_token);
    setUser(response.user);
    setSessionExpired(false);
    return response.user;
  }, []);

  const updateLanguage = useCallback(async (language) => {
    const response = await api.selectLanguage(language);
    setUser((current) => response.user ? { ...current, ...response.user } : current);
    return response.user;
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, sessionExpired, updateLanguage }), [user, loading, login, logout, sessionExpired, updateLanguage]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
