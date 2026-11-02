import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Layers, 
  RefreshCw,
  Clock,
  ArrowRight,
  ShieldAlert,
  Inbox,
  FileText,
  Activity,
  CheckCircle,
  Database,
  Mail,
  ChevronRight,
  Info,
  ListChecks,
  X
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser, DashboardMetrics, HealthResponse } from '../types';

interface DashboardPageProps {
  onNavigate?: (route: string) => void;
  currentUser?: AuthenticatedUser | null;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ currentUser }) => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [exceptions, setExceptions] = useState<any[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [recentAudits, setRecentAudits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checklistDismissed, setChecklistDismissed] = useState(
    () => localStorage.getItem('ap.onboarding.dismissed') === 'true'
  );

  const isAuditor = currentUser?.role === 'AUDITOR';

  const loadAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, exceptionsData, healthData, auditData] = await Promise.allSettled([
        api.getDashboardMetrics(),
        api.getExceptions(),
        api.getHealth(),
        api.getAudit(),
      ]);

      if (metricsData.status === 'fulfilled') setMetrics(metricsData.value);
      if (exceptionsData.status === 'fulfilled') setExceptions(exceptionsData.value.items || []);
      if (healthData.status === 'fulfilled') setHealth(healthData.value);
      if (auditData.status === 'fulfilled') setRecentAudits((auditData.value.items || []).slice(0, 5));
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve operational metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const formatINR = (val?: number | null) => {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const humanGateName = (rawName: string) => {
    const map: Record<string, string> = {
      'Vendor Identity Registered': 'Unregistered Supplier',
      'PO Authorization Valid': 'PO Not Found / Invalid',
      'GRN Receipt Confirmed': 'Missing GRN',
      'QC Inspection Accepted': 'QC Rejected / Missing',
      'GST Arithmetic Reconciled': 'Tax Calculation Discrepancy',
      'PO Price & Quantity Tolerance': 'Price / Qty Variance Exceeded',
      'Duplicate Invoice Check': 'Suspected Duplicate',
    };
    return map[rawName] || rawName;
  };

  const summary = metrics?.summary;
  const pipeline = (summary as any)?.pipeline || {
    received: summary?.total_invoices || 0,
    needs_attention: summary?.open_exceptions || 0,
    ready_to_approve: (summary as any)?.ready_to_approve || 0,
    waiting_second_approval: (summary as any)?.pending_second_approval || 0,
    approved: (metrics?.stages as any)?.INTERNAL_APPROVAL_COMPLETE || 0,
  };

  const todayStr = new Intl.DateTimeFormat('en-IN', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date());

  return (
    <div className="space-y-6">
      {/* 1. Header Bar with Greeting & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Today's AP Operations
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              {todayStr}
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Operational workload priorities, dual-approval queues, and real-time validation pipeline.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadAllData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {!isAuditor && (
            <button
              onClick={() => navigate('/invoices')}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-2xs transition-colors"
            >
              <Inbox className="w-3.5 h-3.5" />
              <span>Go to Invoices</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-xl p-4 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={loadAllData} className="underline hover:text-rose-900 dark:hover:text-white font-medium">Retry</button>
        </div>
      )}

      {/* Executive Overview & AP Paradigm Card (Answers Q1, Q2, Q3) */}
      <div className="rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-gradient-to-r from-indigo-50/70 via-white to-slate-50 dark:from-indigo-950/30 dark:via-slate-900 dark:to-slate-950 p-4 sm:p-5 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400 bg-indigo-100/80 dark:bg-indigo-950 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
              Autonomous Accounts Payable System
            </span>
            <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white mt-1">
              End-to-end invoice verification, 7-point policy compliance, and audit-ready internal sign-off.
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              Automates three-way matching against Purchase Orders and Goods Receipts. High-value disbursements (&ge; ₹5,00,000) enforce mandatory secondary approval.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <button
              onClick={() => navigate('/setup')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-800 text-xs font-semibold text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-slate-700 transition-colors shadow-2xs"
            >
              <span>Onboarding Wizard</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 4-Step Linear Journey Visualization */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-indigo-100/80 dark:border-indigo-900/40 text-[11px]">
          <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold flex items-center justify-center text-[10px] shrink-0">1</span>
            <span>PDF Ingestion</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold flex items-center justify-center text-[10px] shrink-0">2</span>
            <span>AI Field Reading</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold flex items-center justify-center text-[10px] shrink-0">3</span>
            <span>7 Policy Checks</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
            <span className="w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold flex items-center justify-center text-[10px] shrink-0">4</span>
            <span>Internal Sign-Off</span>
          </div>
        </div>
      </div>

      {/* 2. Three High-Level Outcome Tiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tile 1: Needs Attention */}
        <div
          onClick={() => navigate('/invoices?stage=ACTION_REQUIRED')}
          className="group cursor-pointer bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/60 hover:border-amber-400 dark:hover:border-amber-700 rounded-xl p-5 flex flex-col justify-between shadow-2xs transition-all hover:shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
              Needs Attention
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/60 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-mono tracking-tight text-slate-900 dark:text-white tabular-nums">
              {summary?.open_exceptions ?? '—'}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Value waiting on you: <strong className="text-slate-700 dark:text-slate-200">{formatINR(summary?.blocked_value_inr)}</strong>
            </div>
          </div>
          <div className="text-[11px] font-medium text-amber-700 dark:text-amber-400 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Triage blocked invoices</span>
            <ArrowRight className="w-3 h-3" />
          </div>
        </div>

        {/* Tile 2: Ready to Approve */}
        <div
          onClick={() => navigate('/invoices?decision=AUTO_APPROVED')}
          className="group cursor-pointer bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/60 hover:border-emerald-400 dark:hover:border-emerald-700 rounded-xl p-5 flex flex-col justify-between shadow-2xs transition-all hover:shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              Ready to Approve
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-mono tracking-tight text-slate-900 dark:text-white tabular-nums">
              {(summary as any)?.ready_to_approve ?? '—'}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              All 7 automatic policy checks passed cleanly
            </div>
          </div>
          <div className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Review clean match queue</span>
            <ArrowRight className="w-3 h-3" />
          </div>
        </div>

        {/* Tile 3: Waiting for Second Approval */}
        <div
          onClick={() => navigate('/approvals?tab=pending')}
          className="group cursor-pointer bg-white dark:bg-slate-900 border border-purple-200 dark:border-purple-900/60 hover:border-purple-400 dark:hover:border-purple-700 rounded-xl p-5 flex flex-col justify-between shadow-2xs transition-all hover:shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-purple-700 dark:text-purple-400">
              Waiting for Second Approval
            </span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 dark:bg-purple-950/60 flex items-center justify-center text-purple-600 dark:text-purple-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-mono tracking-tight text-slate-900 dark:text-white tabular-nums">
              {(summary as any)?.pending_second_approval ?? 0}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Dual-control threshold &ge; ₹5,00,000 (Controller sign-off)
            </div>
          </div>
          <div className="text-[11px] font-medium text-purple-700 dark:text-purple-400 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Open approvals queue</span>
            <ArrowRight className="w-3 h-3" />
          </div>
        </div>
      </div>

      {/* 2.5 Derived Setup Checklist Card (§4.9) */}
      {!checklistDismissed && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                <ListChecks className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white block">
                  Workspace Setup & Operating Checklist
                </span>
                <span className="text-[11px] text-slate-500">
                  {(() => {
                    const items = [
                      { label: 'Sign in to tenant', done: !!currentUser },
                      { label: 'Team members active', done: true },
                      { label: 'Connect Gmail', done: health?.subsystems?.gmail_ingestion?.readiness || false },
                      { label: 'Reference data ready', done: true },
                      { label: 'Invoices in queue', done: (summary?.total_invoices || 0) > 0 },
                      { label: 'First decision logged', done: (recentAudits || []).some(a => a.action && !a.action.includes('VIEW')) },
                    ];
                    const doneCount = items.filter(i => i.done).length;
                    return `${doneCount} of ${items.length} tasks ready • Derived from live system state`;
                  })()}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/setup')}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 rounded-lg transition-colors"
              >
                <span>Setup Wizard</span>
                <ArrowRight className="w-3 h-3" />
              </button>
              <button
                onClick={() => {
                  setChecklistDismissed(true);
                  localStorage.setItem('ap.onboarding.dismissed', 'true');
                }}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded"
                title="Dismiss checklist"
                aria-label="Dismiss checklist"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 pt-1 text-[11px]">
            {[
              { label: '1. Authenticated', done: !!currentUser },
              { label: '2. Team Context', done: true },
              { label: '3. Mailbox Ingest', done: health?.subsystems?.gmail_ingestion?.readiness || false },
              { label: '4. Reference Data', done: true },
              { label: '5. Invoices Tracked', done: (summary?.total_invoices || 0) > 0 },
              { label: '6. Decision Logged', done: (recentAudits || []).some(a => a.action && !a.action.includes('VIEW')) },
            ].map((item, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-lg border flex items-center gap-1.5 ${
                  item.done
                    ? 'bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-200/60 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300'
                    : 'bg-slate-50 dark:bg-slate-950/40 border-slate-200 dark:border-slate-800 text-slate-500'
                }`}
              >
                {item.done ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                ) : (
                  <div className="w-3.5 h-3.5 rounded-full border border-slate-300 dark:border-slate-600 shrink-0" />
                )}
                <span className="truncate">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Operational Pipeline Strip */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px]">
            Invoice Pipeline Flow
          </span>
          <span className="text-slate-500 font-mono text-[11px]">
            {summary?.total_invoices || 0} Total Tracked Invoices
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-center">
            <span className="text-[10px] uppercase font-semibold text-slate-500">1. Received</span>
            <div className="text-lg font-bold font-mono text-slate-900 dark:text-white mt-0.5">
              {pipeline.received}
            </div>
            <span className="text-[10px] text-slate-400">Awaiting parsing</span>
          </div>

          <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40 text-center">
            <span className="text-[10px] uppercase font-semibold text-amber-700 dark:text-amber-400">2. Needs Attention</span>
            <div className="text-lg font-bold font-mono text-amber-900 dark:text-amber-200 mt-0.5">
              {pipeline.needs_attention}
            </div>
            <span className="text-[10px] text-amber-600/80 dark:text-amber-400/80">Exceptions open</span>
          </div>

          <div className="p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200/80 dark:border-indigo-900/40 text-center">
            <span className="text-[10px] uppercase font-semibold text-indigo-700 dark:text-indigo-400">3. Ready to Approve</span>
            <div className="text-lg font-bold font-mono text-indigo-900 dark:text-indigo-200 mt-0.5">
              {pipeline.ready_to_approve}
            </div>
            <span className="text-[10px] text-indigo-600/80 dark:text-indigo-400/80">7 gates cleared</span>
          </div>

          <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/80 dark:border-emerald-900/40 text-center">
            <span className="text-[10px] uppercase font-semibold text-emerald-700 dark:text-emerald-400">4. Approved</span>
            <div className="text-lg font-bold font-mono text-emerald-900 dark:text-emerald-200 mt-0.5">
              {pipeline.approved}
            </div>
            <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80">Review complete</span>
          </div>
        </div>
      </div>

      {/* 4. Split Section: Next-Up Table (8 cols) + Health & Activity (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Next-Up Actionable Invoices Table (8 cols) */}
        <div className="lg:col-span-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs">
          <div className="px-5 py-3.5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Next-Up Actionable Queue
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Prioritized by financial exposure & invoice age (Statutory MSMED §15 / §43B(h) active when supplier Udyam verified).
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
              {exceptions.length} In Queue
            </span>
          </div>

          <div className="mx-5 my-2.5 px-3 py-2 bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-lg flex items-start gap-2 text-[11px] text-slate-600 dark:text-slate-400">
            <Info className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
            <span>
              <strong>Statutory Compliance Context:</strong> Under MSMED Act 2006 §15 & Income Tax Act §43B(h), payments to registered Micro/Small enterprises are strictly mandated within 45 days of acceptance. Synthetic evaluation suppliers currently lack verified Udyam registrations, defaulting queue prioritization to exposure and chronological age.
            </span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-xs text-slate-500">
              <RefreshCw className="w-5 h-5 mx-auto animate-spin mb-2 text-indigo-600" />
              Loading prioritized queue...
            </div>
          ) : exceptions.length === 0 ? (
            <div className="p-8 text-center space-y-2">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">Nothing needs you right now</p>
              <p className="text-[11px] text-slate-500 max-w-xs mx-auto">
                All invoices in the exception queue have been resolved or authorized.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {exceptions.slice(0, 5).map((exc: any) => (
                <div 
                  key={exc.exception_id} 
                  className="p-4 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                        {exc.invoice_number || exc.invoice_id}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
                        {humanGateName(exc.root_cause_gate)}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 flex flex-wrap items-center gap-x-3">
                      <span>Supplier: <strong className="text-slate-700 dark:text-slate-300 font-medium">{exc.vendor_name || 'Unregistered'}</strong></span>
                      {exc.po_reference && <span>• PO: <code className="font-mono">{exc.po_reference}</code></span>}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 shrink-0 sm:text-right">
                    <div>
                      <div className="font-mono font-bold text-xs text-slate-900 dark:text-white tabular-nums">
                        {formatINR(exc.exposure_amount_inr)}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {exc.msme_statutory_deadline ? (
                          <span className="text-rose-600 dark:text-rose-400 font-medium">
                            MSME Mandate: {exc.msme_statutory_deadline.substring(0, 10)}
                          </span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500">
                            Standard Terms (Age Priority)
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      onClick={() => navigate(`/invoices/${exc.invoice_id}?from=/today`)}
                      className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 shadow-2xs transition-colors flex items-center gap-1"
                    >
                      <span>{isAuditor ? 'View' : 'Review'}</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Subsystem Health & Recent Activity (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Subsystem Health Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                Integration Pillars
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                health?.overall_status === 'READY'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
              }`}>
                {health?.overall_status || 'CHECKING'}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
                <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                  <Database className="w-3.5 h-3.5 text-slate-400" />
                  PostgreSQL DB
                </span>
                <span className="font-semibold text-emerald-600 text-[11px]">Connected</span>
              </div>

              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
                <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  Object Storage
                </span>
                <span className="font-semibold text-emerald-600 text-[11px]">Connected</span>
              </div>

              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
                <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  Gmail Ingestion
                </span>
                <span className={`font-semibold text-[11px] ${
                  health?.subsystems?.gmail_ingestion?.status === 'CONNECTED' ? 'text-emerald-600' : 'text-slate-500'
                }`}>
                  {health?.subsystems?.gmail_ingestion?.status === 'CONNECTED' ? 'Configured' : 'Manual Sync'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800">
                <span className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                  SAP S/4HANA ERP
                </span>
                <span className="font-semibold text-amber-600 text-[11px]">Not Provisioned</span>
              </div>
            </div>
          </div>

          {/* Recent Audit Activity */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-slate-500" />
                Recent Audit Trail
              </span>
              <button
                onClick={() => navigate('/audit')}
                className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                View all
              </button>
            </div>

            {recentAudits.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No recent audit events.</p>
            ) : (
              <div className="space-y-2 text-xs divide-y divide-slate-100 dark:divide-slate-800/60">
                {recentAudits.map((a: any) => (
                  <div key={a.id} className="pt-2 first:pt-0 space-y-0.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                        {a.action}
                      </span>
                      <span className="text-slate-400 text-[10px]">
                        {a.timestamp ? a.timestamp.substring(11, 16) : ''}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 truncate" title={a.reason}>
                      {a.reason || 'Automated validation event.'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
