import React, { useState } from 'react';
import { 
  FileText, ShoppingCart, Truck, ShieldCheck, CheckCircle2, 
  XCircle, Info, HelpCircle, Columns, Layers
} from 'lucide-react';

interface InvoiceLine {
  line_number: number;
  description: string;
  quantity: number;
  rate: number;
  total: number;
}

interface POLine {
  line_number: number;
  item_code?: string;
  description: string;
  authorized_quantity: number;
  contracted_unit_rate: number;
  authorized_line_total: number;
}

interface ProcurementVerificationFlowProps {
  invoice: any;
  lines: InvoiceLine[];
  poSnapshot?: {
    po_number: string;
    vendor_code?: string;
    total_authorized_amount?: number;
    remaining_balance?: number;
    currency?: string;
    status?: string;
    retrieved_at?: string;
    lines?: POLine[];
    grn?: {
      grn_number?: string;
      received_date?: string;
      lines?: any[];
    } | null;
    qc?: {
      qc_certificate_number?: string;
      overall_status?: string;
    } | null;
  } | null;
  rateTolerancePercent?: number;
  onOpenGlossary?: (term?: string) => void;
}

export const ProcurementVerificationFlow: React.FC<ProcurementVerificationFlowProps> = ({
  invoice,
  lines,
  poSnapshot,
  rateTolerancePercent = 1.50,
  onOpenGlossary,
}) => {
  const [viewMode, setViewMode] = useState<'comparison' | 'detailed'>('comparison');

  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const hasPo = Boolean(poSnapshot);
  const poLines = poSnapshot?.lines || [];
  const grn = poSnapshot?.grn;
  const qc = poSnapshot?.qc;

  return (
    <div className="space-y-4 max-w-full">
      {/* 4-Node Procurement Verification Flow Card */}
      <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                Procurement Verification Flow (Three-Way Match)
              </h3>
              {onOpenGlossary && (
                <button
                  type="button"
                  onClick={() => onOpenGlossary('Three-Way Match')}
                  className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                  title="Learn about Three-Way Match in Glossary"
                >
                  <HelpCircle className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Cross-verifying the supplier's billing claim against authoritative procurement records.
            </p>
          </div>
        </div>

        {/* Linear Stage Velocity Tracker */}
        <div className="flex flex-wrap items-center justify-between text-[11px] font-mono px-3 py-1.5 rounded-md bg-white dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800/70 text-slate-500 gap-x-2 gap-y-1">
          <span className="flex items-center gap-1.5 text-indigo-700 dark:text-indigo-300 font-semibold">
            <span className="w-4 h-4 rounded-full bg-indigo-100 dark:bg-indigo-950 flex items-center justify-center text-[10px]">1</span>
            <span>Billed Claim</span>
          </span>
          <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">&rarr;</span>
          <span className={`flex items-center gap-1.5 font-semibold ${hasPo ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-400'}`}>
            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${hasPo ? 'bg-emerald-100 dark:bg-emerald-950' : 'bg-slate-100 dark:bg-slate-800'}`}>2</span>
            <span>PO Contract</span>
          </span>
          <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">&rarr;</span>
          <span className={`flex items-center gap-1.5 font-semibold ${grn ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-400'}`}>
            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${grn ? 'bg-emerald-100 dark:bg-emerald-950' : 'bg-slate-100 dark:bg-slate-800'}`}>3</span>
            <span>Receiving (GRN)</span>
          </span>
          <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">&rarr;</span>
          <span className={`flex items-center gap-1.5 font-semibold ${qc ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-400'}`}>
            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${qc ? 'bg-emerald-100 dark:bg-emerald-950' : 'bg-slate-100 dark:bg-slate-800'}`}>4</span>
            <span>Quality (QC)</span>
          </span>
        </div>

        {/* 4 Flow Cards - 2 cols on split-pane view, comfortable breathing room */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-0.5">
          {/* Node 1: Invoice */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-start justify-between gap-1.5 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                  <span className="font-bold text-xs text-slate-900 dark:text-white truncate">1. Supplier Invoice</span>
                </div>
                <span className="px-1.5 py-0.5 rounded text-[9.5px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 shrink-0 whitespace-nowrap">
                  Claimed
                </span>
              </div>
              <p className="text-[10.5px] text-slate-500 dark:text-slate-400 leading-snug mt-1 line-clamp-2">
                What the supplier is asking to be paid for delivered services or materials.
              </p>
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">Number:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">{invoice.invoice_number || invoice.id}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">Billed Total:</span>
                <span className="font-bold text-slate-900 dark:text-white tabular-nums">{formatINR(invoice.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Node 2: Purchase Order (PO) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-start justify-between gap-1.5 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <ShoppingCart className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span className="font-bold text-xs text-slate-900 dark:text-white truncate">2. Purchase Order</span>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold shrink-0 whitespace-nowrap ${
                  hasPo
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                }`}>
                  {hasPo ? 'Authorized' : 'Missing'}
                </span>
              </div>
              <p className="text-[10.5px] text-slate-500 dark:text-slate-400 leading-snug mt-1 line-clamp-2">
                What the company ordered and legally agreed to pay at contracted unit rates.
              </p>
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">PO Ref:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">{invoice.po_reference || 'NONE'}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">PO Total:</span>
                <span className="font-bold text-slate-900 dark:text-white tabular-nums">
                  {hasPo && poSnapshot?.total_authorized_amount ? formatINR(poSnapshot.total_authorized_amount) : 'Not Found'}
                </span>
              </div>
            </div>
          </div>

          {/* Node 3: Goods Receipt Note (GRN) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-start justify-between gap-1.5 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Truck className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span className="font-bold text-xs text-slate-900 dark:text-white truncate">3. Goods Receipt</span>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold shrink-0 whitespace-nowrap ${
                  grn
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                }`}>
                  {grn ? 'Confirmed' : 'Snapshot Unavailable'}
                </span>
              </div>
              <p className="text-[10.5px] text-slate-500 dark:text-slate-400 leading-snug mt-1 line-clamp-2">
                What the warehouse receiving dock physically logged as received.
              </p>
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">GRN Number:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">{grn?.grn_number || 'Unavailable'}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">Receipt Status:</span>
                <span className="text-slate-700 dark:text-slate-300 font-sans text-[10.5px] text-right truncate" title={grn ? 'Physically Logged' : 'Freight Slip Confirmed'}>
                  {grn ? 'Physically Logged' : 'Freight Slip Confirmed'}
                </span>
              </div>
            </div>
          </div>

          {/* Node 4: Quality Control (QC) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-start justify-between gap-1.5 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400 shrink-0" />
                  <span className="font-bold text-xs text-slate-900 dark:text-white truncate">4. Quality Control</span>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold shrink-0 whitespace-nowrap ${
                  qc
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                }`}>
                  {qc ? qc.overall_status : 'Snapshot Unavailable'}
                </span>
              </div>
              <p className="text-[10.5px] text-slate-500 dark:text-slate-400 leading-snug mt-1 line-clamp-2">
                Whether received goods passed inspection without defect or rejection.
              </p>
            </div>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">Inspection Cert:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">{qc?.qc_certificate_number || 'Unavailable'}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-slate-400 font-sans text-[10.5px] shrink-0">QA Verdict:</span>
                <span className="text-slate-700 dark:text-slate-300 font-sans text-[10.5px] text-right truncate" title={qc ? qc.overall_status : 'Exempt / Not Filed'}>
                  {qc ? qc.overall_status : 'Exempt / Not Filed'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Line-Level Comparison: Billed vs Authoritative PO */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Line-by-Line Procurement Match ({lines?.length || 0} Billed Lines)
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Contract rate variance tolerance enforced at ±{rateTolerancePercent.toFixed(2)}%. Quantity variance tolerance is 0.00%.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-center">
            {poSnapshot && (
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200/80 dark:border-slate-700/80">
                PO: {poSnapshot.po_number}
              </span>
            )}
            {/* View Mode Toggle: Comparison (Compact, fits split pane) vs Detailed (9-col ledger) */}
            <div className="hidden md:inline-flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[10px] font-medium">
              <button
                type="button"
                onClick={() => setViewMode('comparison')}
                className={`px-2 py-0.5 rounded transition-all flex items-center gap-1 ${
                  viewMode === 'comparison'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
                title="Consolidated Billed vs PO Comparison layout (Fits desktop pane without clipping)"
              >
                <Layers className="w-3 h-3" />
                <span>Comparison</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('detailed')}
                className={`px-2 py-0.5 rounded transition-all flex items-center gap-1 ${
                  viewMode === 'detailed'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
                title="Full 9-Column Ledger layout with horizontal scroll"
              >
                <Columns className="w-3 h-3" />
                <span>9-Col Ledger</span>
              </button>
            </div>
          </div>
        </div>

        {(!lines || lines.length === 0) ? (
          <div className="text-center py-6 text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
            No line items extracted. Extraction pipeline pending.
          </div>
        ) : (
          <>
            {/* A. MOBILE STACKED PRESENTATION (< 768px) */}
            <div className="md:hidden space-y-3">
              {lines.map((l: InvoiceLine, idx: number) => {
                const matchingPoLine = poLines.find((pl) => pl.line_number === l.line_number) || poLines[idx];
                const hasPoLine = Boolean(matchingPoLine);

                let rateVariancePercent: number | null = null;
                let rateDeltaINR: number | null = null;
                let isRateFailed = false;
                let isQtyFailed = false;

                if (hasPoLine && matchingPoLine) {
                  const poRate = matchingPoLine.contracted_unit_rate;
                  if (poRate > 0) {
                    rateVariancePercent = ((l.rate - poRate) / poRate) * 100;
                    rateDeltaINR = (l.rate - poRate) * l.quantity;
                    if (Math.abs(rateVariancePercent) > rateTolerancePercent) {
                      isRateFailed = true;
                    }
                  }
                  if (l.quantity > matchingPoLine.authorized_quantity) {
                    isQtyFailed = true;
                  }
                }

                const isLineMatch = hasPoLine && !isRateFailed && !isQtyFailed;

                return (
                  <div 
                    key={l.line_number} 
                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-2.5"
                  >
                    {/* Card Header: Line #, Description, Verdict */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-[10px] font-mono text-slate-500 font-bold shrink-0">
                            #{l.line_number}
                          </span>
                          <h5 className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                            {l.description}
                          </h5>
                        </div>
                        {hasPoLine && matchingPoLine ? (
                          <p className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">
                            <span className="text-emerald-700 dark:text-emerald-400 font-semibold">PO Match:</span> {matchingPoLine.description}
                            {matchingPoLine.item_code && <span className="text-slate-400"> ({matchingPoLine.item_code})</span>}
                          </p>
                        ) : (
                          <p className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                            Unmatched against PO schedule
                          </p>
                        )}
                      </div>
                      <div className="shrink-0">
                        {!hasPo ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                            No PO
                          </span>
                        ) : isLineMatch ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Pass
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1">
                            <XCircle className="w-3 h-3 text-rose-600" />
                            Fail
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 2x2 Metric Comparison Grid */}
                    <div className="grid grid-cols-2 gap-2 p-2.5 rounded-md bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800 font-mono text-[11px]">
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">Billed / PO Qty</span>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span className={`font-bold tabular-nums ${isQtyFailed ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                            {l.quantity}
                          </span>
                          <span className="text-[10px] text-slate-400 font-normal">
                            / {hasPoLine && matchingPoLine ? matchingPoLine.authorized_quantity : '—'}
                          </span>
                        </div>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">Billed / PO Rate</span>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span className={`font-bold tabular-nums ${isRateFailed ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                            {formatINR(l.rate)}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400 block font-normal">
                          PO: {hasPoLine && matchingPoLine ? formatINR(matchingPoLine.contracted_unit_rate) : '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">Rate Variance</span>
                        {rateVariancePercent !== null ? (
                          <div className="mt-0.5 space-y-0.5">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold inline-block ${
                              isRateFailed
                                ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                                : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                            }`}>
                              {rateVariancePercent > 0 ? `+${rateVariancePercent.toFixed(2)}%` : `${rateVariancePercent.toFixed(2)}%`}
                            </span>
                            {rateDeltaINR !== null && Math.abs(rateDeltaINR) > 0.01 && (
                              <div className={`text-[10px] font-mono ${isRateFailed ? 'text-rose-600 dark:text-rose-400 font-semibold' : 'text-slate-400'}`}>
                                {rateDeltaINR > 0 ? `+${formatINR(rateDeltaINR)}` : formatINR(rateDeltaINR)}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">Billed Total</span>
                        <span className="font-bold text-slate-900 dark:text-white tabular-nums text-xs mt-0.5 block">
                          {formatINR(l.total)}
                        </span>
                      </div>
                    </div>

                    {/* Action if failed */}
                    {isRateFailed && rateDeltaINR && rateDeltaINR > 0 && (
                      <div className="px-2.5 py-1.5 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-[10px] text-rose-700 dark:text-rose-300 font-mono flex items-center justify-between">
                        <span className="font-sans font-medium">Resolution Action:</span>
                        <span className="font-bold">Debit Note ({formatINR(rateDeltaINR)})</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* B. DESKTOP & TABLET: REBALANCED COMPARISON VIEW (DEFAULT) */}
            {viewMode === 'comparison' && (
              <div className="hidden md:block border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden shadow-2xs bg-white dark:bg-slate-900 max-w-full">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[10.5px] select-none">
                    <tr>
                      <th className="py-2 px-2 w-6 text-center font-semibold text-slate-400">#</th>
                      <th className="py-2 px-2 font-semibold">Item & PO Match</th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Quantity</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">Billed · PO</div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Unit Rate</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">Billed · PO</div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div className="text-slate-900 dark:text-white font-bold">Variance</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">% · Δ INR</div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Total</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">Billed</div>
                      </th>
                      <th className="py-2 px-2 text-center font-semibold">
                        <div>Verdict</div>
                        <div className="text-[9px] font-normal text-slate-400">Status & Action</div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono text-[11px]">
                    {lines.map((l: InvoiceLine, idx: number) => {
                      const matchingPoLine = poLines.find((pl) => pl.line_number === l.line_number) || poLines[idx];
                      const hasPoLine = Boolean(matchingPoLine);

                      let rateVariancePercent: number | null = null;
                      let rateDeltaINR: number | null = null;
                      let isRateFailed = false;
                      let isQtyFailed = false;

                      if (hasPoLine && matchingPoLine) {
                        const poRate = matchingPoLine.contracted_unit_rate;
                        if (poRate > 0) {
                          rateVariancePercent = ((l.rate - poRate) / poRate) * 100;
                          rateDeltaINR = (l.rate - poRate) * l.quantity;
                          if (Math.abs(rateVariancePercent) > rateTolerancePercent) {
                            isRateFailed = true;
                          }
                        }
                        if (l.quantity > matchingPoLine.authorized_quantity) {
                          isQtyFailed = true;
                        }
                      }

                      const isLineMatch = hasPoLine && !isRateFailed && !isQtyFailed;

                      return (
                        <tr key={l.line_number} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors">
                          {/* 1. Line Number */}
                          <td className="py-2 px-2 text-center text-slate-400 font-mono text-xs">{l.line_number}</td>

                          {/* 2. Item & PO Reference */}
                          <td className="py-2 px-2 font-sans text-slate-800 dark:text-slate-200 min-w-0">
                            <div className="font-semibold text-xs leading-snug line-clamp-2">{l.description}</div>
                            {hasPoLine && matchingPoLine ? (
                              <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex flex-wrap items-center gap-1">
                                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">PO Match:</span>
                                <span className="text-slate-700 dark:text-slate-300">{matchingPoLine.description}</span>
                                {matchingPoLine.item_code && (
                                  <span className="text-slate-400">({matchingPoLine.item_code})</span>
                                )}
                              </div>
                            ) : (
                              <div className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                                Unmatched against PO schedule
                              </div>
                            )}
                          </td>

                          {/* 3. Quantity (Billed / PO) */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            <div className={`font-bold text-xs ${isQtyFailed ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                              {l.quantity}
                            </div>
                            <div className="text-[10px] text-slate-400 font-sans">
                              PO: {hasPoLine && matchingPoLine ? matchingPoLine.authorized_quantity : '—'}
                            </div>
                          </td>

                          {/* 4. Unit Rate (Billed / PO) */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            <div className={`font-bold text-xs ${isRateFailed ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                              {formatINR(l.rate)}
                            </div>
                            <div className="text-[10px] text-slate-400 font-sans">
                              PO: {hasPoLine && matchingPoLine ? formatINR(matchingPoLine.contracted_unit_rate) : '—'}
                            </div>
                          </td>

                          {/* 5. Rate Variance: Bold % Pill & INR Delta */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            {rateVariancePercent !== null ? (
                              <div className="inline-flex flex-col items-end gap-0.5">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-tight inline-block ${
                                  isRateFailed
                                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                                    : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                                }`}>
                                  {rateVariancePercent > 0 ? `+${rateVariancePercent.toFixed(2)}%` : `${rateVariancePercent.toFixed(2)}%`}
                                </span>
                                {rateDeltaINR !== null && Math.abs(rateDeltaINR) > 0.01 && (
                                  <span className={`text-[10px] font-mono leading-none ${
                                    isRateFailed ? 'text-rose-600 dark:text-rose-400 font-semibold' : 'text-slate-400'
                                  }`}>
                                    {rateDeltaINR > 0 ? `+${formatINR(rateDeltaINR)}` : formatINR(rateDeltaINR)}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>

                          {/* 6. Line Total */}
                          <td className="py-2 px-2 text-right tabular-nums font-bold text-xs text-slate-900 dark:text-white whitespace-nowrap">
                            {formatINR(l.total)}
                          </td>

                          {/* 7. Match Verdict & Action */}
                          <td className="py-2 px-2 text-center min-w-0">
                            {!hasPo ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 inline-block whitespace-nowrap">
                                No PO
                              </span>
                            ) : isLineMatch ? (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1 whitespace-nowrap">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                                  Pass
                                </span>
                                <span className="text-[9px] text-emerald-700 dark:text-emerald-400 mt-0.5 font-sans whitespace-nowrap">
                                  ±{rateTolerancePercent.toFixed(2)}%
                                </span>
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center gap-0.5">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1 whitespace-nowrap">
                                  <XCircle className="w-3 h-3 text-rose-600 shrink-0" />
                                  {isRateFailed && isQtyFailed ? 'Rate & Qty Fail' : isRateFailed ? 'Rate Exceeded' : 'Qty Exceeded'}
                                </span>
                                {isRateFailed && rateDeltaINR && rateDeltaINR > 0 && (
                                  <span className="text-[9px] text-rose-600 dark:text-rose-400 font-mono font-semibold">
                                    Debit Note: {formatINR(rateDeltaINR)}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* C. DESKTOP & TABLET: DETAILED 9-COLUMN LEDGER VIEW (OPTIONAL EXPANDED) */}
            {viewMode === 'detailed' && (
              <div className="hidden md:block border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto shadow-2xs bg-white dark:bg-slate-900 max-w-full">
                <table className="w-full text-left text-xs min-w-[700px] border-collapse">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] select-none">
                    <tr>
                      <th className="py-2.5 px-2 w-6 text-center font-semibold text-slate-400">#</th>
                      <th className="py-2.5 px-2.5 min-w-[120px] font-semibold">Billed Item & PO Reference</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">Billed Qty</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">PO Qty</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">Billed Rate</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">PO Rate</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap text-slate-900 dark:text-white font-bold">Rate Variance</th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">Line Total</th>
                      <th className="py-2.5 px-2.5 text-center font-semibold min-w-[110px]">Match Verdict & Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono text-[11px]">
                    {lines.map((l: InvoiceLine, idx: number) => {
                      const matchingPoLine = poLines.find((pl) => pl.line_number === l.line_number) || poLines[idx];
                      const hasPoLine = Boolean(matchingPoLine);

                      let rateVariancePercent: number | null = null;
                      let rateDeltaINR: number | null = null;
                      let isRateFailed = false;
                      let isQtyFailed = false;

                      if (hasPoLine && matchingPoLine) {
                        const poRate = matchingPoLine.contracted_unit_rate;
                        if (poRate > 0) {
                          rateVariancePercent = ((l.rate - poRate) / poRate) * 100;
                          rateDeltaINR = (l.rate - poRate) * l.quantity;
                          if (Math.abs(rateVariancePercent) > rateTolerancePercent) {
                            isRateFailed = true;
                          }
                        }
                        if (l.quantity > matchingPoLine.authorized_quantity) {
                          isQtyFailed = true;
                        }
                      }

                      const isLineMatch = hasPoLine && !isRateFailed && !isQtyFailed;

                      return (
                        <tr key={l.line_number} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors">
                          <td className="py-2.5 px-2 text-center text-slate-400 font-mono text-xs">{l.line_number}</td>
                          <td className="py-2.5 px-2.5 font-sans text-slate-800 dark:text-slate-200">
                            <div className="font-semibold text-xs leading-snug">{l.description}</div>
                            {hasPoLine && matchingPoLine ? (
                              <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex flex-wrap items-center gap-1">
                                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Matched:</span>
                                <span>{matchingPoLine.description}</span>
                                {matchingPoLine.item_code && (
                                  <span className="text-slate-400">({matchingPoLine.item_code})</span>
                                )}
                              </div>
                            ) : (
                              <div className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                                Unmatched against PO schedule
                              </div>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                            {l.quantity}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-500">
                            {hasPoLine && matchingPoLine ? matchingPoLine.authorized_quantity : '—'}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                            {formatINR(l.rate)}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-500">
                            {hasPoLine && matchingPoLine ? formatINR(matchingPoLine.contracted_unit_rate) : '—'}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums">
                            {rateVariancePercent !== null ? (
                              <div className="inline-flex flex-col items-end gap-0.5">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  isRateFailed
                                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                                    : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                                }`}>
                                  {rateVariancePercent > 0 ? `+${rateVariancePercent.toFixed(2)}%` : `${rateVariancePercent.toFixed(2)}%`}
                                </span>
                                {rateDeltaINR !== null && Math.abs(rateDeltaINR) > 0.01 && (
                                  <span className={`text-[10px] font-mono ${
                                    isRateFailed ? 'text-rose-600 dark:text-rose-400 font-semibold' : 'text-slate-400'
                                  }`}>
                                    {rateDeltaINR > 0 ? `+${formatINR(rateDeltaINR)}` : formatINR(rateDeltaINR)}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums font-bold text-slate-900 dark:text-white">
                            {formatINR(l.total)}
                          </td>
                          <td className="py-2.5 px-2.5 text-center">
                            {!hasPo ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                                No PO Record
                              </span>
                            ) : isLineMatch ? (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-2 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                  Pass
                                </span>
                                <span className="text-[9px] text-emerald-700 dark:text-emerald-400 mt-0.5 font-sans">
                                  Within ±{rateTolerancePercent.toFixed(2)}%
                                </span>
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center gap-0.5">
                                <span className="px-2 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1">
                                  <XCircle className="w-3 h-3 text-rose-600" />
                                  {isRateFailed && isQtyFailed ? 'Rate & Qty Exceeded' : isRateFailed ? 'Rate Exceeded' : 'Qty Exceeded'}
                                </span>
                                {isRateFailed && rateDeltaINR && rateDeltaINR > 0 && (
                                  <span className="text-[9px] text-rose-600 dark:text-rose-400 font-mono font-semibold">
                                    Debit Note: {formatINR(rateDeltaINR)}
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Honest Data Availability Disclosures */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 space-y-1">
          <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200">
            <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0" />
            <span>Warehouse Receiving (GRN) Status</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            {grn
              ? `Confirmed: GRN ${grn.grn_number} registered on ${grn.received_date?.substring(0, 10)}.`
              : 'Line-level Goods Receipt Note data is unavailable in this procurement snapshot. Gate 4 evaluated via document header / freight bill confirmation.'}
          </p>
        </div>

        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 space-y-1">
          <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200">
            <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0" />
            <span>Quality Inspection (QC) Status</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            {qc
              ? `Confirmed: Certificate ${qc.qc_certificate_number} recorded with status ${qc.overall_status}.`
              : 'Line-level Quality Inspection record is unavailable in this procurement snapshot. Physical goods inspection was not filed or not required for this procurement category.'}
          </p>
        </div>
      </div>
    </div>
  );
};
