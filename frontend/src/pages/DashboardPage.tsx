import React, { useEffect, useState } from 'react';
import { 
  FileText, 
  AlertTriangle, 
  IndianRupee, 
  Clock, 
  CheckCircle2, 
  Layers, 
  ArrowUpRight,
  RefreshCw,
  Info
} from 'lucide-react';
import { api } from '../api/client';
import type { DashboardMetrics } from '../types';

interface DashboardPageProps {
  onNavigate: (route: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDashboardMetrics();
      setMetrics(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load metrics from server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const formatINR = (amount?: number) => {
    if (amount === undefined || amount === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            Accounts Payable Command Center
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time financial exposure, MSME statutory deadlines & exception resolution queues.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadMetrics}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Queries
          </button>
        </div>
      </div>

      {/* Production Truth Notice */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs flex items-start gap-2.5">
        <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
        <div className="text-slate-300 space-y-0.5">
          <span className="font-semibold text-slate-200">Strict Production Truth Protocol:</span> Zero operational data is fabricated. All metrics below are computed strictly from live database rows. When an integration or input is missing, status displays <code className="text-indigo-300 bg-slate-950 px-1 py-0.5 rounded">Unavailable</code> with the exact reason rather than zero or placeholder data.
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-lg p-4 text-xs text-rose-300 flex items-center justify-between">
          <span>Failed to query metrics: {error}</span>
          <button onClick={loadMetrics} className="underline hover:text-white">Retry</button>
        </div>
      )}

      {/* Primary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Invoices */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Total Invoices Ingested</span>
            <FileText className="w-4 h-4 text-slate-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold font-mono tracking-tight text-white tabular-nums">
              {metrics?.status === 'active' ? metrics.summary?.total_invoices : '—'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 flex items-center justify-between">
              <span>Authoritative count</span>
              <button onClick={() => onNavigate('inbox')} className="text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5">
                View Ledger <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Open Exceptions */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Open Exceptions</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold font-mono tracking-tight text-amber-400 tabular-nums">
              {metrics?.status === 'active' ? metrics.summary?.open_exceptions : '—'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 flex items-center justify-between">
              <span>Requires AP action</span>
              <button onClick={() => onNavigate('exceptions')} className="text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5">
                Triage Queue <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Blocked Financial Exposure */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Blocked Value (Held)</span>
            <IndianRupee className="w-4 h-4 text-slate-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold font-mono tracking-tight text-white tabular-nums">
              {metrics?.status === 'active' ? formatINR(metrics.summary?.blocked_value_inr) : '—'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Held pending 5-way reconciliation
            </div>
          </div>
        </div>

        {/* MSME Statutory Exposure */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">MSMED 45-Day Exposure</span>
            <Clock className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold font-mono tracking-tight text-rose-400 tabular-nums">
              {metrics?.status === 'active' ? metrics.summary?.msme_exposure_count : '—'}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Section 16 penal interest horizon
            </div>
          </div>
        </div>
      </div>

      {/* Stage & Decision Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Processing Stages */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h2 className="text-xs font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Ingestion & Pipeline Stages
            </h2>
            <span className="text-[11px] font-mono text-slate-500">Live DB State</span>
          </div>
          <div className="divide-y divide-slate-800/60 mt-2">
            {['RECEIVED', 'VALIDATING', 'PARSING', 'EXTRACTED', 'MATCHING', 'DECIDED', 'ACTION_REQUIRED'].map((stage) => {
              const count = metrics?.stages?.[stage] || 0;
              return (
                <div key={stage} className="py-2.5 flex items-center justify-between text-xs">
                  <span className="font-mono text-slate-300">{stage}</span>
                  <span className="font-mono tabular-nums text-slate-100 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    {metrics?.status === 'active' ? count : '—'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Engine Decisions */}
        <div className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h2 className="text-xs font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Deterministic Decisions
            </h2>
            <span className="text-[11px] font-mono text-slate-500">AOP Matching Engine</span>
          </div>
          <div className="divide-y divide-slate-800/60 mt-2">
            {[
              { id: 'AUTO_APPROVED', label: 'AUTO_APPROVED', color: 'text-emerald-400' },
              { id: 'NEEDS_REVIEW', label: 'NEEDS_REVIEW', color: 'text-amber-400' },
              { id: 'REJECTED', label: 'REJECTED (Duplicate / Fraud)', color: 'text-rose-400' },
              { id: 'QUARANTINED', label: 'QUARANTINED (Unreadable / Malformed)', color: 'text-purple-400' },
            ].map((dec) => {
              const count = metrics?.decisions?.[dec.id] || 0;
              return (
                <div key={dec.id} className="py-2.5 flex items-center justify-between text-xs">
                  <span className={`font-mono ${dec.color}`}>{dec.label}</span>
                  <span className="font-mono tabular-nums text-slate-100 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    {metrics?.status === 'active' ? count : '—'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
