import React, { useEffect, useState } from 'react';
import { 
  AlertTriangle, 
  Clock, 
  ArrowUpRight, 
  RefreshCw, 
  Info
} from 'lucide-react';
import { api } from '../api/client';
import type { ExceptionItem } from '../types';

interface ExceptionsPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

export const ExceptionsPage: React.FC<ExceptionsPageProps> = ({ onSelectInvoice }) => {
  const [items, setItems] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadExceptions = async () => {
    setLoading(true);
    try {
      const res = await api.getExceptions();
      setItems(res.items || []);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExceptions();
  }, []);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Exceptions Priority Queue
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Ranked primarily by legally verified MSME statutory deadline, then exposure amount.
          </p>
        </div>
        <button
          onClick={loadExceptions}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Queue
        </button>
      </div>

      {/* Statutory Sorting Rule Callout */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs flex items-start gap-2.5">
        <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-slate-300 space-y-0.5">
          <span className="font-semibold text-slate-200">Statutory Urgency Invariant:</span> Snoozing or holding an exception never suppresses or shifts the statutory MSMED Act 45-day deadline. Penal interest compounds monthly at 3× RBI bank rate if settlement is delayed.
        </div>
      </div>

      {/* Exceptions Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden">
        {items.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-xs space-y-2">
            <Clock className="w-8 h-8 text-slate-600 mx-auto" />
            <div className="font-semibold text-slate-300">No unresolved exceptions in queue</div>
            <p className="text-slate-500 max-w-md mx-auto">
              All ingested supplier invoices have passed deterministic policy gates or no unaddressed discrepancies remain.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">MSME Statutory Due</th>
                  <th className="py-2.5 px-3">Exposure Held</th>
                  <th className="py-2.5 px-3">Supplier</th>
                  <th className="py-2.5 px-3">Blocking Gate</th>
                  <th className="py-2.5 px-3">Assigned Owner</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {items.map((e) => (
                  <tr key={e.exception_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-3 font-mono text-[11px]">
                      {e.msme_statutory_deadline ? (
                        <span className="flex items-center gap-1.5 text-rose-400 font-semibold">
                          <Clock className="w-3.5 h-3.5" />
                          {e.msme_statutory_deadline.substring(0, 10)}
                        </span>
                      ) : (
                        <span className="text-slate-500">Unestablished</span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-100 font-bold tabular-nums">
                      {formatINR(e.exposure_amount_inr)}
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-medium text-slate-200">{e.vendor_name || 'Unidentified'}</div>
                      <div className="text-[10px] text-slate-500 font-mono">Inv: {e.invoice_number || e.invoice_id}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        Gate #{e.blocking_gate_number}: {e.blocking_gate_name}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400 text-[11px]">
                      {e.assigned_user_id || 'Unassigned'}
                    </td>
                    <td className="py-3 px-3">
                      <button
                        onClick={() => onSelectInvoice(e.invoice_id)}
                        className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium text-xs"
                      >
                        Resolve <ArrowUpRight className="w-3 h-3" />
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
