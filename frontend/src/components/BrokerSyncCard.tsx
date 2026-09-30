'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Loader2, Link2, Link2Off, RefreshCw, CheckCircle2 } from 'lucide-react';

interface BrokerSyncCardProps {
  portfolioId: string;
  onSynced: () => void;
}

interface Status {
  broker: string;
  account_number: string | null;
  status: string | null;
  last_sync_at: string | null;
}

export default function BrokerSyncCard({ portfolioId, onSynced }: BrokerSyncCardProps) {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [showConnect, setShowConnect] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [busy, setBusy] = useState<'connect' | 'sync' | 'disconnect' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const s = await api.broker.getStatus();
      setStatus(s);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy('connect');
    setError(null);
    setNotice(null);
    try {
      await api.broker.connect(apiKey.trim(), apiSecret.trim());
      setNotice('Alpaca account connected.');
      setApiKey('');
      setApiSecret('');
      setShowConnect(false);
      await loadStatus();
    } catch (err: any) {
      setError(err?.message || 'Connection failed — check the keys');
    } finally {
      setBusy(null);
    }
  };

  const handleSync = async () => {
    setBusy('sync');
    setError(null);
    setNotice(null);
    try {
      const res = await api.broker.syncToPortfolio(portfolioId, 'merge');
      setNotice(
        res.synced > 0
          ? `Synced ${res.synced} positions (${res.added} added, ${res.updated} updated).`
          : 'No open positions at the broker to sync.'
      );
      onSynced();
      await loadStatus();
    } catch (err: any) {
      setError(err?.message || 'Sync failed');
    } finally {
      setBusy(null);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect your Alpaca account?')) return;
    setBusy('disconnect');
    try {
      await api.broker.disconnect();
      setStatus(null);
      setNotice('Broker disconnected.');
    } catch (err: any) {
      setError(err?.message || 'Disconnect failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-6 border border-brand-border">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-brand-cyan/10 rounded-xl">
            <Link2 className="h-5 w-5 text-brand-cyan" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">Broker Sync</h3>
            <p className="text-xs text-slate-500">Import holdings from Alpaca (paper or live)</p>
          </div>
        </div>

        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
        ) : status ? (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSync}
              disabled={busy !== null}
              className="flex items-center space-x-1.5 bg-brand-cyan/15 hover:bg-brand-cyan/25 text-brand-cyan border border-brand-cyan/30 rounded-xl px-3 py-2 text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {busy === 'sync' ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Sync Now
            </button>
            <button
              onClick={handleDisconnect}
              disabled={busy !== null}
              className="p-2 text-slate-600 hover:text-brand-red rounded-lg hover:bg-brand-red/10 transition-colors cursor-pointer"
              title="Disconnect broker"
            >
              <Link2Off className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowConnect((s) => !s)}
            className="bg-brand-card border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 rounded-xl px-3 py-2 text-xs font-semibold cursor-pointer"
          >
            {showConnect ? 'Cancel' : 'Connect Alpaca'}
          </button>
        )}
      </div>

      {status && (
        <div className="flex items-center space-x-2 text-xs text-slate-400">
          <CheckCircle2 className="h-3.5 w-3.5 text-brand-green" />
          <span className="font-mono">{status.broker}</span>
          {status.account_number && <span>· #{status.account_number}</span>}
          {status.status && <span className="capitalize">· {status.status}</span>}
          {status.last_sync_at && (
            <span className="text-slate-600">
              · last sync {new Date(status.last_sync_at).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {showConnect && !status && (
        <form onSubmit={handleConnect} className="mt-4 space-y-3">
          <input
            type="text"
            required
            placeholder="Alpaca API Key ID"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-xs font-mono"
          />
          <input
            type="password"
            required
            placeholder="Alpaca Secret Key"
            value={apiSecret}
            onChange={(e) => setApiSecret(e.target.value)}
            className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-xs font-mono"
          />
          <p className="text-[10px] text-slate-600">
            Free paper-trading keys at app.alpaca.markets. Keys are stored per-user on the server.
          </p>
          <button
            type="submit"
            disabled={busy !== null}
            className="w-full bg-brand-cyan hover:bg-brand-cyan/90 text-brand-bg font-semibold rounded-lg py-2 text-xs cursor-pointer disabled:opacity-50 flex items-center justify-center"
          >
            {busy === 'connect' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Connect Account'}
          </button>
        </form>
      )}

      {notice && (
        <div className="mt-3 p-2.5 bg-brand-green/10 border border-brand-green/25 rounded-lg text-brand-green text-xs">
          {notice}
        </div>
      )}
      {error && (
        <div className="mt-3 p-2.5 bg-brand-red/10 border border-brand-red/25 rounded-lg text-brand-red text-xs">
          {error}
        </div>
      )}
    </div>
  );
}
