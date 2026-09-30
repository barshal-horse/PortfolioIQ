'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api';
import {
  FileText,
  Loader2,
  Download,
  Trash2,
  Plus,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
} from 'lucide-react';

interface ReportItem {
  id: string;
  portfolio_id: string;
  report_type: string;
  title: string;
  status: string;
  file_size_bytes: number | null;
  summary: string | null;
  error_message: string | null;
  created_at: string;
  generated_at: string | null;
}

const REPORT_TYPES = [
  {
    value: 'executive_summary',
    label: 'Executive Summary',
    description: 'One-page overview with key metrics and health score',
  },
  {
    value: 'full_portfolio',
    label: 'Full Portfolio Report',
    description: 'Complete analysis: holdings, risk, optimization, stress tests',
  },
  {
    value: 'monthly_review',
    label: 'Monthly Review',
    description: 'Monthly performance recap with holdings detail',
  },
  {
    value: 'health_report',
    label: 'Health Report',
    description: 'Deep-dive into your portfolio health score',
  },
];

interface ReportsTabProps {
  portfolioId: string;
}

export default function ReportsTab({ portfolioId }: ReportsTabProps) {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.reports.list(portfolioId);
      setReports(list || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [portfolioId]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleGenerate = async (reportType: string) => {
    setGenerating(reportType);
    setError(null);
    setNotice(null);
    try {
      const result = await api.reports.generate(portfolioId, reportType);
      setNotice(`Report generation started (${result?.report_id?.slice(0, 8)}…).`);
      await loadReports();
      // Poll status until it leaves "generating"
      const reportId = result?.report_id;
      if (reportId) {
        let attempts = 0;
        pollRef.current = setInterval(async () => {
          attempts += 1;
          try {
            const status = await api.reports.getStatus(reportId);
            if (status?.status !== 'generating' || attempts > 60) {
              if (pollRef.current) clearInterval(pollRef.current);
              await loadReports();
              if (status?.status === 'completed') {
                setNotice('Report ready for download.');
              } else if (status?.status === 'failed') {
                setError(status?.error_message || 'Report generation failed.');
              }
            }
          } catch {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        }, 2000);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to start report generation');
    } finally {
      setGenerating(null);
    }
  };

  const handleDownload = async (report: ReportItem) => {
    setDownloading(report.id);
    setError(null);
    try {
      const objectUrl = await api.reports.download(report.id);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `${report.report_type}_${report.created_at.slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (err: any) {
      setError(err?.message || 'Download failed');
    } finally {
      setDownloading(null);
    }
  };

  const handleDelete = async (reportId: string) => {
    if (!confirm('Delete this report permanently?')) return;
    try {
      await api.reports.delete(reportId);
      setReports((prev) => prev.filter((r) => r.id !== reportId));
    } catch (err: any) {
      setError(err?.message || 'Delete failed');
    }
  };

  const formatSize = (bytes: number | null) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const StatusBadge = ({ status }: { status: string }) => {
    if (status === 'completed') {
      return (
        <span className="flex items-center space-x-1 text-[10px] font-semibold text-brand-green bg-brand-green/10 border border-brand-green/25 rounded-full px-2 py-0.5">
          <CheckCircle2 className="h-3 w-3" />
          Ready
        </span>
      );
    }
    if (status === 'failed') {
      return (
        <span className="flex items-center space-x-1 text-[10px] font-semibold text-brand-red bg-brand-red/10 border border-brand-red/25 rounded-full px-2 py-0.5">
          <XCircle className="h-3 w-3" />
          Failed
        </span>
      );
    }
    return (
      <span className="flex items-center space-x-1 text-[10px] font-semibold text-brand-orange bg-brand-orange/10 border border-brand-orange/25 rounded-full px-2 py-0.5">
        <Clock className="h-3 w-3 animate-pulse" />
        Generating
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Generate panel */}
      <div className="glass-card rounded-2xl p-6 border border-brand-border">
        <div className="flex items-center space-x-3 mb-5">
          <div className="p-2.5 bg-brand-violet/10 rounded-xl">
            <FileText className="h-5 w-5 text-brand-violet" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100">PDF Reports</h3>
            <p className="text-sm text-slate-400">
              Institutional-grade reports with charts, analytics, and disclaimers
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {REPORT_TYPES.map((rt) => (
            <button
              key={rt.value}
              onClick={() => handleGenerate(rt.value)}
              disabled={generating !== null}
              className="text-left glass-card glass-card-hover rounded-xl p-5 border border-brand-border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed group"
            >
              <div className="flex items-center justify-between mb-1.5">
                <h5 className="text-sm font-bold text-slate-100 group-hover:text-brand-cyan transition-colors">
                  {rt.label}
                </h5>
                {generating === rt.value ? (
                  <Loader2 className="h-4 w-4 text-brand-cyan animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 text-slate-600 group-hover:text-brand-cyan transition-colors" />
                )}
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">{rt.description}</p>
            </button>
          ))}
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

      {/* Reports list */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
            Your Reports
          </h4>
          <button
            onClick={loadReports}
            className="text-xs text-slate-500 hover:text-slate-300 flex items-center space-x-1 cursor-pointer"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="glass-card rounded-2xl p-12 border border-brand-border flex flex-col items-center">
            <Loader2 className="h-8 w-8 text-brand-cyan animate-spin mb-3" />
            <span className="text-sm text-slate-400">Loading reports…</span>
          </div>
        ) : reports.length === 0 ? (
          <div className="glass-card rounded-2xl p-12 border border-brand-border flex flex-col items-center text-center">
            <FileText className="h-12 w-12 text-slate-600 mb-3" />
            <h5 className="text-base font-bold text-slate-300 mb-1">No reports yet</h5>
            <p className="text-xs text-slate-500 max-w-sm">
              Generate your first report using one of the report types above.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map((report) => (
              <div
                key={report.id}
                className="glass-card rounded-2xl p-5 border border-brand-border flex items-center justify-between gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-3 mb-1">
                    <h5 className="text-sm font-bold text-slate-100 truncate">{report.title}</h5>
                    <StatusBadge status={report.status} />
                  </div>
                  <div className="flex items-center space-x-3 text-[10px] text-slate-500 flex-wrap">
                    <span>
                      {new Date(report.created_at).toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span>•</span>
                    <span>{formatSize(report.file_size_bytes)}</span>
                    {report.error_message && (
                      <>
                        <span>•</span>
                        <span className="text-brand-red truncate max-w-xs">
                          {report.error_message}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2 flex-shrink-0">
                  {report.status === 'completed' && (
                    <button
                      onClick={() => handleDownload(report)}
                      disabled={downloading === report.id}
                      className="flex items-center space-x-1.5 bg-brand-cyan/15 hover:bg-brand-cyan/25 text-brand-cyan border border-brand-cyan/30 rounded-xl px-3 py-2 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {downloading === report.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                      PDF
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(report.id)}
                    className="p-2 text-slate-600 hover:text-brand-red rounded-lg hover:bg-brand-red/10 transition-colors cursor-pointer"
                    title="Delete report"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
