'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { Loader2, Search, TrendingUp, X } from 'lucide-react';

interface AddHoldingModalProps {
  onSubmit: (ticker: string, quantity: string, averageCost: string) => void;
  onClose: () => void;
}

interface Suggestion {
  symbol: string;
  name: string;
  exchange: string | null;
}

export default function AddHoldingModal({ onSubmit, onClose }: AddHoldingModalProps) {
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState('');
  const [averageCost, setAverageCost] = useState('');

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searching, setSearching] = useState(false);

  const [priceLoading, setPriceLoading] = useState(false);
  const [priceInfo, setPriceInfo] = useState<{ price: number; name?: string } | null>(null);
  const [priceError, setPriceError] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);

  // Debounced autocomplete as the user types
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = ticker.trim();
    if (q.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      const seq = ++searchSeq.current;
      setSearching(true);
      try {
        const results = await api.search.tickers(q, 8);
        if (seq !== searchSeq.current) return; // stale response
        setSuggestions(results || []);
        setShowSuggestions(true);
      } catch {
        if (seq === searchSeq.current) setSuggestions([]);
      } finally {
        if (seq === searchSeq.current) setSearching(false);
      }
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [ticker]);

  // Fetch the live price whenever a complete ticker is chosen
  const fetchPrice = async (sym: string) => {
    if (!sym) return;
    setPriceLoading(true);
    setPriceError(null);
    setPriceInfo(null);
    try {
      const quote = await api.search.getQuote(sym.toUpperCase());
      const price = Number(quote?.current_price ?? quote?.price ?? 0);
      if (price > 0) {
        setPriceInfo({ price, name: quote?.name || quote?.sector });
        // Pre-fill average cost with today's price so "bought today" is one click
        if (!averageCost) setAverageCost(String(price));
      } else {
        setPriceError('Price unavailable for this ticker right now.');
      }
    } catch {
      setPriceError('Could not fetch price — you can still enter it manually.');
    } finally {
      setPriceLoading(false);
    }
  };

  const pickSuggestion = (s: Suggestion) => {
    setTicker(s.symbol);
    setShowSuggestions(false);
    fetchPrice(s.symbol);
  };

  const handleTickerBlur = () => {
    // Give click handlers on the suggestion list a moment to fire
    setTimeout(() => setShowSuggestions(false), 150);
    const sym = ticker.trim().toUpperCase();
    if (sym && !priceInfo && /^[A-Z.\-]{1,10}$/.test(sym)) {
      fetchPrice(sym);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(ticker.trim().toUpperCase(), quantity, averageCost);
  };

  return (
    <div className="fixed inset-0 bg-brand-bg/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="glass-card rounded-2xl p-8 border border-brand-border w-full max-w-md shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-500 hover:text-slate-200 cursor-pointer"
        >
          <X className="h-4.5 w-4.5" />
        </button>

        <h3 className="text-lg font-bold text-slate-100 mb-6">Add Asset Holding</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Ticker with autocomplete */}
          <div className="relative">
            <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">
              Ticker or company name
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-slate-500" />
              <input
                type="text"
                required
                autoComplete="off"
                placeholder="Search e.g. Apple or AAPL"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                onBlur={handleTickerBlur}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 pl-10 pr-9 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm"
              />
              {searching && (
                <Loader2 className="absolute right-3 top-2.5 h-4.5 w-4.5 text-brand-cyan animate-spin" />
              )}
            </div>

            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-10 mt-1 w-full bg-brand-card border border-brand-border rounded-xl shadow-2xl overflow-hidden">
                {suggestions.map((s) => (
                  <button
                    key={s.symbol}
                    type="button"
                    onClick={() => pickSuggestion(s)}
                    className="w-full text-left px-4 py-2.5 hover:bg-brand-cyan/10 flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <div className="min-w-0">
                      <span className="font-mono font-bold text-sm text-slate-100">{s.symbol}</span>
                      <span className="block text-[11px] text-slate-500 truncate">{s.name}</span>
                    </div>
                    {s.exchange && (
                      <span className="text-[9px] text-slate-500 bg-brand-bg/60 border border-brand-border rounded px-1.5 py-0.5 flex-shrink-0">
                        {s.exchange}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Live price hint */}
          {priceLoading && (
            <div className="flex items-center space-x-2 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-cyan" />
              Fetching current price…
            </div>
          )}
          {priceInfo && !priceLoading && (
            <div className="flex items-center space-x-2 p-2.5 bg-brand-green/10 border border-brand-green/25 rounded-lg text-xs text-brand-green">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>
                {ticker.toUpperCase()} @ <b>${priceInfo.price.toFixed(2)}</b>
                {priceInfo.name ? ` — ${priceInfo.name}` : ''} · avg cost pre-filled
              </span>
            </div>
          )}
          {priceError && !priceLoading && (
            <div className="p-2.5 bg-brand-orange/10 border border-brand-orange/25 rounded-lg text-xs text-brand-orange">
              {priceError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Quantity</label>
              <input
                type="number"
                required
                step="any"
                min="0"
                placeholder="0.00"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Avg Cost</label>
              <input
                type="number"
                required
                step="any"
                min="0"
                placeholder="0.00"
                value={averageCost}
                onChange={(e) => setAverageCost(e.target.value)}
                className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-brand-border hover:bg-brand-card rounded-lg text-sm text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-brand-cyan hover:bg-brand-cyan/90 text-brand-bg font-semibold rounded-lg text-sm cursor-pointer"
            >
              Add holding
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
