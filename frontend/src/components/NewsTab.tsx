'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import {
  Newspaper,
  RefreshCw,
  Loader2,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Minus,
  Calendar,
  Brain,
} from 'lucide-react';

interface NewsArticle {
  id: string;
  source: string;
  title: string;
  summary: string | null;
  url: string;
  published_at: string;
  category: string | null;
  related_tickers: string[];
}

interface TickerSentiment {
  ticker: string;
  overall_sentiment: string;
  avg_confidence: number;
  avg_impact_score: number;
  article_count: number;
  distribution: { positive: number; negative: number; neutral: number };
}

interface NewsTabProps {
  portfolioId: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  earnings: 'bg-brand-green/10 text-brand-green border-brand-green/25',
  market: 'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/25',
  company: 'bg-brand-violet/10 text-brand-violet border-brand-violet/25',
};

const SENTIMENT_ICONS: Record<string, any> = {
  positive: TrendingUp,
  negative: TrendingDown,
  neutral: Minus,
};

const SENTIMENT_COLORS: Record<string, string> = {
  positive: 'text-brand-green bg-brand-green/10 border-brand-green/25',
  negative: 'text-brand-red bg-brand-red/10 border-brand-red/25',
  neutral: 'text-slate-400 bg-slate-500/10 border-slate-500/25',
};

export default function NewsTab({ portfolioId }: NewsTabProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [sentiments, setSentiments] = useState<TickerSentiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processingSentiment, setProcessingSentiment] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  const loadNews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [news, sent] = await Promise.all([
        api.news.getPortfolioNews(portfolioId, days, 50).catch(() => []),
        api.news.getPortfolioSentiment(portfolioId, days).catch(() => []),
      ]);
      setArticles(news || []);
      setSentiments(sent || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load news');
    } finally {
      setLoading(false);
    }
  }, [portfolioId, days]);

  useEffect(() => {
    loadNews();
  }, [loadNews]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setNotice(null);
    setError(null);
    try {
      const result = await api.news.refreshPortfolioNews(portfolioId, days);
      setNotice(
        `Fetched ${result?.fetched ?? 0} articles, ${result?.stored ?? 0} new ones stored.`
      );
      await loadNews();
    } catch (err: any) {
      const msg = err?.message || 'Refresh failed';
      setError(
        msg.includes('API key') || msg.includes('401')
          ? 'News refresh failed — check FINNHUB_API_KEY / NEWSAPI_API_KEY on the backend.'
          : msg
      );
    } finally {
      setRefreshing(false);
    }
  };

  const handleProcessSentiment = async () => {
    setProcessingSentiment(true);
    setNotice(null);
    setError(null);
    try {
      const result = await api.news.processSentiment(100);
      setNotice(
        result?.processed > 0
          ? `Sentiment analysis completed for ${result.processed} articles.`
          : 'No unanalyzed articles pending sentiment processing.'
      );
      await loadNews();
    } catch (err: any) {
      const msg = err?.message || 'Sentiment processing failed';
      setError(
        msg.includes('API key') || msg.includes('quota') || msg.includes('401')
          ? 'Sentiment analysis requires GEMINI_API_KEY on the backend.'
          : msg
      );
    } finally {
      setProcessingSentiment(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const hoursAgo = Math.floor(diffMs / (1000 * 60 * 60));
    if (hoursAgo < 1) return 'Just now';
    if (hoursAgo < 24) return `${hoursAgo}h ago`;
    const daysAgo = Math.floor(hoursAgo / 24);
    if (daysAgo < 7) return `${daysAgo}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="space-y-6">
      {/* Header controls */}
      <div className="glass-card rounded-2xl p-6 border border-brand-border">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-brand-cyan/10 rounded-xl">
              <Newspaper className="h-5 w-5 text-brand-cyan" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-100">News Intelligence</h3>
              <p className="text-sm text-slate-400">
                Holdings-relevant news and AI sentiment for your portfolio
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="bg-brand-card border border-brand-border rounded-xl px-3 py-2 text-xs text-slate-200 cursor-pointer focus:outline-none focus:border-brand-cyan"
            >
              <option value={1}>Last 24 hours</option>
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center space-x-1.5 bg-brand-cyan/15 hover:bg-brand-cyan/25 text-brand-cyan border border-brand-cyan/30 rounded-xl px-3 py-2 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {refreshing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Refresh News
            </button>
            <button
              onClick={handleProcessSentiment}
              disabled={processingSentiment}
              className="flex items-center space-x-1.5 bg-brand-violet/15 hover:bg-brand-violet/25 text-brand-violet border border-brand-violet/30 rounded-xl px-3 py-2 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              {processingSentiment ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Brain className="h-3.5 w-3.5" />
              )}
              Analyze Sentiment
            </button>
          </div>
        </div>

        {notice && (
          <div className="mt-4 p-3 bg-brand-green/10 border border-brand-green/25 rounded-lg text-brand-green text-xs">
            {notice}
          </div>
        )}
        {error && (
          <div className="mt-4 p-3 bg-brand-red/10 border border-brand-red/25 rounded-lg text-brand-red text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Sentiment summary cards */}
      {sentiments.length > 0 && (
        <div>
          <h4 className="text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">
            Sentiment by Holding
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {sentiments.map((s) => {
              const Icon = SENTIMENT_ICONS[s.overall_sentiment] || Minus;
              const colorClass = SENTIMENT_COLORS[s.overall_sentiment] || SENTIMENT_COLORS.neutral;
              return (
                <div
                  key={s.ticker}
                  className="glass-card rounded-xl p-4 border border-brand-border"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono font-bold text-sm text-slate-100">{s.ticker}</span>
                    <span className={`p-1 rounded border ${colorClass}`}>
                      <Icon className="h-3 w-3" />
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 capitalize">{s.overall_sentiment}</p>
                  <div className="mt-2 flex items-center justify-between text-[10px]">
                    <span className="text-slate-500">{s.article_count} articles</span>
                    <span className="text-slate-400">
                      impact {(s.avg_impact_score >= 0 ? '+' : '') + s.avg_impact_score.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* News feed */}
      <div>
        <h4 className="text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">
          Latest News
        </h4>
        {loading ? (
          <div className="glass-card rounded-2xl p-12 border border-brand-border flex flex-col items-center">
            <Loader2 className="h-8 w-8 text-brand-cyan animate-spin mb-3" />
            <span className="text-sm text-slate-400">Loading news feed…</span>
          </div>
        ) : articles.length === 0 ? (
          <div className="glass-card rounded-2xl p-12 border border-brand-border flex flex-col items-center text-center">
            <Newspaper className="h-12 w-12 text-slate-600 mb-3" />
            <h5 className="text-base font-bold text-slate-300 mb-1">No news yet</h5>
            <p className="text-xs text-slate-500 max-w-sm mb-4">
              Click &quot;Refresh News&quot; to fetch the latest articles for your holdings from
              Finnhub and NewsAPI. Requires news API keys on the backend.
            </p>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="bg-brand-cyan/15 hover:bg-brand-cyan/25 text-brand-cyan border border-brand-cyan/30 rounded-xl px-4 py-2 text-xs font-semibold cursor-pointer"
            >
              Fetch Now
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {articles.map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="glass-card glass-card-hover rounded-2xl p-5 border border-brand-border block group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-2 flex-wrap">
                      {article.category && (
                        <span
                          className={`text-[9px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wide ${
                            CATEGORY_COLORS[article.category] ||
                            'bg-slate-500/10 text-slate-400 border-slate-500/25'
                          }`}
                        >
                          {article.category}
                        </span>
                      )}
                      {article.related_tickers?.slice(0, 4).map((t) => (
                        <span
                          key={t}
                          className="text-[9px] px-1.5 py-0.5 rounded-full bg-brand-card border border-brand-border text-slate-400 font-mono"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                    <h5 className="text-sm font-semibold text-slate-100 group-hover:text-brand-cyan transition-colors leading-snug">
                      {article.title}
                    </h5>
                    {article.summary && (
                      <p className="text-xs text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                        {article.summary}
                      </p>
                    )}
                    <div className="flex items-center space-x-3 mt-2.5 text-[10px] text-slate-500">
                      <span className="uppercase font-semibold">{article.source}</span>
                      <span>•</span>
                      <span>{formatDate(article.published_at)}</span>
                    </div>
                  </div>
                  <ExternalLink className="h-4 w-4 text-slate-600 group-hover:text-brand-cyan flex-shrink-0 mt-1 transition-colors" />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
