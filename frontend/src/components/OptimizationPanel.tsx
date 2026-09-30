'use client';

import React, { useState } from 'react';
import { api } from '@/lib/api';
import {
  Target,
  Loader2,
  TrendingUp,
  ShieldCheck,
  Zap,
  BarChart3,
} from 'lucide-react';

interface OptimizationPanelProps {
  portfolioId: string;
}

const METHODS = [
  { value: 'max_sharpe', label: 'Max Sharpe', description: 'Best risk-adjusted return' },
  { value: 'min_volatility', label: 'Min Volatility', description: 'Lowest possible risk' },
  { value: 'max_utility', label: 'Max Utility', description: 'Balanced return/risk preference' },
  { value: 'risk_parity', label: 'Risk Parity', description: 'Equal risk from every holding' },
];

interface OptimizeResult {
  optimal_allocation: Record<string, number>;
  expected_metrics: {
    expected_return: number;
    expected_volatility: number;
    expected_sharpe: number;
  };
  trades: Array<{
    ticker: string;
    action: string;
    current_weight: number;
    optimal_weight: number;
    delta_weight: number;
  }>;
}

export default function OptimizationPanel({ portfolioId }: OptimizationPanelProps) {
  const [method, setMethod] = useState('max_sharpe');
  const [minWeight, setMinWeight] = useState(0);
  const [maxWeight, setMaxWeight] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runOptimization = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.optimization.optimize(portfolioId, {
        method,
        constraints: { min_weight: minWeight, max_weight: maxWeight },
        lookback_days: 252,
        risk_free_rate: 0.05,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || 'Optimization failed');
    } finally {
      setLoading(false);
    }
  };

  const formatPct = (v: number | null | undefined) =>
    v === null || v === undefined ? '—' : `${(v * 100).toFixed(2)}%`;

  const trades = result?.trades?.filter((t) => Math.abs(t.delta_weight) > 0.001) || [];

  return (
    <div className="space-y-6">
      {/* Method selection */}
      <div className="glass-card rounded-2xl p-6 border border-brand-border">
        <div className="flex items-center space-x-3 mb-5">
          <div className="p-2.5 bg-brand-cyan/10 rounded-xl">
            <Target className="h-5 w-5 text-brand-cyan" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100">Portfolio Optimization</h3>
            <p className="text-sm text-slate-400">
              Institutional mean-variance methods (PyPortfolioOpt, Ledoit-Wolf covariance)
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          {METHODS.map((m) => (
            <button
              key={m.value}
              onClick={() => setMethod(m.value)}
              className={`text-left p-4 rounded-xl border-2 cursor-pointer transition-all ${
                method === m.value
                  ? 'border-brand-cyan bg-brand-cyan/10'
                  : 'border-brand-border bg-brand-bg/40 hover:border-brand-border-focus'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                {m.value === 'max_sharpe' && <Zap className="h-4 w-4 text-brand-cyan" />}
                {m.value === 'min_volatility' && <ShieldCheck className="h-4 w-4 text-brand-green" />}
                {m.value === 'max_utility' && <TrendingUp className="h-4 w-4 text-brand-violet" />}
                {m.value === 'risk_parity' && <BarChart3 className="h-4 w-4 text-brand-orange" />}
                <span className="text-sm font-bold text-slate-100">{m.label}</span>
              </div>
              <p className="text-[11px] text-slate-500">{m.description}</p>
            </button>
          ))}
        </div>

        {/* Weight constraint sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-5">
          <div>
            <label className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase mb-2">
              Min Weight per holding
              <span className="text-brand-cyan font-mono">{(minWeight * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min={0}
              max={30}
              value={minWeight * 100}
              onChange={(e) => setMinWeight(Number(e.target.value) / 100)}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>
          <div>
            <label className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase mb-2">
              Max Weight per holding
              <span className="text-brand-cyan font-mono">{(maxWeight * 100).toFixed(0)}%</span>
            </label>
            <input
              type="range"
              min={30}
              max={100}
              value={maxWeight * 100}
              onChange={(e) => setMaxWeight(Number(e.target.value) / 100)}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>
        </div>

        <button
          onClick={runOptimization}
          disabled={loading}
          className="w-full bg-gradient-to-r from-brand-cyan to-brand-violet text-slate-100 rounded-xl py-3 font-bold hover:shadow-lg hover:shadow-brand-cyan/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Optimizing…
            </>
          ) : (
            'Run Optimization'
          )}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-brand-red/10 border border-brand-red/25 rounded-lg text-brand-red text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-card rounded-2xl p-5 border border-brand-border">
              <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Expected Return</span>
              <h3 className="text-2xl font-bold mt-1 text-brand-green">{formatPct(result.expected_metrics?.expected_return)}</h3>
            </div>
            <div className="glass-card rounded-2xl p-5 border border-brand-border">
              <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Expected Volatility</span>
              <h3 className="text-2xl font-bold mt-1 text-brand-orange">{formatPct(result.expected_metrics?.expected_volatility)}</h3>
            </div>
            <div className="glass-card rounded-2xl p-5 border border-brand-border">
              <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Expected Sharpe</span>
              <h3 className="text-2xl font-bold mt-1 text-brand-cyan">
                {result.expected_metrics?.expected_sharpe?.toFixed(2) ?? '—'}
              </h3>
            </div>
          </div>

          {trades.length > 0 && (
            <div className="glass-card rounded-2xl border border-brand-border overflow-hidden">
              <div className="px-6 py-4 border-b border-brand-border">
                <h4 className="text-sm font-bold text-slate-100">Rebalancing Trades</h4>
                <p className="text-xs text-slate-500 mt-0.5">Weight changes to reach the optimal allocation</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500 border-b border-brand-border">
                      <th className="px-6 py-3">Ticker</th>
                      <th className="px-6 py-3">Action</th>
                      <th className="px-6 py-3 text-right">Current</th>
                      <th className="px-6 py-3 text-right">Optimal</th>
                      <th className="px-6 py-3 text-right">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t) => (
                      <tr key={t.ticker} className="border-b border-brand-border/50 hover:bg-brand-card/40">
                        <td className="px-6 py-3.5 font-mono font-bold text-slate-100">{t.ticker}</td>
                        <td className="px-6 py-3.5">
                          <span
                            className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full ${
                              t.delta_weight > 0
                                ? 'bg-brand-green/10 text-brand-green'
                                : 'bg-brand-red/10 text-brand-red'
                            }`}
                          >
                            {t.delta_weight > 0 ? 'Buy' : 'Sell'}
                          </span>
                        </td>
                        <td className="px-6 py-3.5 text-right font-mono text-slate-400">{formatPct(t.current_weight)}</td>
                        <td className="px-6 py-3.5 text-right font-mono text-slate-100">{formatPct(t.optimal_weight)}</td>
                        <td
                          className={`px-6 py-3.5 text-right font-mono font-bold ${
                            t.delta_weight > 0 ? 'text-brand-green' : 'text-brand-red'
                          }`}
                        >
                          {t.delta_weight > 0 ? '+' : ''}
                          {(t.delta_weight * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <p className="text-[10px] text-slate-600 text-center max-w-lg mx-auto leading-relaxed">
            Optimization is based on historical data and Ledoit-Wolf shrinkage covariance.
            Past performance does not guarantee future results. Informational only — not financial advice.
          </p>
        </>
      )}
    </div>
  );
}
