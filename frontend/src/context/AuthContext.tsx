import React, { createContext, useContext, useState, useCallback } from 'react';

interface AuthContextValue {
  isAuthenticated: boolean;
  role: string;
  hospitalId: number | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeToken(token: string): { role: string; hospital_id: number | null } {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return { role: payload.role ?? 'staff', hospital_id: payload.hospital_id ?? null };
  } catch {
    return { role: 'staff', hospital_id: null };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const existingToken = localStorage.getItem('token');
  const existingDecoded = existingToken ? decodeToken(existingToken) : null;

  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!existingToken);
  const [role, setRole] = useState<string>(existingDecoded?.role ?? 'staff');
  const [hospitalId, setHospitalId] = useState<number | null>(existingDecoded?.hospital_id ?? null);

  const login = useCallback((token: string) => {
    localStorage.setItem('token', token);
    const decoded = decodeToken(token);
    
    setIsAuthenticated(true);
    setRole(decoded.role);
    setHospitalId(decoded.hospital_id);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setRole('staff');
    setHospitalId(null);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, role, hospitalId, login, logout }}>
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