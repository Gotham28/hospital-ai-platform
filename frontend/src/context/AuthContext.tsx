import React, { createContext, useContext, useState, useCallback } from 'react';

interface AuthContextValue {
  isAuthenticated: boolean;
  // Call login(token) after a successful API response.
  // Stores the token in localStorage AND updates React state
  // in one atomic step — no reload needed.
  login: (token: string) => void;
  // Call logout() to clear the token and flip state.
  // React Router navigation happens in the caller (DashboardLayout)
  // so the context stays navigation-library-agnostic.
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Initialise from localStorage so a page refresh restores the session.
  // This is the only place we read localStorage for auth — everything else
  // reads from this state, which eliminates the stale-read bug in App.tsx.
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    () => !!localStorage.getItem('token')
  );

  const login = useCallback((token: string) => {
    localStorage.setItem('token', token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Typed hook — throws if used outside AuthProvider so mistakes surface fast.
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}