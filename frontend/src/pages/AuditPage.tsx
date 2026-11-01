import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  Download, 
  RefreshCw, 
  Search, 
  Lock
} from 'lucide-react';
import { api, getAuthToken } from '../api/client';
import type { AuditEventItem } from '../types';

export const AuditPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterInvoice, setFilterInvoice] = useState('');

  const loadAudit = async () => {
    setLoading(true);
    try {
      const res = await api.getAudit({
        invoice_id: filterInvoice || undefined,
      });
      setEvents(res.items || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudit();
  }, [filterInvoice]);

  const handleExportCSV = async () => {
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
      loadAudit(); // reload audit log to show that export was registered
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-400" />
            Append-Only Audit Trail & Compliance Ledger
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Database-enforced immutable ledger of all human reviews, dual approvals and pipeline transitions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export Audited CSV
          </button>
          <button
            onClick={loadAudit}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Immutability Invariant Callout */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs flex items-start gap-2.5">
        <Lock className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <div className="text-slate-300 space-y-0.5">
          <span className="font-semibold text-slate-200">Database-Level Immutability Active:</span> Table <code className="text-emerald-300 bg-slate-950 px-1 py-0.5 rounded">audit_events</code> is append-only. Triggers block any UPDATE or DELETE operations. Compensating financial corrections are stored as new atomic events.
        </div>
      </div>

      {/* Filter Strip */}
      <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800 p-3 rounded-lg text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <Search className="w-3.5 h-3.5 text-slate-500" />
          <span>Filter by Invoice ID:</span>
        </div>
        <input
          type="text"
          value={filterInvoice}
          onChange={(e) => setFilterInvoice(e.target.value)}
          placeholder="e.g. inv_..."
          className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 font-mono"
        />
        <div className="ml-auto text-slate-500 font-mono text-[11px]">
          Showing {events.length} immutable events
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden">
        {events.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs space-y-2">
            <ShieldCheck className="w-8 h-8 text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-300">No audit events recorded yet</div>
            <p className="text-slate-500 max-w-md mx-auto">
              Every invoice upload, automated rule evaluation, human exception triage, and dual approval creates an immutable event in this table.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Actor / Role</th>
                  <th className="py-2.5 px-3">Invoice Ref</th>
                  <th className="py-2.5 px-3">Operational Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {e.timestamp.replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-bold">
                        {e.action}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">
                      <div>{e.actor_id}</div>
                      <div className="text-[10px] text-slate-500">{e.actor_role}</div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {e.invoice_id || '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 font-sans">
                      {e.reason || '—'}
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
