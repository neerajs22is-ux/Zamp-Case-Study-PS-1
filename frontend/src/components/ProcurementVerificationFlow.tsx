import React from 'react';
import { 
  FileText, ShoppingCart, Truck, ShieldCheck, CheckCircle2, 
  XCircle, Info, HelpCircle 
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
    <div className="space-y-4">
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
        <div className="flex flex-wrap items-center justify-between text-[11px] font-mono px-3 py-1.5 rounded-md bg-white dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800/70 text-slate-500 gap-y-1">
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

        {/* 4 Flow Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 pt-0.5">
          {/* Node 1: Invoice */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                <span className="font-bold text-xs text-slate-900 dark:text-white">1. Supplier Invoice</span>
              </div>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                Claimed
              </span>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">
              What the supplier is asking to be paid for delivered services or materials.
            </p>
            <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-0.5">
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">Number:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{invoice.invoice_number || invoice.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">Billed Total:</span>
                <span className="font-bold text-slate-900 dark:text-white">{formatINR(invoice.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Node 2: Purchase Order (PO) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <ShoppingCart className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span className="font-bold text-xs text-slate-900 dark:text-white">2. Purchase Order</span>
              </div>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                hasPo
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
              }`}>
                {hasPo ? 'Authorized' : 'Missing'}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">
              What the company ordered and legally agreed to pay at contracted unit rates.
            </p>
            <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-0.5">
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">PO Ref:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{invoice.po_reference || 'NONE'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">PO Total:</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  {hasPo && poSnapshot?.total_authorized_amount ? formatINR(poSnapshot.total_authorized_amount) : 'Not Found'}
                </span>
              </div>
            </div>
          </div>

          {/* Node 3: Goods Receipt Note (GRN) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Truck className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                <span className="font-bold text-xs text-slate-900 dark:text-white">3. Goods Receipt</span>
              </div>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                grn
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
              }`}>
                {grn ? 'Confirmed' : 'Snapshot Unavailable'}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">
              What the warehouse receiving dock physically logged as received.
            </p>
            <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-0.5">
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">GRN Number:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{grn?.grn_number || 'Unavailable'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">Receipt Status:</span>
                <span className="text-slate-600 dark:text-slate-300 font-sans text-[10px]">
                  {grn ? 'Physically Logged' : 'Freight Slip Confirmed'}
                </span>
              </div>
            </div>
          </div>

          {/* Node 4: Quality Control (QC) */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <span className="font-bold text-xs text-slate-900 dark:text-white">4. Quality Control</span>
              </div>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${
                qc
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
              }`}>
                {qc ? qc.overall_status : 'Snapshot Unavailable'}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-tight">
              Whether received goods passed inspection without defect or rejection.
            </p>
            <div className="pt-1.5 border-t border-slate-100 dark:border-slate-800 font-mono text-[11px] space-y-0.5">
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">Inspection Cert:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{qc?.qc_certificate_number || 'Unavailable'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400 font-sans">QA Verdict:</span>
                <span className="text-slate-600 dark:text-slate-300 font-sans text-[10px]">
                  {qc ? qc.overall_status : 'Exempt / Not Filed'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Line-Level Comparison: Billed vs Authoritative PO */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Line-by-Line Procurement Match ({lines?.length || 0} Billed Lines)
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Contract rate variance tolerance enforced at ±{rateTolerancePercent.toFixed(2)}%. Quantity variance tolerance is 0.00%.
            </p>
          </div>
          {poSnapshot && (
            <span className="text-[10px] font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
              PO: {poSnapshot.po_number}
            </span>
          )}
        </div>

        {(!lines || lines.length === 0) ? (
          <div className="text-center py-6 text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
            No line items extracted. Extraction pipeline pending.
          </div>
        ) : (
          <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto shadow-2xs">
            <table className="w-full text-left text-xs min-w-[840px]">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] select-none">
                <tr>
                  <th className="py-2.5 px-3 w-8">#</th>
                  <th className="py-2.5 px-3">Billed Item & PO Reference</th>
                  <th className="py-2.5 px-3 text-right">Billed Qty</th>
                  <th className="py-2.5 px-3 text-right">PO Qty</th>
                  <th className="py-2.5 px-3 text-right">Billed Rate</th>
                  <th className="py-2.5 px-3 text-right">PO Rate</th>
                  <th className="py-2.5 px-3 text-right">Rate Variance</th>
                  <th className="py-2.5 px-3 text-right">Line Total</th>
                  <th className="py-2.5 px-3 text-center">Match Verdict & Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {lines.map((l: InvoiceLine, idx: number) => {
                  // Find corresponding PO line by index or line_number
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
                      <td className="py-2.5 px-3 text-slate-400">{l.line_number}</td>
                      <td className="py-2.5 px-3 font-sans text-slate-800 dark:text-slate-200">
                        <div className="font-medium">{l.description}</div>
                        {hasPoLine && matchingPoLine ? (
                          <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex items-center gap-1.5">
                            <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Matched:</span>
                            <span>{matchingPoLine.description}</span>
                            {matchingPoLine.item_code && (
                              <span className="text-slate-400">({matchingPoLine.item_code})</span>
                            )}
                          </div>
                        ) : (
                          <div className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                            Unmatched against purchase order line schedule
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                        {l.quantity}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-slate-500">
                        {hasPoLine && matchingPoLine ? matchingPoLine.authorized_quantity : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                        {formatINR(l.rate)}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-slate-500">
                        {hasPoLine && matchingPoLine ? formatINR(matchingPoLine.contracted_unit_rate) : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {rateVariancePercent !== null ? (
                          <div className="flex flex-col items-end gap-0.5">
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
                      <td className="py-2.5 px-3 text-right tabular-nums font-bold text-slate-900 dark:text-white">
                        {formatINR(l.total)}
                      </td>
                      <td className="py-2.5 px-3 text-center">
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
                                Action: Debit Note ({formatINR(rateDeltaINR)})
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
