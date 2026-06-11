/**
 * Zentral API helper layer connecting to FastAPI backend.
 */

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  meta?: any;
}

// Token Storage Helpers
export const getAccessToken = () => typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
export const getRefreshToken = () => typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
export const setTokens = (accessToken: string, refreshToken?: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('access_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
  }
};
export const clearTokens = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
};

// Central fetch wrapper with automatic token management & interceptor logic
async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Set default headers
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  
  const token = getAccessToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  const response = await fetch(url, { ...options, headers });
  
  // Hande Token Expiration (401 Unauthorized) & Refresh
  if (response.status === 401 && endpoint !== '/auth/login' && endpoint !== '/auth/register') {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (refreshResponse.ok) {
          const refreshData = await refreshResponse.json();
          const newAccessToken = refreshData.data.access_token;
          setTokens(newAccessToken);
          
          // Retry original request with new token
          headers.set('Authorization', `Bearer ${newAccessToken}`);
          const retryResponse = await fetch(url, { ...options, headers });
          if (!retryResponse.ok) {
            const errJson = await retryResponse.json();
            throw new Error(errJson.error?.message || 'Request failed');
          }
          const retryJson = await retryResponse.json();
          return retryJson.data as T;
        }
      } catch (refreshErr) {
        clearTokens();
        if (typeof window !== 'undefined') {
          window.location.href = '/auth'; // Redirect to auth page on failure
        }
        throw new Error('Session expired');
      }
    }
    
    clearTokens();
    if (typeof window !== 'undefined') {
      window.location.href = '/auth';
    }
    throw new Error('Unauthorized');
  }
  
  if (!response.ok) {
    const errJson = await response.json().catch(() => ({}));
    throw new Error(errJson.error?.message || `Request failed with status ${response.status}`);
  }
  
  const json = await response.json();
  return json.data as T;
}

export const api = {
  // Authentication
  auth: {
    register: async (body: any) => apiFetch<any>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
    login: async (body: any) => {
      const data = await apiFetch<any>('/auth/login', { method: 'POST', body: JSON.stringify(body) });
      setTokens(data.access_token, data.refresh_token);
      return data.user;
    },
    me: async () => apiFetch<any>('/auth/me'),
  },
  
  // Portfolios
  portfolios: {
    list: async () => apiFetch<any[]>('/portfolios'),
    get: async (id: string) => apiFetch<any>(`/portfolios/${id}`),
    create: async (body: any) => apiFetch<any>('/portfolios', { method: 'POST', body: JSON.stringify(body) }),
    update: async (id: string, body: any) => apiFetch<any>(`/portfolios/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
    delete: async (id: string) => apiFetch<any>(`/portfolios/${id}`, { method: 'DELETE' }),
    uploadCsv: async (id: string, file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiFetch<any>(`/portfolios/${id}/upload-csv`, { method: 'POST', body: formData });
    }
  },
  
  // Holdings
  holdings: {
    add: async (portfolioId: string, body: any) => apiFetch<any>(`/portfolios/${portfolioId}/holdings`, { method: 'POST', body: JSON.stringify(body) }),
    update: async (portfolioId: string, holdingId: string, body: any) => apiFetch<any>(`/portfolios/${portfolioId}/holdings/${holdingId}`, { method: 'PUT', body: JSON.stringify(body) }),
    delete: async (portfolioId: string, holdingId: string) => apiFetch<any>(`/portfolios/${portfolioId}/holdings/${holdingId}`, { method: 'DELETE' }),
    bulk: async (portfolioId: string, holdings: any[], mode: 'merge' | 'replace') => apiFetch<any>(`/portfolios/${portfolioId}/holdings/bulk`, { method: 'POST', body: JSON.stringify({ holdings, mode }) }),
  },
  
  // Market Data
  marketData: {
    getQuote: async (ticker: string) => apiFetch<any>(`/market-data/quote/${ticker}`),
    getHistory: async (ticker: string, period?: string) => apiFetch<any>(`/market-data/history/${ticker}?period=${period || '1y'}`),
    getValuation: async (portfolioId: string, period?: string) => apiFetch<any>(`/portfolios/${portfolioId}/valuation?period=${period || '1y'}`),
    getReturns: async (portfolioId: string, period?: string) => apiFetch<any>(`/portfolios/${portfolioId}/returns?period=${period || '1y'}`),
  },
  
  // Risk
  risk: {
    getRisk: async (portfolioId: string, lookback?: number) => apiFetch<any>(`/portfolios/${portfolioId}/risk?lookback_days=${lookback || 252}`),
    getVaR: async (portfolioId: string, method?: string, confidence?: number, horizon?: number) => {
      return apiFetch<any>(`/portfolios/${portfolioId}/risk/var?method=${method || 'historical'}&confidence=${confidence || 0.95}&horizon_days=${horizon || 1}`);
    },
    getContributions: async (portfolioId: string) => apiFetch<any>(`/portfolios/${portfolioId}/risk/contributions`),
  },
  
  // Benchmark
  benchmark: {
    getComparison: async (portfolioId: string, lookback?: number) => apiFetch<any>(`/portfolios/${portfolioId}/benchmark?lookback_days=${lookback || 252}`),
    list: async () => apiFetch<any[]>('/benchmarks'),
  },
  
  // Health Score
  health: {
    getHealth: async (portfolioId: string) => apiFetch<any>(`/portfolios/${portfolioId}/health`),
    refresh: async (portfolioId: string) => apiFetch<any>(`/portfolios/${portfolioId}/health/refresh`, { method: 'POST' }),
  }
};
