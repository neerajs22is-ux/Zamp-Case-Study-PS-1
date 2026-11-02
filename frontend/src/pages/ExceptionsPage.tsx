import React, { useEffect, useMemo, useState } from 'react';
import { 
  AlertTriangle, 
  Clock, 
  RefreshCw, 
  Info,
  Search,
  X,
  User,
  ShieldAlert,
  ChevronRight,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { api } from '../api/client';
import type { ExceptionItem } from '../types';

interface ExceptionsPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

export const ExceptionsPage: React.FC<ExceptionsPageProps> = ({ onSelectInvoice }) => {
  const [items, setItems] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'critical' | 'high_exposure' | 'unassigned'>('all');
  
  // Reassign Modal State
  const [reassignModalItem, setReassignModalItem] = useState<ExceptionItem | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [selectedOwnerId, setSelectedOwnerId] = useState<string>('');
  const [reassignReason, setReassignReason] = useState<string>('');
  const [reassignLoading, setReassignLoading] = useState<boolean>(false);
  const [reassignSuccessMsg, setReassignSuccessMsg] = useState<string | null>(null);

  const loadExceptions = async () => {
    setLoading(true);
    try {
      const res = await api.getExceptions();
      setItems(res.items || []);
    } catch (err: any) {
      console.error('Failed to load exceptions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamMembers = async () => {
    try {
      const res = await api.getMembers();
      if (res && res.items) {
        setTeamMembers(res.items.filter((m: any) => m.is_active));
      }
    } catch (err) {
      console.debug('Failed to load team members:', err);
    }
  };

  useEffect(() => {
    loadExceptions();
    loadTeamMembers();
  }, []);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  // Calculate relative days from now to deadline
  const getDeadlineUrgency = (deadlineStr: string | null) => {
    if (!deadlineStr) return { label: 'Standard Terms', days: null, urgency: 'normal' as const };
    const deadline = new Date(deadlineStr);
    const now = new Date();
    const diffMs = deadline.getTime() - now.getTime();
    const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

    if (days < 0) {
      return { label: `Overdue by ${Math.abs(days)}d`, days, urgency: 'overdue' as const };
    }
    if (days <= 5) {
      return { label: `Due in ${days}d`, days, urgency: 'critical' as const };
    }
    if (days <= 15) {
      return { label: `Due in ${days}d`, days, urgency: 'warning' as const };
    }
    return { label: `Due in ${days}d`, days, urgency: 'normal' as const };
  };

  // Key metrics calculation
  const totalExposure = useMemo(() => {
    return items.reduce((sum, item) => sum + (item.exposure_amount_inr || 0), 0);
  }, [items]);

  const criticalCount = useMemo(() => {
    return items.filter(item => {
      const urgency = getDeadlineUrgency(item.msme_statutory_deadline).urgency;
      return urgency === 'critical' || urgency === 'overdue';
    }).length;
  }, [items]);

  const highExposureCount = useMemo(() => {
    return items.filter(item => (item.exposure_amount_inr || 0) >= 25000).length;
  }, [items]);

  const unassignedCount = useMemo(() => {
    return items.filter(item => !item.assigned_user_id).length;
  }, [items]);

  // Filtered Items
  const filteredItems = useMemo(() => {
    return items.filter(item => {
      // Tab filtering
      if (activeTab === 'critical') {
        const u = getDeadlineUrgency(item.msme_statutory_deadline).urgency;
        if (u !== 'critical' && u !== 'overdue') return false;
      } else if (activeTab === 'high_exposure') {
        if ((item.exposure_amount_inr || 0) < 25000) return false;
      } else if (activeTab === 'unassigned') {
        if (item.assigned_user_id) return false;
      }

      // Search query filtering
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesVendor = (item.vendor_name || '').toLowerCase().includes(q);
        const matchesInv = (item.invoice_number || item.invoice_id || '').toLowerCase().includes(q);
        const matchesGate = (item.blocking_gate_name || '').toLowerCase().includes(q) || 
                            `gate ${item.blocking_gate_number}`.includes(q);
        const matchesOwner = (item.assigned_user_id || '').toLowerCase().includes(q);
        return matchesVendor || matchesInv || matchesGate || matchesOwner;
      }

      return true;
    });
  }, [items, activeTab, searchQuery]);

  // Handle reassign submit
  const handleReassignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reassignModalItem || !selectedOwnerId || !reassignReason.trim()) return;

    setReassignLoading(true);
    try {
      await api.reassignException(
        reassignModalItem.exception_id,
        selectedOwnerId,
        reassignReason.trim()
      );
      setReassignSuccessMsg(`Exception successfully reassigned to ${selectedOwnerId}`);
      setTimeout(() => {
        setReassignSuccessMsg(null);
        setReassignModalItem(null);
        setSelectedOwnerId('');
        setReassignReason('');
        loadExceptions();
      }, 1200);
    } catch (err: any) {
      alert(`Failed to reassign exception: ${err?.message || 'Server error'}`);
    } finally {
      setReassignLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-500 border border-amber-500/20">
              <AlertTriangle className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Exceptions Priority Queue
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Prioritized by legally verified MSME statutory deadline, then exposure amount. Governed by MSMED Act 2006.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadExceptions}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Queue
          </button>
        </div>
      </div>

      {/* Exposure & Urgency KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Total Blocked Exposure</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white font-mono tabular-nums">
            {formatINR(totalExposure)}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Across {items.length} open exceptions</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Critical MSME Deadlines</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-amber-600 dark:text-amber-400 font-mono tabular-nums">
            {criticalCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Less than 5 days remaining</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>High Exposure Items</span>
            <AlertCircle className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-indigo-600 dark:text-indigo-400 font-mono tabular-nums">
            {highExposureCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Exceeds ₹25,000 threshold</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span>Unassigned Queue</span>
            <User className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-200 font-mono tabular-nums">
            {unassignedCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Requires ownership assignment</div>
        </div>
      </div>

      {/* Statutory Sorting Rule Callout */}
      <div className="bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40 rounded-xl p-3 text-xs flex items-start gap-2.5">
        <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="text-slate-700 dark:text-slate-300 space-y-0.5 leading-relaxed">
          <span className="font-semibold text-slate-900 dark:text-slate-100">Statutory Urgency Invariant:</span> Snoozing or holding an exception never suppresses or shifts the statutory MSMED Act 45-day deadline. Penal interest compounds monthly at 3× RBI bank rate if settlement is delayed. All reassignments create an immutable audit record.
        </div>
      </div>

      {/* Controls: Segmented Tabs & Instant Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-1">
        {/* Segmented Filter Pills */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800/60 rounded-xl border border-slate-200/70 dark:border-slate-700/50 text-xs overflow-x-auto">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all shrink-0 ${
              activeTab === 'all'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            All Exceptions <span className="ml-1 text-[10px] opacity-75 font-mono">({items.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('critical')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all shrink-0 ${
              activeTab === 'critical'
                ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 shadow-2xs border border-rose-200 dark:border-rose-900/50'
                : 'text-slate-600 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-300'
            }`}
          >
            Critical MSME <span className="ml-1 text-[10px] opacity-75 font-mono">({criticalCount})</span>
          </button>
          <button
            onClick={() => setActiveTab('high_exposure')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all shrink-0 ${
              activeTab === 'high_exposure'
                ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 shadow-2xs border border-indigo-200 dark:border-indigo-900/50'
                : 'text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-300'
            }`}
          >
            High Exposure <span className="ml-1 text-[10px] opacity-75 font-mono">({highExposureCount})</span>
          </button>
          <button
            onClick={() => setActiveTab('unassigned')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all shrink-0 ${
              activeTab === 'unassigned'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            Unassigned <span className="ml-1 text-[10px] opacity-75 font-mono">({unassignedCount})</span>
          </button>
        </div>

        {/* Real-time search */}
        <div className="relative min-w-[240px]">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search vendor, invoice, gate..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-7 py-1.5 text-xs rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 transition-all shadow-2xs"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Exceptions Table */}
      <div className="bg-white dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs">
        {filteredItems.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs space-y-2">
            <Clock className="w-8 h-8 text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-300">
              {searchQuery ? 'No exceptions match your search criteria' : 'No unresolved exceptions in this view'}
            </div>
            <p className="text-slate-500 max-w-md mx-auto">
              {searchQuery
                ? 'Try broadening your search term or clearing the filter.'
                : 'All supplier invoices in this category have passed deterministic policy gates.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[760px]">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider sticky top-0 backdrop-blur-xs">
                <tr>
                  <th className="py-2.5 px-3">MSME Statutory Due</th>
                  <th className="py-2.5 px-3">Exposure Held</th>
                  <th className="py-2.5 px-3">Supplier & Invoice</th>
                  <th className="py-2.5 px-3">Blocking Policy Gate</th>
                  <th className="py-2.5 px-3">Assigned Owner</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredItems.map((e) => {
                  const deadlineInfo = getDeadlineUrgency(e.msme_statutory_deadline);

                  return (
                    <tr 
                      key={e.exception_id} 
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      onClick={() => onSelectInvoice(e.invoice_id)}
                    >
                      <td className="py-3 px-3 font-mono text-[11px]">
                        {e.msme_statutory_deadline ? (
                          <div className="space-y-0.5">
                            <span className="flex items-center gap-1.5 font-semibold text-slate-900 dark:text-slate-200">
                              <Clock className="w-3.5 h-3.5 text-slate-400" />
                              {e.msme_statutory_deadline.substring(0, 10)}
                            </span>
                            <div>
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                deadlineInfo.urgency === 'critical' || deadlineInfo.urgency === 'overdue'
                                  ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60'
                                  : deadlineInfo.urgency === 'warning'
                                  ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60'
                                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                              }`}>
                                {deadlineInfo.label}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-0.5">
                            <span className="text-slate-400 dark:text-slate-500 font-mono">Non-MSME</span>
                            <div className="text-[10px] text-slate-400">Standard Terms (30d)</div>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-900 dark:text-slate-100 font-bold tabular-nums text-sm">
                        {formatINR(e.exposure_amount_inr)}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-medium text-slate-900 dark:text-slate-200">
                          {e.vendor_name || 'Unidentified Supplier'}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          Inv: {e.invoice_number || e.invoice_id}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-500/10 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-500/20">
                          <span className="font-bold">Gate #{e.blocking_gate_number}:</span> {e.blocking_gate_name}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {e.assigned_user_id ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-slate-700 dark:text-slate-300 font-medium">
                            <User className="w-3 h-3 text-slate-400" />
                            {e.assigned_user_id}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-amber-600 dark:text-amber-400 border border-dashed border-amber-300 dark:border-amber-700">
                            Unassigned
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right" onClick={(ev) => ev.stopPropagation()}>
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            onClick={() => {
                              setReassignModalItem(e);
                              setSelectedOwnerId(e.assigned_user_id || (teamMembers[0]?.id || ''));
                              setReassignReason('');
                            }}
                            title="Reassign owner with audit log"
                            className="px-2 py-1 rounded-md text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-slate-200 dark:border-slate-800"
                          >
                            Reassign
                          </button>
                          <button
                            onClick={() => onSelectInvoice(e.invoice_id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 border border-indigo-200 dark:border-indigo-800 transition-colors"
                          >
                            Resolve <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reassign Modal */}
      {reassignModalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="p-1 rounded-md bg-indigo-500/10 text-indigo-500">
                  <User className="w-4 h-4" />
                </span>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  Reassign Exception Ownership
                </h3>
              </div>
              <button
                onClick={() => setReassignModalItem(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {reassignSuccessMsg ? (
              <div className="py-6 text-center space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {reassignSuccessMsg}
                </div>
              </div>
            ) : (
              <form onSubmit={handleReassignSubmit} className="space-y-3.5 text-xs">
                {/* Context snapshot */}
                <div className="bg-slate-50 dark:bg-slate-950 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 space-y-1">
                  <div className="text-slate-500">Target Invoice:</div>
                  <div className="font-mono font-bold text-slate-900 dark:text-white">
                    {reassignModalItem.invoice_number || reassignModalItem.invoice_id} ({reassignModalItem.vendor_name})
                  </div>
                  <div className="text-slate-500 flex items-center justify-between text-[11px] pt-1">
                    <span>Exposure at Risk:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-white">
                      {formatINR(reassignModalItem.exposure_amount_inr)}
                    </span>
                  </div>
                </div>

                {/* Team member selection */}
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Assign To Team Member:
                  </label>
                  <select
                    value={selectedOwnerId}
                    onChange={(e) => setSelectedOwnerId(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs"
                  >
                    <option value="" disabled>Select team member...</option>
                    {teamMembers.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.full_name} ({m.role.replace('_', ' ')}) - {m.email}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Audit Reason */}
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Mandatory Audit Reassignment Reason:
                  </label>
                  <textarea
                    rows={2}
                    value={reassignReason}
                    onChange={(e) => setReassignReason(e.target.value)}
                    placeholder="e.g. Reassigned to AP Lead for debit note vendor reconciliation..."
                    required
                    minLength={3}
                    className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs resize-none"
                  />
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    This reason will be recorded immutably in the compliance audit trail.
                  </div>
                </div>

                {/* Buttons */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => setReassignModalItem(null)}
                    disabled={reassignLoading}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reassignLoading || !selectedOwnerId || reassignReason.trim().length < 3}
                    className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold transition-colors disabled:opacity-50"
                  >
                    {reassignLoading ? 'Logging Reassignment...' : 'Confirm Reassignment'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
