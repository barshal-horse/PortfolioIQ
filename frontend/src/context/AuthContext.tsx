'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { api, clearTokens, getAccessToken, setTokens } from '@/lib/api';

interface User {
  id: string;
  email: string;
  full_name: string;
  base_currency: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (body: any) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Test mode: auto-create and login a test user
const TEST_MODE = process.env.NEXT_PUBLIC_TEST_MODE === 'true';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      if (TEST_MODE) {
        // Auto-login test user in test mode
        try {
          // Try to register first (will fail if exists), then login
          await api.auth.register({
            email: 'test@portfolioiq.local',
            password: 'testpassword123',
            full_name: 'Test User',
          });
        } catch (err) {
          // User might already exist, ignore
        }
        try {
          const loggedUser = await api.auth.login({
            email: 'test@portfolioiq.local',
            password: 'testpassword123',
          });
          setUser(loggedUser);
        } catch (err) {
          console.error('Test mode login failed:', err);
        }
        setLoading(false);
        return;
      }

      const token = getAccessToken();
      if (token) {
        try {
          const userProfile = await api.auth.me();
          setUser(userProfile);
        } catch (err) {
          clearTokens();
          setUser(null);
        }
      }
      setLoading(false);
    }
    loadUser();
  }, []);

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      const loggedUser = await api.auth.login({ email, password });
      setUser(loggedUser);
    } catch (err) {
      setUser(null);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (body: any) => {
    setLoading(true);
    try {
      await api.auth.register(body);
      // Log in automatically after registration
      await login(body.email, body.password);
    } catch (err) {
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    clearTokens();
    setUser(null);
    if (typeof window !== 'undefined') {
      window.location.href = '/auth';
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
