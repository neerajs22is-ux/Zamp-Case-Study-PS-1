import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldCheck, 
  Download, 
  RefreshCw, 
  Search, 
  Lock, 
  Filter, 
  X, 
  ExternalLink, 
  ChevronRight, 
  CheckCircle2, 
  Copy, 
  Check,
  UserCheck,
  Shield,
  FileText,
  Code
} from 'lucide-react';
import { api, getAuthToken } from '../api/client';
import type { AuditEventItem, AuthenticatedUser } from '../types';

interface AuditPageProps {
  currentUser?: AuthenticatedUser | null;
}

const ACTION_LABELS: Record<string, { label: string; color: string; category: 'invoice' | 'approval' | 'security' | 'system' }> = {
  APPROVE_AP_REVIEW: { label: 'Approved (AP Review)', color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40', category: 'approval' },
  APPROVE_UNDISPUTED: { label: 'Approved (Undisputed)', color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40', category: 'approval' },
  DUAL_APPROVAL_SIGNED: { label: 'Dual Approval Signed', color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800/40', category: 'approval' },
  REJECT_INVOICE: { label: 'Rejected Invoice', color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40', category: 'invoice' },
  QUARANTINE: { label: 'Quarantined', color: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40', category: 'invoice' },
  HOLD_PENDING_EVIDENCE: { label: 'Hold (Evidence)', color: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40', category: 'invoice' },
  REQUEST_SUPPLIER_CORRECTION: { label: 'Supplier Correction', color: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40', category: 'invoice' },
  RAISE_DEBIT_NOTE: { label: 'Debit Note Raised', color: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800/40', category: 'invoice' },
  ESCALATE: { label: 'Escalated', color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800/40', category: 'invoice' },
  EXCEPTION_REASSIGNED: { label: 'Exception Reassigned', color: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800/40', category: 'invoice' },
  DOCUMENT_UPLOADED: { label: 'Document Uploaded', color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700', category: 'system' },
  DOCUMENT_QUARANTINED: { label: 'File Quarantined', color: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40', category: 'system' },
  AUDIT_TRAIL_EXPORTED: { label: 'Audit Exported', color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800/40', category: 'security' },
  USER_INVITED: { label: 'User Invited', color: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40', category: 'security' },
  INVITATION_ACCEPTED: { label: 'Invitation Accepted', color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40', category: 'security' },
  INVITATION_REVOKED: { label: 'Invitation Revoked', color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40', category: 'security' },
  ROLE_UPDATED: { label: 'Role Updated', color: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800/40', category: 'security' },
  USER_DEACTIVATED: { label: 'User Deactivated', color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40', category: 'security' },
  ACCESS_REQUEST_CREATED: { label: 'Access Requested', color: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40', category: 'security' },
  ACCESS_REQUEST_APPROVED: { label: 'Access Approved', color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40', category: 'security' },
  ACCESS_REQUEST_REJECTED: { label: 'Access Rejected', color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40', category: 'security' },
};

export const AuditPage: React.FC<AuditPageProps> = ({ currentUser }) => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [filterInvoice, setFilterInvoice] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterActor, setFilterActor] = useState('');
  const [activeCategory, setActiveCategory] = useState<'all' | 'approval' | 'invoice' | 'security'>('all');
  
  // Detail Drawer State
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showJsonRaw, setShowJsonRaw] = useState(false);

  const canExport = currentUser?.role && ['AUDITOR', 'CONTROLLER', 'SYSTEM_ADMIN'].includes(currentUser.role);

  const loadAudit = async () => {
    setLoading(true);
    try {
      const res = await api.getAudit({
        invoice_id: filterInvoice.trim() || undefined,
        action: filterAction || undefined,
        actor_id: filterActor.trim() || undefined,
        limit: 100
      });
      setEvents(res.items || []);
    } catch (err: any) {
      console.error('Failed to load audit events:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const handler = setTimeout(() => {
      loadAudit();
    }, 200);
    return () => clearTimeout(handler);
  }, [filterInvoice, filterAction, filterActor]);

  // Filtered by category tab
  const filteredEvents = useMemo(() => {
    if (activeCategory === 'all') return events;
    return events.filter(e => {
      const meta = ACTION_LABELS[e.action];
      return meta && meta.category === activeCategory;
    });
  }, [events, activeCategory]);

  // Executive Metric Counts
  const approvalCount = useMemo(() => {
    return events.filter(e => ACTION_LABELS[e.action]?.category === 'approval').length;
  }, [events]);

  const invoiceDecisionCount = useMemo(() => {
    return events.filter(e => ACTION_LABELS[e.action]?.category === 'invoice').length;
  }, [events]);

  const securityGovernanceCount = useMemo(() => {
    return events.filter(e => ACTION_LABELS[e.action]?.category === 'security').length;
  }, [events]);

  const handleExportCSV = async () => {
    if (!canExport) {
      alert('CSV export is restricted to Auditor, Financial Controller, or System Admin.');
      return;
    }

    try {
      const response = await fetch('/api/v1/audit/export', {
        headers: {
          Authorization: `Bearer ${getAuthToken()}`,
        },
      });
      if (!response.ok) {
        throw new Error('CSV export failed. Ensure role has AUDITOR/CONTROLLER/SYSTEM_ADMIN authority.');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ap_command_center_audit_${new Date().toISOString().substring(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      
      setExportNotice('Export complete. An immutable AUDIT_TRAIL_EXPORTED event has been logged.');
      setTimeout(() => setExportNotice(null), 5000);
      loadAudit();
    } catch (err: any) {
      alert(err?.message || 'Export error');
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const hasActiveFilters = Boolean(filterInvoice || filterAction || filterActor || activeCategory !== 'all');

  const resetFilters = () => {
    setFilterInvoice('');
    setFilterAction('');
    setFilterActor('');
    setActiveCategory('all');
  };

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Immutable Audit Ledger
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40 font-mono">
              <Lock className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
              Append-Only (PostgreSQL Trigger Enforced)
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Authoritative, tamper-evident chronological record of human exception determinations, dual approvals, and automated pipeline actions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            disabled={!canExport}
            title={!canExport ? 'Export restricted to Auditor, Controller, or System Admin' : 'Export immutable audit trail to CSV'}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-2xs transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download className="w-3.5 h-3.5" />
            Export Audited CSV
          </button>

          <button
            onClick={loadAudit}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Audit Ledger Metrics Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Total Logged Events</span>
            <Shield className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white font-mono tabular-nums">
            {events.length}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Append-only sequence</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Approval Decisions</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono tabular-nums">
            {approvalCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Dual & AP sign-offs</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Triage Determinations</span>
            <FileText className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-amber-600 dark:text-amber-400 font-mono tabular-nums">
            {invoiceDecisionCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Holds, notes, rejects</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Team & Access Governance</span>
            <UserCheck className="w-4 h-4 text-sky-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-sky-600 dark:text-sky-400 font-mono tabular-nums">
            {securityGovernanceCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Invitations & RBAC</div>
        </div>
      </div>

      {/* Export feedback toast */}
      {exportNotice && (
        <div className="p-3.5 rounded-xl border bg-emerald-50/80 border-emerald-200 text-emerald-900 dark:bg-emerald-950/30 dark:border-emerald-800/40 dark:text-emerald-200 text-xs flex items-start gap-2.5 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{exportNotice}</div>
          <button onClick={() => setExportNotice(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {/* Category Segmented Tabs */}
      <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800/60 rounded-xl border border-slate-200/70 dark:border-slate-700/50 text-xs overflow-x-auto whitespace-nowrap max-w-full">
        <button
          onClick={() => setActiveCategory('all')}
          className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
            activeCategory === 'all'
              ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          All Events <span className="ml-1 text-[10px] opacity-75 font-mono">({events.length})</span>
        </button>
        <button
          onClick={() => setActiveCategory('approval')}
          className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
            activeCategory === 'approval'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 shadow-2xs border border-emerald-200 dark:border-emerald-900/50'
              : 'text-slate-600 dark:text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-300'
          }`}
        >
          Approvals & Sign-Offs <span className="ml-1 text-[10px] opacity-75 font-mono">({approvalCount})</span>
        </button>
        <button
          onClick={() => setActiveCategory('invoice')}
          className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
            activeCategory === 'invoice'
              ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 shadow-2xs border border-amber-200 dark:border-amber-900/50'
              : 'text-slate-600 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-300'
          }`}
        >
          Invoice Triage <span className="ml-1 text-[10px] opacity-75 font-mono">({invoiceDecisionCount})</span>
        </button>
        <button
          onClick={() => setActiveCategory('security')}
          className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
            activeCategory === 'security'
              ? 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 shadow-2xs border border-sky-200 dark:border-sky-900/50'
              : 'text-slate-600 dark:text-slate-400 hover:text-sky-600 dark:hover:text-sky-300'
          }`}
        >
          Access & Team Security <span className="ml-1 text-[10px] opacity-75 font-mono">({securityGovernanceCount})</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-3.5 rounded-xl shadow-2xs text-xs flex flex-wrap items-center gap-3">
        {/* Invoice ID Filter */}
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            value={filterInvoice}
            onChange={(e) => setFilterInvoice(e.target.value)}
            placeholder="Filter by Invoice ID (e.g. inv_...)"
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 font-mono text-xs"
          />
        </div>

        {/* Action Dropdown Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            aria-label="Filter by Action"
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs"
          >
            <option value="">All Specific Actions</option>
            <option value="APPROVE_AP_REVIEW">Approved (AP Review)</option>
            <option value="APPROVE_UNDISPUTED">Approved (Undisputed)</option>
            <option value="DUAL_APPROVAL_SIGNED">Dual Approval Signed</option>
            <option value="REJECT_INVOICE">Rejected Invoice</option>
            <option value="QUARANTINE">Quarantined</option>
            <option value="HOLD_PENDING_EVIDENCE">Hold Pending Evidence</option>
            <option value="REQUEST_SUPPLIER_CORRECTION">Supplier Correction</option>
            <option value="RAISE_DEBIT_NOTE">Debit Note Raised</option>
            <option value="ESCALATE">Escalated</option>
            <option value="EXCEPTION_REASSIGNED">Exception Reassigned</option>
            <option value="USER_INVITED">User Invited</option>
            <option value="INVITATION_ACCEPTED">Invitation Accepted</option>
            <option value="INVITATION_REVOKED">Invitation Revoked</option>
            <option value="AUDIT_TRAIL_EXPORTED">Audit Trail Exported</option>
          </select>
        </div>

        {/* Actor ID Filter */}
        <div className="flex items-center gap-2 min-w-[150px]">
          <input
            type="text"
            value={filterActor}
            onChange={(e) => setFilterActor(e.target.value)}
            placeholder="Actor ID (e.g. usr_...)"
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 font-mono text-xs"
          />
        </div>

        {hasActiveFilters && (
          <button
            onClick={resetFilters}
            className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 px-2 py-1 rounded text-xs"
          >
            <X className="w-3 h-3" />
            Reset
          </button>
        )}

        <div className="w-full sm:w-auto sm:ml-auto text-slate-500 dark:text-slate-400 font-mono text-[11px]">
          Showing {filteredEvents.length} event{filteredEvents.length === 1 ? '' : 's'}
        </div>
      </div>

      {/* Main Audit Table */}
      <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs overflow-hidden">
        {filteredEvents.length === 0 ? (
          <div className="py-16 text-center text-xs space-y-2 px-4">
            <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto" />
            <div className="font-semibold text-slate-700 dark:text-slate-300">
              No audit events found
            </div>
            <p className="text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
              {hasActiveFilters 
                ? 'No audit events match the current filter criteria.'
                : 'Every human review, automated evaluation, and dual sign-off generates an append-only event in this ledger.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[800px]">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider sticky top-0 backdrop-blur-xs">
                <tr>
                  <th className="py-2.5 px-4">Timestamp (UTC)</th>
                  <th className="py-2.5 px-4">Action</th>
                  <th className="py-2.5 px-4">Actor / Role</th>
                  <th className="py-2.5 px-4">Invoice Reference</th>
                  <th className="py-2.5 px-4">Reason / Operational Justification</th>
                  <th className="py-2.5 px-4 text-right">State Diff</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-[11px]">
                {filteredEvents.map((e) => {
                  const actionMeta = ACTION_LABELS[e.action] || {
                    label: e.action,
                    color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
                    category: 'system' as const
                  };

                  return (
                    <tr 
                      key={e.id}
                      onClick={() => setSelectedEvent(e)}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors cursor-pointer group"
                    >
                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {e.timestamp ? e.timestamp.replace('T', ' ').substring(0, 19) : '—'}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-sans font-semibold border ${actionMeta.color}`}>
                          {actionMeta.label}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">{e.actor_id}</div>
                        <div className="text-[10px] text-slate-400 font-sans">{e.actor_role}</div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        {e.invoice_id ? (
                          <Link
                            to={`/invoices/${e.invoice_id}`}
                            onClick={(ev) => ev.stopPropagation()}
                            className="text-indigo-600 dark:text-indigo-400 hover:underline font-bold inline-flex items-center gap-1"
                          >
                            <span>{e.invoice_id}</span>
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        ) : (
                          <span className="text-slate-400 font-sans">—</span>
                        )}
                      </td>

                      <td className="py-3 px-4 font-sans text-slate-700 dark:text-slate-300 max-w-xs truncate">
                        {e.reason || '—'}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <span className="text-indigo-600 dark:text-indigo-400 group-hover:underline inline-flex items-center gap-1 font-sans text-xs font-semibold">
                          Inspect Diff
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Right-Hand Detail Drawer: Before/After State Diff */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end animate-in fade-in duration-150">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 h-full shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <h2 className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                  Event: {selectedEvent.id}
                </h2>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-2 min-w-[40px] min-h-[40px] flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="Close audit event details"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-4 text-xs">
              {/* Event Metadata */}
              <div className="grid grid-cols-2 gap-3 font-mono">
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block font-sans">Action</span>
                  <span className="font-bold text-slate-900 dark:text-white text-xs">{selectedEvent.action}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block font-sans">Timestamp (UTC)</span>
                  <span className="text-slate-700 dark:text-slate-300 text-xs">{selectedEvent.timestamp}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block font-sans">Actor</span>
                  <span className="font-bold text-slate-900 dark:text-white text-xs">{selectedEvent.actor_id}</span>
                  <span className="text-[10px] text-slate-400 block font-sans">{selectedEvent.actor_role}</span>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60">
                  <span className="text-slate-400 text-[11px] block font-sans">Target Invoice</span>
                  {selectedEvent.invoice_id ? (
                    <Link
                      to={`/invoices/${selectedEvent.invoice_id}`}
                      className="text-indigo-600 dark:text-indigo-400 hover:underline font-bold text-xs inline-flex items-center gap-1"
                    >
                      <span>{selectedEvent.invoice_id}</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  ) : (
                    <span className="text-slate-400 font-sans">—</span>
                  )}
                </div>
              </div>

              {/* Justification Reason */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5 font-sans">
                  Operational Justification & Audit Reason
                </h3>
                <div className="p-3.5 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60 text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
                  {selectedEvent.reason || 'No written reason recorded for this system action.'}
                </div>
              </div>

              {/* View Toggle: Visual Diff vs Raw JSON */}
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 font-sans">
                  State Mutation Payloads
                </h3>
                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-[11px]">
                  <button
                    onClick={() => setShowJsonRaw(false)}
                    className={`px-2 py-0.5 rounded ${!showJsonRaw ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs' : 'text-slate-500'}`}
                  >
                    Visual Diff
                  </button>
                  <button
                    onClick={() => setShowJsonRaw(true)}
                    className={`px-2 py-0.5 rounded flex items-center gap-1 ${showJsonRaw ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs' : 'text-slate-500'}`}
                  >
                    <Code className="w-3 h-3" />
                    Raw JSON
                  </button>
                </div>
              </div>

              {!showJsonRaw ? (
                <div className="grid grid-cols-2 gap-3">
                  {/* Before State */}
                  <div className="p-3 bg-rose-50/40 dark:bg-rose-950/20 border border-rose-200/60 dark:border-rose-900/40 rounded-xl space-y-1.5 font-mono">
                    <span className="text-rose-700 dark:text-rose-400 font-bold block text-[11px] font-sans">
                      Before State
                    </span>
                    {selectedEvent.before_state ? (
                      <div className="space-y-1 text-[11px] text-slate-700 dark:text-slate-300">
                        {Object.entries(selectedEvent.before_state).map(([k, v]) => (
                          <div key={k} className="truncate">
                            <span className="text-slate-400">{k}:</span> <strong>{String(v)}</strong>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-400 text-[11px] italic font-sans">Initial creation / None</span>
                    )}
                  </div>

                  {/* After State */}
                  <div className="p-3 bg-emerald-50/40 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/40 rounded-xl space-y-1.5 font-mono">
                    <span className="text-emerald-700 dark:text-emerald-400 font-bold block text-[11px] font-sans">
                      After State
                    </span>
                    {selectedEvent.after_state ? (
                      <div className="space-y-1 text-[11px] text-slate-700 dark:text-slate-300">
                        {Object.entries(selectedEvent.after_state).map(([k, v]) => (
                          <div key={k} className="truncate">
                            <span className="text-slate-400">{k}:</span> <strong className="text-emerald-600 dark:text-emerald-400">{String(v)}</strong>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-400 text-[11px] italic font-sans">Unmodified</span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto relative group">
                  <button
                    onClick={() => copyToClipboard(JSON.stringify(selectedEvent, null, 2), 'raw_json')}
                    className="absolute right-2.5 top-2.5 p-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                    title="Copy JSON Payload"
                  >
                    {copiedId === 'raw_json' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                  <pre>{JSON.stringify(selectedEvent, null, 2)}</pre>
                </div>
              )}

              {/* Correlation ID & Source Reference */}
              <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-sans">Correlation ID:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-700 dark:text-slate-300">{selectedEvent.correlation_id || '—'}</span>
                    {selectedEvent.correlation_id && (
                      <button
                        onClick={() => copyToClipboard(selectedEvent.correlation_id!, 'corr')}
                        className="text-slate-400 hover:text-slate-600"
                      >
                        {copiedId === 'corr' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                      </button>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-sans">Source Reference:</span>
                  <span className="text-slate-700 dark:text-slate-300 truncate max-w-[240px]">
                    {selectedEvent.source_reference || '—'}
                  </span>
                </div>
              </div>

              {/* Immutability Invariant */}
              <div className="p-3 bg-slate-50 dark:bg-slate-950/40 rounded-xl border border-slate-100 dark:border-slate-800/60 text-[11px] text-slate-500 space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300 font-sans">
                  <Lock className="w-3.5 h-3.5 text-indigo-500" />
                  Append-Only Ledger Guarantee
                </div>
                <p className="leading-relaxed font-sans">
                  This audit record is sealed by PostgreSQL trigger constraint. `UPDATE` and `DELETE` operations on `audit_events` are strictly rejected by the database engine.
                </p>
              </div>
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 flex justify-end">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shadow-2xs"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
