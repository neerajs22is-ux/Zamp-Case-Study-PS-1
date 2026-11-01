import React, { useEffect, useState } from 'react';
import { 
  Inbox as InboxIcon, 
  Filter, 
  RefreshCw, 
  ArrowUpRight, 
  FileText,
  Clock,
  Mail,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { api } from '../api/client';
import type { InboxResponse } from '../types';

interface InboxPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

export const InboxPage: React.FC<InboxPageProps> = ({ onSelectInvoice }) => {
  const [data, setData] = useState<InboxResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState<string>('');
  const [decisionFilter, setDecisionFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [syncingMailbox, setSyncingMailbox] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const loadInbox = async () => {
    setLoading(true);
    try {
      const res = await api.getInbox({
        page,
        stage: stageFilter || undefined,
        decision: decisionFilter || undefined,
      });
      setData(res);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
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
  }, [page, stageFilter, decisionFilter]);

  const formatINR = (val: number | null) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'AUTO_APPROVED':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">AUTO_APPROVED</span>;
      case 'MANUALLY_APPROVED':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20">MANUALLY_APPROVED</span>;
      case 'NEEDS_REVIEW':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">NEEDS_REVIEW</span>;
      case 'REJECTED':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">REJECTED</span>;
      default:
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">{decision}</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <InboxIcon className="w-5 h-5 text-indigo-400" />
            Invoice Inbox Ledger
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Server-paginated operational ledger of genuine supplier invoices.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncMailbox}
            disabled={syncingMailbox}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white transition-colors disabled:opacity-50"
            title="Incremental History API Sync"
          >
            <Mail className="w-3.5 h-3.5" />
            <span>{syncingMailbox ? 'Syncing Mailbox...' : 'Sync Mailbox Now'}</span>
          </button>
          <button
            onClick={loadInbox}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Sync Status Banner */}
      {syncFeedback && (
        <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-lg p-3 text-xs text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{syncFeedback}</span>
          </div>
          <button 
            onClick={() => setSyncFeedback(null)} 
            className="text-emerald-400 hover:text-emerald-200 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {syncError && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-lg p-3 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{syncError}</span>
          </div>
          <button 
            onClick={() => setSyncError(null)} 
            className="text-rose-400 hover:text-rose-200 text-xs ml-2 font-mono"
          >
            &times;
          </button>
        </div>
      )}

      {/* Filter Strip */}
      <div className="flex flex-wrap items-center gap-3 bg-slate-900/60 border border-slate-800 p-3 rounded-lg text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <span>Filters:</span>
        </div>

        <select
          value={stageFilter}
          onChange={(e) => { setStageFilter(e.target.value); setPage(1); }}
          className="bg-slate-950 border border-slate-800 text-slate-300 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All Stages</option>
          <option value="RECEIVED">RECEIVED</option>
          <option value="VALIDATING">VALIDATING</option>
          <option value="PARSING">PARSING</option>
          <option value="EXTRACTED">EXTRACTED</option>
          <option value="MATCHING">MATCHING</option>
          <option value="DECIDED">DECIDED</option>
          <option value="ACTION_REQUIRED">ACTION_REQUIRED</option>
        </select>

        <select
          value={decisionFilter}
          onChange={(e) => { setDecisionFilter(e.target.value); setPage(1); }}
          className="bg-slate-950 border border-slate-800 text-slate-300 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All Decisions</option>
          <option value="AUTO_APPROVED">AUTO_APPROVED</option>
          <option value="MANUALLY_APPROVED">MANUALLY_APPROVED</option>
          <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
          <option value="REJECTED">REJECTED</option>
          <option value="QUARANTINED">QUARANTINED</option>
        </select>

        <div className="ml-auto text-slate-500 font-mono text-[11px]">
          Showing {data?.items.length || 0} of {data?.total_count || 0} records
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden">
        {(!data?.items || data.items.length === 0) ? (
          <div className="py-16 text-center text-slate-400 text-xs space-y-2">
            <FileText className="w-8 h-8 text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-300">No genuine invoices found in database ledger</div>
            <p className="text-slate-500 max-w-md mx-auto">
              In accordance with production truth rules, zero fake records exist. Upload genuine invoices in <span className="text-indigo-400 underline cursor-pointer">Connections</span> or configure Gmail API intake to populate this ledger.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">Supplier</th>
                  <th className="py-2.5 px-3">Invoice #</th>
                  <th className="py-2.5 px-3">PO / WO Ref</th>
                  <th className="py-2.5 px-3">Amount</th>
                  <th className="py-2.5 px-3">MSME Statutory Due</th>
                  <th className="py-2.5 px-3">Stage</th>
                  <th className="py-2.5 px-3">Decision</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.items.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-medium text-slate-200">{inv.vendor_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{inv.vendor_gstin || 'No GSTIN'}</div>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-300">
                      {inv.invoice_number || inv.id.substring(0, 10)}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400">
                      {inv.po_reference || '—'}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-200 tabular-nums">
                      {formatINR(inv.total_amount)}
                    </td>
                    <td className="py-3 px-3 text-[11px] font-mono text-slate-300">
                      {inv.msme_statutory_deadline ? (
                        <span className="flex items-center gap-1 text-rose-400">
                          <Clock className="w-3.5 h-3.5" />
                          {inv.msme_statutory_deadline.substring(0, 10)}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-400">
                      {inv.stage}
                    </td>
                    <td className="py-3 px-3">
                      {getDecisionBadge(inv.decision)}
                    </td>
                    <td className="py-3 px-3">
                      <button
                        onClick={() => onSelectInvoice(inv.id)}
                        className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium text-xs"
                      >
                        Inspect <ArrowUpRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
