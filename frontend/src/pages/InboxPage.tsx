import React, { useEffect, useState, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Inbox as InboxIcon, 
  Filter, 
  RefreshCw, 
  ArrowUpRight, 
  FileText,
  Clock,
  Mail,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Search,
  X,
  Plus,
  UploadCloud
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import type { InboxResponse } from '../types';

interface InboxPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

export const InboxPage: React.FC<InboxPageProps> = ({ onSelectInvoice }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<InboxResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState<string>(searchParams.get('stage') || '');
  const [decisionFilter, setDecisionFilter] = useState<string>(searchParams.get('decision') || '');
  const [fyFilter, setFyFilter] = useState<string>(() => searchParams.get('fy') || localStorage.getItem('ap.inbox.fy') || '');
  const [monthFilter, setMonthFilter] = useState<string>(() => searchParams.get('month') || localStorage.getItem('ap.inbox.month') || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [syncingMailbox, setSyncingMailbox] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeQuickTab = (() => {
    if (stageFilter === 'ACTION_REQUIRED') return 'EXCEPTIONS';
    if (decisionFilter === 'MATCH_CANDIDATE' || decisionFilter === 'AUTO_APPROVED') return 'READY';
    if (decisionFilter === 'MANUALLY_APPROVED') return 'APPROVED';
    if (decisionFilter === 'QUARANTINED') return 'QUARANTINE';
    return 'ALL';
  })();

  const setQuickTab = (tab: string) => {
    setPage(1);
    const next = new URLSearchParams();
    if (tab === 'EXCEPTIONS') {
      next.set('stage', 'ACTION_REQUIRED');
      setStageFilter('ACTION_REQUIRED');
      setDecisionFilter('');
    } else if (tab === 'READY') {
      next.set('decision', 'MATCH_CANDIDATE');
      setStageFilter('');
      setDecisionFilter('MATCH_CANDIDATE');
    } else if (tab === 'APPROVED') {
      next.set('decision', 'MANUALLY_APPROVED');
      setStageFilter('');
      setDecisionFilter('MANUALLY_APPROVED');
    } else if (tab === 'QUARANTINE') {
      next.set('decision', 'QUARANTINED');
      setStageFilter('');
      setDecisionFilter('QUARANTINED');
    } else {
      setStageFilter('');
      setDecisionFilter('');
    }
    setSearchParams(next);
  };

  const handleUploadFile = async (file: File) => {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File exceeds maximum upload size of 50 MB.');
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadFeedback(`Uploading ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.uploadDocument(formData);
      setUploadFeedback(`Uploaded ${file.name}. Invoice registered into processing queue.`);
      await loadInbox();
    } catch (err: any) {
      if (err.message && err.message.includes('409')) {
        setUploadError(`Duplicate detected: ${file.name} has already been registered in the system.`);
      } else {
        setUploadError(err.message || 'Invoice upload failed.');
      }
    } finally {
      setUploading(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!searchQuery.trim()) return data.items;
    const q = searchQuery.toLowerCase().trim();
    return data.items.filter((inv) =>
      (inv.vendor_name || '').toLowerCase().includes(q) ||
      (inv.invoice_number || '').toLowerCase().includes(q) ||
      (inv.po_reference || '').toLowerCase().includes(q) ||
      (inv.vendor_gstin || '').toLowerCase().includes(q) ||
      inv.id.toLowerCase().includes(q)
    );
  }, [data?.items, searchQuery]);

  // Sync state if query params change externally
  useEffect(() => {
    const stageParam = searchParams.get('stage') || '';
    const decisionParam = searchParams.get('decision') || '';
    if (stageParam !== stageFilter) setStageFilter(stageParam);
    if (decisionParam !== decisionFilter) setDecisionFilter(decisionParam);
  }, [searchParams]);

  const loadInbox = async () => {
    setLoading(true);
    try {
      const res = await api.getInbox({
        page,
        stage: stageFilter || undefined,
        decision: decisionFilter || undefined,
        fy: fyFilter || undefined,
        month: monthFilter ? parseInt(monthFilter, 10) : undefined,
      });
      setData(res);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleFyChange = (val: string) => {
    setPage(1);
    setFyFilter(val);
    if (val) {
      localStorage.setItem('ap.inbox.fy', val);
    } else {
      localStorage.removeItem('ap.inbox.fy');
    }
  };

  const handleMonthChange = (val: string) => {
    setPage(1);
    setMonthFilter(val);
    if (val) {
      localStorage.setItem('ap.inbox.month', val);
    } else {
      localStorage.removeItem('ap.inbox.month');
    }
  };

  const handleSyncMailbox = async () => {
    setSyncingMailbox(true);
    setSyncFeedback(null);
    setSyncError(null);
    try {
      const res = await api.syncGmailMailbox(15);
      const mode = res.sync_mode === 'INCREMENTAL_HISTORY' ? 'History API' : 'Full Reconciliation';
      const msg = `Synced (${mode}): ${res.ingested_count} ingested, ${res.duplicates_skipped} duplicate(s) skipped, ${res.quarantined_count || 0} quarantined.`;
      setSyncFeedback(msg);
      await loadInbox();
    } catch (err: any) {
      setSyncError(err.message || 'Mailbox synchronization failed.');
    } finally {
      setSyncingMailbox(false);
    }
  };

  useEffect(() => {
    loadInbox();
  }, [page, stageFilter, decisionFilter, fyFilter, monthFilter]);

  // Poll inbox every 3 seconds if any item is currently processing
  useEffect(() => {
    const hasActiveProcessing = data?.items?.some(
      (inv) =>
        inv.stage === 'RECEIVED' ||
        inv.job_status === 'PROCESSING' ||
        inv.job_status === 'QUEUED'
    );
    if (!hasActiveProcessing) return;

    const timer = setInterval(() => {
      api.getInbox({
        page,
        stage: stageFilter || undefined,
        decision: decisionFilter || undefined,
      }).then((res) => {
        setData(res);
      }).catch((err) => console.error('Background poll error:', err));
    }, 3000);

    return () => clearInterval(timer);
  }, [data?.items, page, stageFilter, decisionFilter]);

  const handleStageChange = (newStage: string) => {
    setStageFilter(newStage);
    setPage(1);
    const next = new URLSearchParams(searchParams);
    if (newStage) next.set('stage', newStage);
    else next.delete('stage');
    setSearchParams(next);
  };

  const handleDecisionChange = (newDecision: string) => {
    setDecisionFilter(newDecision);
    setPage(1);
    const next = new URLSearchParams(searchParams);
    if (newDecision) next.set('decision', newDecision);
    else next.delete('decision');
    setSearchParams(next);
  };

  const getMsmeBadge = (deadlineStr: string | null | undefined) => {
    if (!deadlineStr) return <span className="text-slate-400 dark:text-slate-500">—</span>;
    const deadline = new Date(deadlineStr);
    const now = new Date();
    const diffTime = deadline.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) {
      return (
        <span className="inline-flex items-center gap-1 font-semibold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900/60 px-2 py-0.5 rounded text-[11px]" title="Overdue under Section 15 of MSMED Act">
          <Clock className="w-3 h-3 text-rose-600" />
          {deadlineStr.substring(0, 10)} ({Math.abs(diffDays)}d overdue)
        </span>
      );
    } else if (diffDays <= 7) {
      return (
        <span className="inline-flex items-center gap-1 font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-900/60 px-2 py-0.5 rounded text-[11px]" title="Due within 7 days under Section 15 of MSMED Act">
          <Clock className="w-3 h-3 text-amber-600" />
          {deadlineStr.substring(0, 10)} ({diffDays}d left)
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/60 px-2 py-0.5 rounded text-[11px]" title="Statutory 45-day deadline under MSMED Act">
          <Clock className="w-3 h-3 text-slate-400" />
          {deadlineStr.substring(0, 10)} ({diffDays}d left)
        </span>
      );
    }
  };

  const formatINR = (val: number | null) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const getWhyNextAction = (inv: any) => {
    if (inv.job_status === 'FAILED') {
      return (
        <span className="text-rose-600 dark:text-rose-400 font-medium text-[11px] block max-w-xs truncate" title={inv.job_error || 'Processing failed'}>
          Processing failed: {inv.job_error || 'Check document format'}
        </span>
      );
    }
    if (inv.job_status === 'PROCESSING' || inv.job_status === 'QUEUED' || inv.stage === 'RECEIVED') {
      return (
        <span className="text-indigo-600 dark:text-indigo-400 font-medium text-[11px] flex items-center gap-1">
          <RefreshCw className="w-3 h-3 animate-spin shrink-0" />
          Reading invoice…
        </span>
      );
    }
    const isUnreadable =
      inv.decision === 'FLAGGED_HITL_REVIEW' &&
      (!inv.invoice_number || inv.invoice_number === 'UNKNOWN' || !inv.total_amount);
    if (isUnreadable) {
      return (
        <span className="text-amber-700 dark:text-amber-400 font-medium text-[11px]">
          Couldn't read document — clearer copy needed
        </span>
      );
    }
    if (inv.decision === 'AUTO_APPROVED' || inv.decision === 'MATCH_CANDIDATE') {
      return (
        <span className="text-emerald-700 dark:text-emerald-400 font-medium text-[11px]">
          Clean match — ready to approve
        </span>
      );
    }
    if (inv.decision === 'MANUALLY_APPROVED') {
      return (
        <span className="text-slate-600 dark:text-slate-400 text-[11px]">
          Approved by AP team
        </span>
      );
    }
    if (inv.decision === 'QUARANTINED') {
      return (
        <span className="text-rose-700 dark:text-rose-400 font-medium text-[11px] block max-w-xs truncate" title={inv.decision_reason || 'Security review required'}>
          Quarantined: {inv.decision_reason || 'Security review'}
        </span>
      );
    }
    if (inv.decision_reason) {
      return (
        <span className="text-slate-700 dark:text-slate-300 text-[11px] block max-w-xs truncate" title={inv.decision_reason}>
          {inv.decision_reason}
        </span>
      );
    }
    return <span className="text-slate-400">—</span>;
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <InboxIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Invoice Inbox Ledger
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Server-paginated operational ledger of genuine supplier invoices and compliance states.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                handleUploadFile(e.target.files[0]);
                e.target.value = '';
              }
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-xs font-semibold text-white transition-colors shadow-2xs disabled:opacity-50"
            title="Direct 1-Click Invoice PDF Upload"
          >
            {uploading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Plus className="w-3.5 h-3.5" />
            )}
            <span>{uploading ? 'Uploading…' : 'Upload Invoice'}</span>
          </button>
          <button
            onClick={handleSyncMailbox}
            disabled={syncingMailbox}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs disabled:opacity-50"
            title="Incremental History API Sync"
          >
            <Mail className="w-3.5 h-3.5" />
            <span>{syncingMailbox ? 'Syncing...' : 'Sync Mailbox'}</span>
          </button>
          <button
            onClick={loadInbox}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Upload Feedback Banner */}
      {uploadFeedback && (
        <div className="bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800/60 rounded-xl p-3 text-xs text-indigo-800 dark:text-indigo-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {uploading ? (
              <RefreshCw className="w-4 h-4 text-indigo-600 dark:text-indigo-400 animate-spin shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            )}
            <span>{uploadFeedback}</span>
          </div>
          <button 
            onClick={() => setUploadFeedback(null)} 
            className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {uploadError && (
        <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-xl p-3 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{uploadError}</span>
          </div>
          <button 
            onClick={() => setUploadError(null)} 
            className="text-rose-600 dark:text-rose-400 hover:text-rose-800 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {/* 1-Click Upload Drag & Drop Zone */}
      <div 
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          if (e.dataTransfer.files?.[0]) {
            handleUploadFile(e.dataTransfer.files[0]);
          }
        }}
        className={`border-2 border-dashed rounded-xl p-3.5 transition-all flex items-center justify-between text-xs ${
          isDragOver 
            ? 'border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300' 
            : 'border-slate-200 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-700'
        }`}
      >
        <div className="flex items-center gap-2.5">
          <UploadCloud className={`w-4 h-4 ${isDragOver ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400'}`} />
          <span>
            <strong className="font-semibold text-slate-800 dark:text-slate-200">Drag and drop an invoice PDF here</strong> or{' '}
            <button 
              type="button" 
              onClick={() => fileInputRef.current?.click()}
              className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
            >
              browse files
            </button>{' '}
            for direct automated ingestion
          </span>
        </div>
        <span className="text-[11px] text-slate-400 font-mono hidden md:inline">PDF up to 50 MB</span>
      </div>

      {/* Sync Status Banner */}
      {syncFeedback && (
        <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 rounded-xl p-3 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>{syncFeedback}</span>
          </div>
          <button 
            onClick={() => setSyncFeedback(null)} 
            className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-800 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {syncError && (
        <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-xl p-3 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{syncError}</span>
          </div>
          <button 
            onClick={() => setSyncError(null)} 
            className="text-rose-600 dark:text-rose-400 hover:text-rose-800 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {/* Quick Segmented Ledger Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs border-b border-slate-200 dark:border-slate-800">
        {[
          { id: 'ALL', label: 'All Invoices' },
          { id: 'EXCEPTIONS', label: 'Needs Attention', badge: 'Action Required', badgeColor: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300' },
          { id: 'READY', label: 'Ready to Approve', badge: 'Clean Match', badgeColor: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300' },
          { id: 'APPROVED', label: 'Approved', badge: 'Complete', badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300' },
        ].map((tab) => {
          const isActive = activeQuickTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setQuickTab(tab.id)}
              className={`inline-flex items-center gap-2 px-3.5 py-2 font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                isActive
                  ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold'
                  : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <span>{tab.label}</span>
              {tab.badge && (
                <span className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${tab.badgeColor}`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Filter & Real-Time Search Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 rounded-xl text-xs shadow-2xs">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search supplier, invoice #, PO reference..."
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white pl-8 pr-8 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-medium hidden sm:flex">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Advanced:</span>
          </div>

          <select
            value={stageFilter}
            onChange={(e) => handleStageChange(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
          >
            <option value="">All Processing Stages</option>
            <option value="ACTION_REQUIRED">Action Required (Needs Human Review)</option>
            <option value="DECIDED">Decided (Evaluation Complete)</option>
            <option value="MATCHING">Matching (PO / GRN Verification)</option>
            <option value="EXTRACTED">Extracted (Data Parsed)</option>
            <option value="PARSING">Processing (OCR & AI Ingestion)</option>
            <option value="VALIDATING">Validating (Format & Sanity Checks)</option>
            <option value="RECEIVED">Received (Pending Pipeline)</option>
          </select>

          <select
            value={decisionFilter}
            onChange={(e) => handleDecisionChange(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
          >
            <option value="">All Verification Decisions</option>
            <option value="AUTO_APPROVED">Passed Straight-Through (All Gates Met)</option>
            <option value="MANUALLY_APPROVED">AP Team Approved (Human Sign-off)</option>
            <option value="NEEDS_REVIEW">Needs Review (Exceptions / Discrepancies)</option>
            <option value="REJECTED">Rejected by AP</option>
            <option value="QUARANTINED">Quarantined (Security / Fraud Block)</option>
          </select>

          {/* Stage A3 (OPP-04): Temporal Accounting Period Selectors */}
          <select
            value={fyFilter}
            onChange={(e) => handleFyChange(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs font-mono"
            aria-label="Filter by Financial Year"
          >
            <option value="">All Financial Years</option>
            <option value="FY 2026-27">FY 2026-27 (Current)</option>
            <option value="FY 2025-26">FY 2025-26</option>
            <option value="FY 2024-25">FY 2024-25</option>
          </select>

          <select
            value={monthFilter}
            onChange={(e) => handleMonthChange(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
            aria-label="Filter by Calendar Month"
          >
            <option value="">All Months</option>
            <option value="4">April</option>
            <option value="5">May</option>
            <option value="6">June</option>
            <option value="7">July</option>
            <option value="8">August</option>
            <option value="9">September</option>
            <option value="10">October</option>
            <option value="11">November</option>
            <option value="12">December</option>
            <option value="1">January</option>
            <option value="2">February</option>
            <option value="3">March</option>
          </select>

          {(fyFilter || monthFilter) && (
            <button
              onClick={() => {
                handleFyChange('');
                handleMonthChange('');
              }}
              className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline px-1 font-medium"
            >
              Clear Period
            </button>
          )}

          <div className="text-slate-500 dark:text-slate-400 font-mono text-[11px] tabular-nums pl-1">
            {filteredItems.length} records
          </div>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs">
        {(!data?.items || data.items.length === 0) ? (
          <div className="py-16 text-center text-slate-500 dark:text-slate-400 text-xs space-y-2">
            <FileText className="w-8 h-8 text-slate-400 dark:text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-700 dark:text-slate-200">No invoices found in review queue</div>
            <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              No invoices match your current filter. Drop an invoice PDF above or click Upload Invoice to ingest.
            </p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs space-y-2">
            <Search className="w-6 h-6 text-slate-400 mx-auto" />
            <p className="font-semibold text-slate-700 dark:text-slate-300">No invoices matched "{searchQuery}"</p>
            <button onClick={() => setSearchQuery('')} className="text-indigo-600 hover:underline font-medium">
              Clear search filter
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[920px]">
              <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider backdrop-blur-xs">
                <tr>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Invoice #</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">PO / WO Ref</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4">MSME Statutory Due</th>
                  <th className="py-3 px-4">Workflow Status</th>
                  <th className="py-3 px-4">Why / Next Action</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredItems.map((inv) => (
                  <tr 
                    key={inv.id} 
                    onClick={() => onSelectInvoice(inv.id)}
                    className="hover:bg-slate-50/90 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                        {inv.vendor_name || 'Unknown Supplier'}
                      </div>
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">{inv.vendor_gstin || 'No GSTIN'}</div>
                    </td>
                    <td className="py-3 px-4 font-mono font-medium text-slate-800 dark:text-slate-200">
                      {inv.invoice_number || inv.id.substring(0, 10)}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {(inv as any).invoice_date ? new Date((inv as any).invoice_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500 dark:text-slate-400">
                      {inv.po_reference || '—'}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-right text-slate-900 dark:text-white tabular-nums">
                      {formatINR(inv.total_amount)}
                    </td>
                    <td className="py-3 px-4 text-[11px] font-mono">
                      {getMsmeBadge(inv.msme_statutory_deadline)}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge invoice={inv} size="sm" />
                    </td>
                    <td className="py-3 px-4">
                      {getWhyNextAction(inv)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectInvoice(inv.id);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-50 dark:group-hover:bg-indigo-950/60 shadow-2xs transition-colors"
                      >
                        <span>Review</span>
                        <ArrowUpRight className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Server Pagination */}
        {data && data.total_pages > 1 && (
          <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
            <div>
              Page <span className="font-semibold text-slate-900 dark:text-slate-100">{data.page}</span> of{' '}
              <span className="font-semibold text-slate-900 dark:text-slate-100">{data.total_pages}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                disabled={data.page <= 1}
                onClick={() => setPage(data.page - 1)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Previous
              </button>
              <button
                disabled={data.page >= data.total_pages}
                onClick={() => setPage(data.page + 1)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                Next <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
