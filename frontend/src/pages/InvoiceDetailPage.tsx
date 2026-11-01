import React, { useEffect, useState } from 'react';
import { 
  ArrowLeft, 
  FileText, 
  ShieldCheck, 
  ExternalLink,
  Layers,
  RefreshCw
} from 'lucide-react';
import { api } from '../api/client';

interface InvoiceDetailPageProps {
  invoiceId: string;
  onBack: () => void;
}

export const InvoiceDetailPage: React.FC<InvoiceDetailPageProps> = ({ invoiceId, onBack }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const loadDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getInvoiceDetail(invoiceId);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve invoice detail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [invoiceId]);

  const handleAction = async (action: string) => {
    if (!actionReason.trim()) {
      alert('Please enter an operational justification reason before executing this action.');
      return;
    }

    setActionLoading(true);
    try {
      await api.executeAction(invoiceId, action, actionReason);
      setActionReason('');
      loadDetail();
    } catch (err: any) {
      alert(`Action rejected: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const formatINR = (val?: number) => {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-xs text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
        Retrieving authoritative 3-pane invoice data...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 text-xs text-center space-y-3">
        <div className="text-rose-400 font-semibold">{error || 'Invoice not found.'}</div>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 text-slate-200 text-xs"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to Inbox
        </button>
      </div>
    );
  }

  const { invoice, document, extracted_fields, lines, match_gates, approval, timeline } = data;

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white font-mono">
                {invoice.invoice_number || invoice.id}
              </h1>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {invoice.stage}
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {invoice.decision}
              </span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Vendor: <span className="text-slate-200 font-medium">{invoice.vendor_name || 'Unidentified'}</span> | Total: <span className="font-mono text-slate-100">{formatINR(invoice.total_amount)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3-Pane Operational Inspection Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* PANE 1: Original Document & Extracted Fields */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col h-[750px] overflow-hidden">
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-indigo-400" />
              Pane 1: Document & Extraction
            </h2>
            {document?.preview_url && (
              <a 
                href={document.preview_url} 
                target="_blank" 
                rel="noreferrer"
                className="text-[11px] text-indigo-400 hover:underline flex items-center gap-1"
              >
                Full PDF <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs">
            {document ? (
              <div className="bg-slate-950 p-2.5 rounded border border-slate-800 text-[11px] font-mono space-y-1">
                <div><span className="text-slate-500">Filename:</span> {document.filename}</div>
                <div><span className="text-slate-500">SHA-256:</span> {document.sha256?.substring(0, 20)}...</div>
                <div><span className="text-slate-500">Size:</span> {(document.size_bytes / 1024).toFixed(1)} KB</div>
              </div>
            ) : (
              <div className="text-slate-500 text-center py-4">No original file attached</div>
            )}

            <div>
              <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Traceable Field Evidence
              </h3>
              {(!extracted_fields || extracted_fields.length === 0) ? (
                <div className="text-slate-500 text-center py-6">
                  Zero extracted fields. Extraction pipeline pending.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {extracted_fields.map((f: any, idx: number) => (
                    <div key={idx} className="bg-slate-950/80 p-2 rounded border border-slate-800/80 flex items-center justify-between text-xs">
                      <div>
                        <div className="text-slate-400 font-mono text-[11px]">{f.field_name}</div>
                        <div className="text-slate-200 font-medium">{f.value || '—'}</div>
                      </div>
                      <div className="text-right font-mono text-[10px] text-slate-500">
                        {f.confidence !== null ? `${(f.confidence * 100).toFixed(0)}% conf` : 'unverified'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* PANE 2: 5-Way Reconciliation & Lines */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col h-[750px] overflow-hidden">
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Pane 2: Line Reconciliation
            </h2>
            <span className="text-[11px] font-mono text-slate-400">PO: {invoice.po_reference || 'NONE'}</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs">
            {(!lines || lines.length === 0) ? (
              <div className="text-slate-500 text-center py-8">
                No parsed line items. Line extraction pending.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {lines.map((l: any) => (
                  <div key={l.line_number} className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-slate-200 font-sans">{l.description}</div>
                      <div className="text-slate-500">{l.quantity} units @ {formatINR(l.rate)}</div>
                    </div>
                    <div className="text-slate-100 font-bold tabular-nums">
                      {formatINR(l.total)}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Net Payable Waterfall */}
            <div className="bg-slate-950 p-3 rounded border border-slate-800 space-y-1.5 mt-4 text-xs font-mono">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-800 pb-1 mb-2 font-sans">
                Net Payable Waterfall
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Subtotal Billed:</span>
                <span className="text-slate-200 tabular-nums">{formatINR(invoice.subtotal)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>GST Tax (Reconciled):</span>
                <span className="text-slate-200 tabular-nums">{formatINR(invoice.tax_amount)}</span>
              </div>
              <div className="flex justify-between text-slate-200 font-bold border-t border-slate-800 pt-1">
                <span>Net Payable:</span>
                <span className="text-emerald-400 tabular-nums">{formatINR(invoice.net_payable || invoice.total_amount)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* PANE 3: Decision Trace, Dual Control & Actions */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 flex flex-col h-[750px] overflow-hidden">
          <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
            <h2 className="text-xs font-semibold text-slate-200 uppercase flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              Pane 3: Match Gates & Actions
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs">
            {/* 17 Gates Summary */}
            <div>
              <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Deterministic Policy Gates
              </h3>
              {(!match_gates || match_gates.length === 0) ? (
                <div className="text-slate-500 text-center py-4 bg-slate-950 rounded border border-slate-800">
                  AOP Match engine evaluation pending.
                </div>
              ) : (
                <div className="space-y-1 text-[11px] font-mono">
                  {match_gates.map((g: any) => (
                    <div key={g.gate_number} className="flex items-center justify-between p-1.5 rounded bg-slate-950 border border-slate-800/60">
                      <span className="text-slate-300">#{g.gate_number} {g.gate_name}</span>
                      <span className={g.status === 'PASS' ? 'text-emerald-400' : (g.status === 'FAIL' ? 'text-rose-400' : 'text-amber-400')}>
                        {g.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Dual Control Status */}
            {approval && (
              <div className="bg-indigo-950/30 border border-indigo-800/40 rounded p-3 text-[11px] space-y-1">
                <div className="font-semibold text-indigo-300">Dual-Control Approval Gate:</div>
                <div className="text-slate-300">First Approver: {approval.first_approver_id || 'Pending'}</div>
                <div className="text-slate-300">Second Approver: {approval.second_approver_id || 'Pending'}</div>
                <div className="text-slate-400 font-mono">Status: {approval.status}</div>
              </div>
            )}

            {/* Append-Only Timeline */}
            <div>
              <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Audit Trail ({timeline?.length || 0} events)
              </h3>
              {(!timeline || timeline.length === 0) ? (
                <div className="text-slate-500 text-center py-3 bg-slate-950 rounded border border-slate-800 text-[11px]">
                  No historical actions logged.
                </div>
              ) : (
                <div className="space-y-1.5 text-[11px] font-mono">
                  {timeline.map((t: any) => (
                    <div key={t.event_id} className="p-2 rounded bg-slate-950 border border-slate-800/60">
                      <div className="flex justify-between text-slate-300">
                        <span className="font-bold text-indigo-400">{t.action}</span>
                        <span className="text-slate-500">{t.timestamp.substring(11, 19)}</span>
                      </div>
                      <div className="text-slate-400 text-[10px] mt-0.5">By: {t.actor_id} ({t.actor_role})</div>
                      {t.reason && <div className="text-slate-300 font-sans mt-1 text-[11px]">{t.reason}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Action Form */}
            <div className="bg-slate-950 p-3 rounded border border-slate-800 space-y-2 mt-auto">
              <label className="block text-[11px] font-semibold text-slate-300">
                Action Operational Justification (Mandatory):
              </label>
              <textarea
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder="State operational reason for decision..."
                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                rows={2}
              />
              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  onClick={() => handleAction('APPROVE_AP_REVIEW')}
                  disabled={actionLoading}
                  className="px-2.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
                >
                  Approve Review
                </button>
                <button
                  onClick={() => handleAction('HOLD_PENDING_EVIDENCE')}
                  disabled={actionLoading}
                  className="px-2.5 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium"
                >
                  Hold for Evidence
                </button>
                <button
                  onClick={() => handleAction('REQUEST_SUPPLIER_CORRECTION')}
                  disabled={actionLoading}
                  className="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs"
                >
                  Request Correction
                </button>
                <button
                  onClick={() => handleAction('QUARANTINE')}
                  disabled={actionLoading}
                  className="px-2.5 py-1.5 rounded bg-purple-800 hover:bg-purple-700 text-white text-xs"
                >
                  Quarantine File
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
