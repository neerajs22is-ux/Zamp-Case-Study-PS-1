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
  AlertCircle,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
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
          <button
            onClick={handleSyncMailbox}
            disabled={syncingMailbox}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-xs font-medium text-white transition-colors shadow-2xs disabled:opacity-50"
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

      {/* Filter Strip */}
      <div className="flex flex-wrap items-center gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 rounded-xl text-xs shadow-2xs">
        <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-medium">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span>Filters:</span>
        </div>

        <select
          value={stageFilter}
          onChange={(e) => { setStageFilter(e.target.value); setPage(1); }}
          className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
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
          className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 text-xs"
        >
          <option value="">All Decisions</option>
          <option value="AUTO_APPROVED">AUTO_APPROVED</option>
          <option value="MANUALLY_APPROVED">MANUALLY_APPROVED</option>
          <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
          <option value="REJECTED">REJECTED</option>
          <option value="QUARANTINED">QUARANTINED</option>
        </select>

        <div className="ml-auto text-slate-500 dark:text-slate-400 font-mono text-[11px] tabular-nums">
          Showing {data?.items.length || 0} of {data?.total_count || 0} records
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs">
        {(!data?.items || data.items.length === 0) ? (
          <div className="py-16 text-center text-slate-500 dark:text-slate-400 text-xs space-y-2">
            <FileText className="w-8 h-8 text-slate-400 dark:text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-700 dark:text-slate-200">No invoices found in review queue</div>
            <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              No invoices match your current filter. Upload an invoice in <span className="text-indigo-600 dark:text-indigo-400 underline cursor-pointer">Connections</span> or configure intake sources to populate this list.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Invoice #</th>
                  <th className="py-3 px-4">PO / WO Ref</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4">MSME Statutory Due</th>
                  <th className="py-3 px-4">Workflow Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {data.items.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900 dark:text-slate-100">{inv.vendor_name || 'Unknown Supplier'}</div>
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">{inv.vendor_gstin || 'No GSTIN'}</div>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700 dark:text-slate-300">
                      {inv.invoice_number || inv.id.substring(0, 10)}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500 dark:text-slate-400">
                      {inv.po_reference || '—'}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-right text-slate-900 dark:text-slate-100 tabular-nums">
                      {formatINR(inv.total_amount)}
                    </td>
                    <td className="py-3 px-4 text-[11px] font-mono">
                      {inv.msme_statutory_deadline ? (
                        <span className="inline-flex items-center gap-1 font-medium text-rose-600 dark:text-rose-400">
                          <Clock className="w-3.5 h-3.5" />
                          {inv.msme_statutory_deadline.substring(0, 10)}
                        </span>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge invoice={inv} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => onSelectInvoice(inv.id)}
                        className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium text-xs hover:underline"
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
