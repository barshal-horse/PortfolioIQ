/**
 * Zentral API helper layer connecting to FastAPI backend.
 */

const API_BASE_URL = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000/api/v1';

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
  },

  // Stress Testing
  stress_testing: {
    runStressTest: async (portfolioId: string, body: any) => apiFetch<any>(`/portfolios/${portfolioId}/stress-test`, { method: 'POST', body: JSON.stringify(body) }),
    listScenarios: async () => apiFetch<any[]>('/stress-test/scenarios'),
    getHistory: async (portfolioId: string, limit?: number) => apiFetch<any[]>(`/portfolios/${portfolioId}/stress-test/history?limit=${limit || 20}`),
  },

  // Optimization
  optimization: {
    optimize: async (portfolioId: string, body: any) => apiFetch<any>(`/portfolios/${portfolioId}/optimize`, { method: 'POST', body: JSON.stringify(body) }),
    optimizeBlackLitterman: async (portfolioId: string, body: any) => apiFetch<any>(`/portfolios/${portfolioId}/optimize/black-litterman`, { method: 'POST', body: JSON.stringify(body) }),
    getHistory: async (portfolioId: string, limit?: number) => apiFetch<any[]>(`/portfolios/${portfolioId}/optimize/history?limit=${limit || 10}`),
  },

  // Copilot (Phase 10)
  copilot: {
    createSession: async (portfolioId?: string, title?: string) =>
      apiFetch<any>('/copilot/sessions', { method: 'POST', body: JSON.stringify({ portfolio_id: portfolioId || null, title }) }),
    listSessions: async () => apiFetch<any[]>('/copilot/sessions'),
    getSession: async (sessionId: string) => apiFetch<any>(`/copilot/sessions/${sessionId}`),
    deleteSession: async (sessionId: string) => apiFetch<any>(`/copilot/sessions/${sessionId}`, { method: 'DELETE' }),
    getMessages: async (sessionId: string, limit?: number) =>
      apiFetch<any>(`/copilot/sessions/${sessionId}/messages?limit=${limit || 50}`),
    sendMessage: async (sessionId: string, content: string) =>
      apiFetch<any>(`/copilot/sessions/${sessionId}/messages`, { method: 'POST', body: JSON.stringify({ content }) }),
  },

  // News Intelligence (Phase 11)
  news: {
    getPortfolioNews: async (portfolioId: string, days?: number, limit?: number) =>
      apiFetch<any[]>(`/news/portfolio/${portfolioId}?days=${days || 7}&limit=${limit || 50}`),
    getTickerNews: async (ticker: string, days?: number, limit?: number) =>
      apiFetch<any[]>(`/news/ticker/${ticker}?days=${days || 7}&limit=${limit || 20}`),
    refreshPortfolioNews: async (portfolioId: string, days?: number) =>
      apiFetch<any>(`/news/portfolio/${portfolioId}/refresh?days=${days || 7}`, { method: 'POST' }),
    getTickerSentiment: async (ticker: string, days?: number) =>
      apiFetch<any>(`/news/sentiment/ticker/${ticker}?days=${days || 7}`),
    getPortfolioSentiment: async (portfolioId: string, days?: number) =>
      apiFetch<any[]>(`/news/sentiment/portfolio/${portfolioId}?days=${days || 7}`),
    processSentiment: async (limit?: number) =>
      apiFetch<any>(`/news/sentiment/process?limit=${limit || 100}`, { method: 'POST' }),
    getEarningsCalendar: async (portfolioId: string, daysAhead?: number) =>
      apiFetch<any[]>(`/news/earnings/portfolio/${portfolioId}?days_ahead=${daysAhead || 30}`),
  },

  // Reports (Phase 12)
  reports: {
    generate: async (portfolioId: string, reportType: string, parameters?: any) =>
      apiFetch<any>(`/reports/generate?portfolio_id=${portfolioId}`, { method: 'POST', body: JSON.stringify({ report_type: reportType, parameters: parameters || {} }) }),
    list: async (portfolioId?: string, statusFilter?: string) => {
      const params = new URLSearchParams();
      if (portfolioId) params.set('portfolio_id', portfolioId);
      if (statusFilter) params.set('status_filter', statusFilter);
      const qs = params.toString();
      return apiFetch<any[]>(`/reports${qs ? `?${qs}` : ''}`);
    },
    get: async (reportId: string) => apiFetch<any>(`/reports/${reportId}`),
    getStatus: async (reportId: string) => apiFetch<any>(`/reports/${reportId}/status`),
    delete: async (reportId: string) => apiFetch<any>(`/reports/${reportId}`, { method: 'DELETE' }),
    // Authenticated download — returns object URL for the PDF blob
    download: async (reportId: string): Promise<string> => {
      const token = getAccessToken();
      const response = await fetch(`${API_BASE_URL}/reports/${reportId}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Download failed (${response.status})`);
      }
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    },
  },

  // Broker Sync (Alpaca)
  broker: {
    getStatus: async () => apiFetch<any>('/broker/status'),
    connect: async (apiKey: string, apiSecret: string) =>
      apiFetch<any>('/broker/connect', { method: 'POST', body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }) }),
    disconnect: async () => apiFetch<any>('/broker/disconnect', { method: 'POST' }),
    getPositions: async () => apiFetch<any[]>('/broker/positions'),
    getAccount: async () => apiFetch<any>('/broker/account'),
    syncToPortfolio: async (portfolioId: string, mode: 'merge' | 'replace') =>
      apiFetch<any>(`/broker/sync/${portfolioId}?mode=${mode}`, { method: 'POST' }),
  },

  // Ticker Search (autocomplete)
  search: {
    tickers: async (query: string, limit?: number) =>
      apiFetch<any[]>(`/market-data/search?q=${encodeURIComponent(query)}&limit=${limit || 8}`),
    getQuote: async (ticker: string) => apiFetch<any>(`/market-data/quote/${ticker}`),
  },
};

/**
 * Stream a Copilot response via SSE. Returns an unsubscribe function.
 * Events: {type: 'token'|'citation'|'done'|'error', ...}
 */
export function streamCopilotMessage(
  sessionId: string,
  content: string,
  handlers: {
    onToken?: (chunk: string) => void;
    onCitation?: (citation: any) => void;
    onDone?: (messageId: string) => void;
    onError?: (message: string) => void;
  }
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const token = getAccessToken();
      const response = await fetch(`${API_BASE_URL}/copilot/sessions/${sessionId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        handlers.onError?.(`Stream failed (${response.status})`);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by double newlines
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          const line = frame.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'token') handlers.onToken?.(event.content);
            else if (event.type === 'citation') handlers.onCitation?.(event.citation);
            else if (event.type === 'done') handlers.onDone?.(event.message_id);
            else if (event.type === 'error') handlers.onError?.(event.message);
          } catch {
            // ignore malformed frame
          }
        }
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        handlers.onError?.(err?.message || 'Stream failed');
      }
    }
  })();

  return () => controller.abort();
}

