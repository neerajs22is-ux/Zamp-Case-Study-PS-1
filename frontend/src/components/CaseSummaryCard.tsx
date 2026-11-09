import React, { useState } from 'react';
import { 
  CheckCircle2, AlertTriangle, ShieldAlert, ChevronDown, ChevronUp, ShieldCheck, XCircle
} from 'lucide-react';
import { Badge } from './ui';
import { checkResultKind, summarizeCheckResults } from '../utils/checkResults';

interface CaseSummaryCardProps {
  invoice: any;
  matchGates: any[];
  userRole?: string | null;
  policy: {
    dual_approval_threshold_inr: number;
    rate_tolerance_percent: number;
    rounding_tolerance_inr: number;
  };
  onOpenGlossary?: (term?: string) => void;
  onOpenPolicyDrawer?: () => void;
}

const CANONICAL_GATE_DEFS = [
  { num: 1, label: 'Vendor Identity', short: 'Vendor ID', matchNames: ['vendor'] },
  { num: 2, label: 'PO Authorization', short: 'PO Auth', matchNames: ['po authorization', 'purchase order'] },
  { num: 3, label: 'Goods Receipt Note (GRN)', short: 'GRN Receipt', matchNames: ['goods receipt', 'grn'] },
  { num: 4, label: 'Quality Inspection (QC)', short: 'QC Passed', matchNames: ['quality', 'qc'] },
  { num: 5, label: 'GST & Arithmetic Validation', short: 'GST Math', matchNames: ['arithmetic', 'tax', 'gst'] },
  { num: 6, label: 'PO Price & Qty Tolerance', short: 'PO Tolerance', matchNames: ['tolerance', 'rate', 'price'] },
  { num: 7, label: 'Duplicate Check & Hash', short: 'Duplicate Check', matchNames: ['duplicate'] },
];

export const CaseSummaryCard: React.FC<CaseSummaryCardProps> = ({
  invoice,
  matchGates,
  userRole = 'AP_LEAD',
  policy,
  onOpenGlossary,
  onOpenPolicyDrawer,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);
  };

  const totalGates = matchGates.length;
  const failedGates = matchGates.filter((g) => g.status === 'FAIL');
  const hasFailedGates = failedGates.length > 0;
  const passedGates = matchGates.filter((g) => g.status === 'PASS');
  const incompleteGates = matchGates.filter((g) => g.status !== 'PASS' && g.status !== 'FAIL');

  const isUnreadable = Boolean(
    invoice.decision === 'FLAGGED_HITL_REVIEW' && (
      !invoice.invoice_number ||
      invoice.invoice_number === 'UNKNOWN' ||
      invoice.invoice_number?.startsWith('SCAN-') ||
      invoice.vendor_name === 'Unidentified Supplier' ||
      invoice.vendor_name === 'Unknown' ||
      (invoice.total_amount === 0 && !invoice.po_reference)
    )
  );

  const totalAmount = invoice.total_amount || 0;
  const requiresDualApproval = totalAmount >= policy.dual_approval_threshold_inr;
  const isApproved = invoice.stage === 'INTERNAL_APPROVAL_COMPLETE';
  const isPendingSecondApproval = invoice.workflow_substatus === 'PENDING_SECOND_APPROVAL';

  // Plain-English Decision Verdict
  let tone: 'success' | 'warning' | 'error' | 'info' | 'purple' = 'success';
  let title = '';
  let explanation = '';

  if (userRole === 'AUDITOR') {
    tone = 'info';
    title = 'Read-Only Audit Mode';
    explanation = 'Auditor oversight session active. All approval and edit controls are disabled.';
  } else if (isApproved) {
    tone = 'success';
    title = 'Approved & Signed Off';
    explanation = 'Internal AP review complete. This does not send a payment.';
  } else if (isUnreadable) {
    tone = 'error';
    title = 'Document needs review';
    explanation = 'Some invoice details are missing or unclear. Inspect the source document and available checks.';
  } else if (hasFailedGates) {
    tone = 'error';
    title = `${failedGates.length} Verification Discrepanc${failedGates.length > 1 ? 'ies' : 'y'} Identified`;
    explanation = failedGates.map((g) => g.gate_name || g.name).join(', ');
  } else if (isPendingSecondApproval) {
    tone = 'warning';
    title = 'Awaiting Secondary Controller Sign-Off';
    explanation = 'The first sign-off is recorded; an independent second sign-off is pending.';
  } else if (totalGates === 0 || incompleteGates.length > 0) {
    tone = 'warning';
    title = 'Verification incomplete';
    explanation = summarizeCheckResults(matchGates) + '.';
  } else {
    tone = 'success';
    title = 'All 7 Verification Checks Passed';
    explanation = summarizeCheckResults(matchGates) + '.';
  }

  const toneBg = {
    success: 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/50 text-emerald-950 dark:text-emerald-200',
    warning: 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/50 text-amber-950 dark:text-amber-200',
    error: 'bg-rose-50/70 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800/50 text-rose-950 dark:text-rose-200',
    info: 'bg-sky-50/70 dark:bg-sky-950/20 border-sky-200 dark:border-sky-800/50 text-sky-950 dark:text-sky-200',
    purple: 'bg-purple-50/70 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800/50 text-purple-950 dark:text-purple-200',
  }[tone];

  // Resolve canonical 7 gates list
  const gateItems = CANONICAL_GATE_DEFS.map((def) => {
    const found = matchGates.find((g) => {
      if (g.gate_number === def.num) return true;
      const gName = (g.gate_name || g.name || '').toLowerCase();
      return def.matchNames.some((m) => gName.includes(m));
    });
    return {
      num: def.num,
      name: def.label,
      short: def.short,
      status: found ? found.status : 'NOT_EVALUATED',
      notes: found?.notes || found?.evidence_notes || null,
      raw: found,
    };
  });

  return (
    <div className={`review-summary rounded-xl border p-4 space-y-3.5 transition-all ${toneBg} flex flex-col h-full`}>
      {/* 1. Header Bar: Verdict + Discrepancy count + Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-2 rounded-lg bg-white/80 dark:bg-slate-900/80 shadow-2xs shrink-0">
            {tone === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            ) : tone === 'error' ? (
              <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-sm sm:text-base tracking-tight text-slate-900 dark:text-white">
                {title}
              </span>
              {requiresDualApproval && (
                <Badge tone="purple" size="sm">
                  Dual approval ≥ {formatINR(policy.dual_approval_threshold_inr)}
                </Badge>
              )}
            </div>
            <p className="review-summary-explanation text-xs text-slate-600 dark:text-slate-300 mt-0.5 line-clamp-2" title={explanation}>
              {explanation}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
          <button
            type="button"
            onClick={onOpenPolicyDrawer ? onOpenPolicyDrawer : () => setIsExpanded(!isExpanded)}
            className="cursor-pointer"
          >
            <Badge tone={tone} size="md" className="font-semibold px-2.5 py-1">
              {failedGates.length > 0
                ? `${failedGates.length} failed · ${passedGates.length} passed`
                : 'All 7 checks passed'}
            </Badge>
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 text-slate-500 cursor-pointer"
            aria-label={isExpanded ? 'Collapse policy summary' : 'Expand policy summary'}
            title={isExpanded ? 'Collapse breakdown' : 'Expand detailed checks breakdown'}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* 2. Canonical Seven-Gate Status Overview Grid */}
      <div className="pt-2 border-t border-black/5 dark:border-white/5">
        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-2">
          <span className="uppercase tracking-wider">Seven-Gate Policy Validation Overview</span>
          <button
            type="button"
            onClick={onOpenPolicyDrawer ? onOpenPolicyDrawer : () => setIsExpanded(true)}
            className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer flex items-center gap-1 font-medium"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>View check evidence drawer</span>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 min-[1750px]:grid-cols-7 gap-1.5">
          {gateItems.map((gate) => {
            const isPass = gate.status === 'PASS';
            const isFail = gate.status === 'FAIL';

            return (
              <div
                key={gate.num}
                onClick={onOpenPolicyDrawer ? onOpenPolicyDrawer : undefined}
                className={`p-2 rounded-lg border text-left transition-all ${
                  onOpenPolicyDrawer ? 'cursor-pointer hover:shadow-2xs' : ''
                } ${
                  isFail
                    ? 'bg-rose-100/70 dark:bg-rose-950/40 border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-200'
                    : isPass
                    ? 'bg-white/80 dark:bg-slate-900/80 border-slate-200/80 dark:border-slate-800 text-slate-800 dark:text-slate-200'
                    : 'bg-slate-100/60 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800 text-slate-500'
                }`}
                title={`${gate.num}. ${gate.name}: ${checkResultKind(gate.status)}${gate.notes ? ` — ${gate.notes}` : ''}`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="font-mono text-[10px] font-bold opacity-60">
                    G{gate.num}
                  </span>
                  {isPass ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  ) : isFail ? (
                    <XCircle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600 shrink-0" />
                  )}
                </div>
                <div className="truncate text-[11px] font-semibold leading-tight">
                  {gate.short}
                </div>
                <div className="mt-1 flex items-center justify-between text-[9.5px]">
                  <span className={`font-mono font-medium ${
                    isFail ? 'text-rose-700 dark:text-rose-300 font-bold' : isPass ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-400'
                  }`}>
                    {isPass ? 'PASS' : isFail ? 'FAIL' : 'PENDING'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. High-Contrast Discrepancy Callout (when any gate fails) */}
      {hasFailedGates && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-bold text-rose-800 dark:text-rose-300">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Blocking Discrepancy Identified:</span>
          </div>
          <ul className="review-check-list my-1 text-xs space-y-1" aria-label="Checks requiring attention">
            {[...failedGates, ...incompleteGates].map((gate, index) => (
              <li key={gate.gate_number ?? index} className="text-rose-900 dark:text-rose-200">
                <strong>{gate.gate_name || gate.name || 'Check'}:</strong>{' '}
                <span className="font-semibold">{checkResultKind(gate.status)}</span>
                {gate.notes ? ` — ${gate.notes}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 4. Progressive Details & Policy Parameters */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-black/10 dark:border-white/10 text-xs space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {matchGates.map((gate, i) => (
              <div
                key={i}
                className="p-2.5 rounded-lg bg-white/70 dark:bg-slate-900/70 border border-slate-200/60 dark:border-slate-800 flex items-start justify-between gap-2"
              >
                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-center gap-1.5 truncate">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${gate.status === 'PASS' ? 'bg-emerald-500' : gate.status === 'FAIL' ? 'bg-rose-500' : 'bg-slate-400'}`} />
                    <span className="truncate text-xs font-semibold text-slate-800 dark:text-slate-200">
                      {gate.gate_name || gate.name}
                    </span>
                  </div>
                  {gate.notes && (
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 pl-3.5">
                      {gate.notes}
                    </p>
                  )}
                </div>
                <Badge tone={gate.status === 'PASS' ? 'success' : gate.status === 'FAIL' ? 'error' : 'neutral'} size="sm">
                  {checkResultKind(gate.status)}
                </Badge>
              </div>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] text-slate-500 pt-1 border-t border-black/5 dark:border-white/5">
            <span>
              Price Tolerance: &le; {policy.rate_tolerance_percent}% • Qty Tolerance: 0.00% (Strict) • Evaluated against authoritative procurement snapshots.
            </span>
            {onOpenGlossary && (
              <button
                type="button"
                onClick={() => onOpenGlossary()}
                className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer font-medium shrink-0"
              >
                View AP Glossary
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
