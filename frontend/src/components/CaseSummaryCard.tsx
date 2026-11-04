import React, { useState } from 'react';
import { 
  CheckCircle2, AlertTriangle, ShieldAlert, ChevronDown, ChevronUp
} from 'lucide-react';
import { Badge } from './ui';

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
      maximumFractionDigits: 0,
    }).format(val);
  };

  const totalGates = matchGates.length;
  const failedGates = matchGates.filter((g) => g.status === 'FAIL');
  const passedGates = matchGates.filter((g) => g.status === 'PASS');
  const hasFailedGates = failedGates.length > 0;

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
    explanation = 'Internal AP review complete. Ready for payment batching.';
  } else if (isUnreadable) {
    tone = 'error';
    title = 'Document Unreadable — OCR Failed';
    explanation = 'The uploaded scan could not be read cleanly. Downstream 3-way matching was halted to prevent false flags.';
  } else if (hasFailedGates) {
    tone = 'error';
    title = `${failedGates.length} Verification Discrepanc${failedGates.length > 1 ? 'ies' : 'y'} Identified`;
    explanation = failedGates.map((g) => g.gate_name || g.name).join(', ');
  } else if (isPendingSecondApproval) {
    tone = 'warning';
    title = 'Awaiting Secondary Controller Sign-Off';
    explanation = `Total amount (${formatINR(totalAmount)}) exceeds the ₹5,00,000 threshold. Primary review completed.`;
  } else {
    tone = 'success';
    title = requiresDualApproval 
      ? '3-Way Match Verified (Requires Dual-Approval)' 
      : '3-Way Match Verified — Ready for Approval';
    explanation = `All ${totalGates} policy checks passed. PO rates and physical quantities match.`;
  }

  const toneBg = {
    success: 'bg-emerald-50/80 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/60 text-emerald-950 dark:text-emerald-200',
    warning: 'bg-amber-50/80 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/60 text-amber-950 dark:text-amber-200',
    error: 'bg-rose-50/80 dark:bg-rose-950/30 border-rose-200 dark:border-rose-800/60 text-rose-950 dark:text-rose-200',
    info: 'bg-sky-50/80 dark:bg-sky-950/30 border-sky-200 dark:border-sky-800/60 text-sky-950 dark:text-sky-200',
    purple: 'bg-purple-50/80 dark:bg-purple-950/30 border-purple-200 dark:border-purple-800/60 text-purple-950 dark:text-purple-200',
  }[tone];

  return (
    <div className={`rounded-xl border p-3.5 transition-all ${toneBg}`}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {tone === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          ) : tone === 'error' ? (
            <AlertTriangle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
          ) : (
            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
          )}

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-xs sm:text-sm tracking-tight text-slate-900 dark:text-white">
                {title}
              </span>
              {requiresDualApproval && (
                <Badge tone="purple" size="sm">
                  Dual-Approval ≥ ₹5L
                </Badge>
              )}
            </div>
            <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-0.5 truncate">
              {explanation}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onOpenPolicyDrawer ? onOpenPolicyDrawer : () => setIsExpanded(!isExpanded)}
            className="cursor-pointer"
          >
            <Badge tone={tone} size="sm">
              {passedGates.length} / {totalGates} Checks Passed
            </Badge>
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-slate-500 cursor-pointer"
            aria-label={isExpanded ? 'Collapse policy summary' : 'Expand policy summary'}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Collapsible Policy Breakdown (Progressive Disclosure) */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-black/10 dark:border-white/10 text-xs space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {matchGates.map((gate, i) => (
              <div
                key={i}
                className="p-2 rounded bg-white/70 dark:bg-slate-900/70 border border-slate-200/60 dark:border-slate-800 flex items-center justify-between"
              >
                <div className="flex items-center gap-1.5 truncate">
                  <span className={`w-1.5 h-1.5 rounded-full ${gate.status === 'PASS' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  <span className="truncate text-[11px] font-medium text-slate-800 dark:text-slate-200">
                    {gate.gate_name || gate.name}
                  </span>
                </div>
                <Badge tone={gate.status === 'PASS' ? 'success' : 'error'} size="sm">
                  {gate.status === 'PASS' ? 'Passed' : 'Failed'}
                </Badge>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
            <span>Price Tolerance: &le; {policy.rate_tolerance_percent}% • Qty Tolerance: 0.00% (Strict)</span>
            {onOpenGlossary && (
              <button
                type="button"
                onClick={() => onOpenGlossary()}
                className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
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
