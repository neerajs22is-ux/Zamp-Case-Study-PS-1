import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle, 
  ShieldAlert, 
  RefreshCw, 
  AlertTriangle,
  UserCheck,
  Clock,
  Layers,
  ChevronRight
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser } from '../types';

interface ApprovalsPageProps {
  currentUser?: AuthenticatedUser | null;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({ currentUser }) => {
  const navigate = useNavigate();
  const [approvals, setApprovals] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'pending' | 'all' | 'approved'>('pending');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const isAuditor = currentUser?.role === 'AUDITOR';
  const isController = currentUser?.role === 'CONTROLLER' || currentUser?.role === 'SYSTEM_ADMIN';

  const fetchApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getApprovals();
      setApprovals(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load approvals queue.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const formatINR = (amount?: number) => {
    if (amount === undefined || amount === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const filteredApprovals = approvals.filter((item) => {
    if (activeTab === 'pending') return item.status === 'PENDING_SECOND_APPROVAL';
    if (activeTab === 'approved') return item.status === 'APPROVED';
    return true; // 'all'
  });

  const pendingCount = approvals.filter((a) => a.status === 'PENDING_SECOND_APPROVAL').length;
  const approvedCount = approvals.filter((a) => a.status === 'APPROVED').length;

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Dual-Control Approvals Queue
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
              {pendingCount} Awaiting Second Sign-off
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Invoices meeting or exceeding ₹5,00,000 threshold requiring independent Financial Controller sign-off.
          </p>
        </div>

        <button
          onClick={fetchApprovals}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs self-start"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 2. Governance Policy Notice */}
      <div className="rounded-xl border border-purple-200 dark:border-purple-900/60 bg-purple-50/60 dark:bg-purple-950/20 p-4 flex items-start gap-3 shadow-2xs">
        <ShieldAlert className="w-5 h-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
        <div className="text-xs text-purple-900 dark:text-purple-200 space-y-1">
          <p className="font-semibold text-sm">
            Statutory Financial Control Invariant (Dual-Approval Policy)
          </p>
          <p className="text-purple-800 dark:text-purple-300 leading-relaxed">
            Per company financial delegations, disbursements meeting or exceeding <strong>₹5,00,000</strong> require two independent sign-offs. The second approval must be rendered by a <strong>Financial Controller</strong> or <strong>System Admin</strong> distinct from the initial approver.
          </p>
          <p className="text-[11px] text-purple-700 dark:text-purple-400 font-medium pt-0.5">
            Note: Review sign-off authorizes payment batch readiness; no bank funds transfer or ERP posting is executed.
          </p>
          {isAuditor && (
            <p className="text-[11px] text-purple-800 dark:text-purple-300 font-semibold pt-0.5">
              Read-only view: Auditor role can inspect approval queues but cannot submit sign-offs.
            </p>
          )}
          {!isController && !isAuditor && (
            <p className="text-[11px] text-purple-800 dark:text-purple-300 font-semibold pt-0.5">
              Financial Controller or System Admin credentials required to submit second approval.
            </p>
          )}
        </div>
      </div>

      {/* 3. Tab Bar */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-px overflow-x-auto whitespace-nowrap scrollbar-none">
        <button
          onClick={() => setActiveTab('pending')}
          className={`px-3 py-2 text-xs font-medium rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'pending'
              ? 'border-purple-600 text-purple-700 dark:border-purple-400 dark:text-purple-300 bg-white dark:bg-slate-900'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Awaiting Second Sign-off ({pendingCount})</span>
        </button>

        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-2 text-xs font-medium rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'all'
              ? 'border-purple-600 text-purple-700 dark:border-purple-400 dark:text-purple-300 bg-white dark:bg-slate-900'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>All Dual-Control Invoices ({approvals.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('approved')}
          className={`px-3 py-2 text-xs font-medium rounded-t-lg border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'approved'
              ? 'border-purple-600 text-purple-700 dark:border-purple-400 dark:text-purple-300 bg-white dark:bg-slate-900'
              : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <CheckCircle className="w-3.5 h-3.5" />
          <span>Completed Dual Approvals ({approvedCount})</span>
        </button>
      </div>

      {/* 4. Table / List */}
      {loading ? (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-xs text-slate-500">
          <RefreshCw className="w-6 h-6 mx-auto animate-spin mb-2 text-purple-600" />
          Loading dual-approval records...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/20 p-6 text-center text-rose-800 dark:text-rose-300 text-xs">
          <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-rose-600" />
          <p className="font-semibold text-sm">Failed to Load Approvals Queue</p>
          <p className="mt-1">{error}</p>
          <button
            onClick={fetchApprovals}
            className="mt-3 px-3 py-1.5 rounded-lg bg-rose-600 text-white font-medium hover:bg-rose-700"
          >
            Retry
          </button>
        </div>
      ) : filteredApprovals.length === 0 ? (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center space-y-2">
          <CheckCircle className="w-10 h-10 mx-auto text-emerald-500 mb-2" />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            {activeTab === 'pending' ? 'No Dual Approvals Pending' : 'No Records in this Tab'}
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {activeTab === 'pending'
              ? 'All high-value invoices (≥ ₹5,00,000) have received secondary sign-off or are not yet submitted for second approval.'
              : 'There are no approval records matching the selected tab filter.'}
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[720px]">
              <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Invoice & Supplier</th>
                  <th className="px-4 py-3">PO Reference</th>
                  <th className="px-4 py-3 text-right">Billed Amount</th>
                  <th className="px-4 py-3">First Approval</th>
                  <th className="px-4 py-3">Dual Status</th>
                  <th className="px-4 py-3 text-right">Authorization</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredApprovals.map((item) => (
                  <tr 
                    key={item.id} 
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    {/* Invoice & Supplier */}
                    <td className="px-4 py-3.5">
                      <div className="font-mono font-bold text-slate-900 dark:text-white">
                        {item.invoice_number || item.invoice_id}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                        {item.vendor_name || 'Unregistered Supplier'}
                      </div>
                      {item.vendor_gstin && (
                        <div className="text-[10px] font-mono text-slate-400">
                          {item.vendor_gstin}
                        </div>
                      )}
                    </td>

                    {/* PO Reference */}
                    <td className="px-4 py-3.5">
                      {item.po_reference ? (
                        <code className="px-1.5 py-0.5 rounded font-mono text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {item.po_reference}
                        </code>
                      ) : (
                        <span className="text-slate-400 italic">No PO ref</span>
                      )}
                    </td>

                    {/* Amount */}
                    <td className="px-4 py-3.5 text-right">
                      <div className="font-mono font-bold text-slate-900 dark:text-white tabular-nums text-sm">
                        {formatINR(item.total_amount)}
                      </div>
                      <div className="text-[10px] text-purple-600 dark:text-purple-400 font-medium">
                        &ge; ₹5,00,000 threshold
                      </div>
                    </td>

                    {/* First Approval Info */}
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300">
                        <UserCheck className="w-3.5 h-3.5 text-indigo-600" />
                        <span>{item.first_approver_name || item.first_approver_id || 'AP Lead'}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{item.first_approved_at ? item.first_approved_at.substring(0, 16).replace('T', ' ') : 'Pending'}</span>
                      </div>
                    </td>

                    {/* Status Chip */}
                    <td className="px-4 py-3.5">
                      {item.status === 'APPROVED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                          <CheckCircle className="w-3 h-3" />
                          Dual Approved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800 animate-pulse">
                          <ShieldAlert className="w-3 h-3" />
                          Awaiting Controller
                        </span>
                      )}
                    </td>

                    {/* Action / Authorization Column */}
                    <td className="px-4 py-3.5 text-right">
                      {item.can_approve ? (
                        <button
                          onClick={() => navigate(`/invoices/${item.invoice_id}?from=/approvals`)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold shadow-2xs transition-colors"
                        >
                          <span>Review & Sign Off</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <div className="inline-flex flex-col items-end gap-1">
                          <button
                            onClick={() => navigate(`/invoices/${item.invoice_id}?from=/approvals`)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 transition-colors"
                          >
                            <span>Inspect Record</span>
                            <ChevronRight className="w-3 h-3" />
                          </button>
                          {item.cannot_approve_reason && (
                            <span 
                              className="text-[10px] text-slate-400 max-w-[200px] truncate"
                              title={item.cannot_approve_reason}
                            >
                              {item.cannot_approve_reason}
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
