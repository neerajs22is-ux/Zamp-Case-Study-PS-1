import React, { useState } from 'react';
import { 
  CheckCircle2, HelpCircle, ChevronDown, ChevronUp, ShieldAlert, Sparkles
} from 'lucide-react';

interface CaseSummaryCardProps {
  invoice: any;
  matchGates: any[];
  userRole?: string;
  policy: {
    dual_approval_threshold_inr: number;
    rate_tolerance_percent: number;
    rounding_tolerance_inr: number;
  };
  onOpenGlossary?: (term?: string) => void;
}

export const CaseSummaryCard: React.FC<CaseSummaryCardProps> = ({
  invoice,
  matchGates,
  userRole = 'AP_LEAD',
  policy,
  onOpenGlossary,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
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
      invoice.invoice_number.startsWith('SCAN-') ||
      invoice.vendor_name === 'Unidentified Supplier' ||
      invoice.vendor_name === 'Unknown' ||
      (invoice.total_amount === 0 && !invoice.po_reference)
    )
  );

  const totalAmount = invoice.total_amount || 0;
  const requiresDualApproval = totalAmount >= policy.dual_approval_threshold_inr;
  const isApproved = invoice.stage === 'INTERNAL_APPROVAL_COMPLETE';
  const isPendingSecondApproval = invoice.workflow_substatus === 'PENDING_SECOND_APPROVAL';

  // Determine legally and operationally permissible decision for current user
  let decisionTitle = '';
  let decisionDescription = '';
  let decisionType: 'BLOCKED' | 'READY_FIRST' | 'READY_SECOND' | 'COMPLETED' | 'READ_ONLY' = 'READY_FIRST';

  if (userRole === 'AUDITOR') {
    decisionType = 'READ_ONLY';
    decisionTitle = 'Read-Only Oversight';
    decisionDescription = 'Auditor role has inspection permissions only. Approval and triage mutations are disabled.';
  } else if (isApproved) {
    decisionType = 'COMPLETED';
    decisionTitle = 'Review Complete (Signed Off)';
    decisionDescription = 'Internal AP review sign-off has been recorded. This invoice is cleared for external payment batching.';
  } else if (isUnreadable) {
    decisionType = 'BLOCKED';
    decisionTitle = 'Approval Blocked (Document Unreadable)';
    decisionDescription = 'This document could not be read automatically due to scan degradation. Downstream checks were not evaluated. Upload a clearer copy or input details manually.';
  } else if (hasFailedGates) {
    decisionType = 'BLOCKED';
    decisionTitle = `Approval Blocked (${failedGates.length} check${failedGates.length > 1 ? 's' : ''} failed)`;
    decisionDescription = `Internal sign-off is strictly blocked until policy discrepancies are triaged. Available triage actions: Hold for Evidence, Request Supplier Correction, Raise Debit Note, Escalate, or Reject.`;
  } else if (isPendingSecondApproval) {
    if (['CONTROLLER', 'SYSTEM_ADMIN'].includes(userRole)) {
      decisionType = 'READY_SECOND';
      decisionTitle = 'Ready for Secondary Sign-Off';
      decisionDescription = `First approval was recorded. As a Financial Controller/System Admin, you are authorized to provide the final internal sign-off.`;
    } else {
      decisionType = 'BLOCKED';
      decisionTitle = 'Awaiting Secondary Controller Sign-Off';
      decisionDescription = `First approval recorded. Dual-control governance strictly requires secondary review from a Financial Controller or System Admin.`;
    }
  } else if (requiresDualApproval) {
    decisionType = 'READY_FIRST';
    decisionTitle = 'Eligible for Initial Review Sign-Off (Dual Control Active)';
    decisionDescription = `All checks passed. Billed total (${formatINR(totalAmount)}) exceeds the ${formatINR(policy.dual_approval_threshold_inr)} threshold. Approving now will grant initial review sign-off and route to a Controller for second approval.`;
  } else {
    decisionType = 'READY_FIRST';
    decisionTitle = 'Eligible for Internal Review Approval';
    decisionDescription = `All ${totalGates} validation checks passed. Approving will grant internal AP review sign-off and clear the invoice for payment batching.`;
  }

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/70 shadow-2xs overflow-hidden transition-all duration-150">
      {/* Header Bar */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className={`px-3 py-2 bg-slate-50/80 dark:bg-slate-950/60 flex items-center justify-between cursor-pointer select-none hover:bg-slate-100/70 dark:hover:bg-slate-900/80 transition-colors ${
          isExpanded ? 'border-b border-slate-200 dark:border-slate-800' : ''
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-5 h-5 rounded-md bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-bold text-xs shrink-0">
            <Sparkles className="w-3 h-3" />
          </div>
          <div className="flex items-center gap-2 truncate">
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 shrink-0">
              Decision Guide:
            </span>
            <span className="text-xs text-slate-600 dark:text-slate-400 truncate">
              {decisionTitle}
            </span>
            <span className={`hidden sm:inline-flex px-1.5 py-0.2 rounded text-[10px] font-mono font-medium shrink-0 ${
              hasFailedGates
                ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
            }`}>
              {passedGates.length} of {totalGates} Checks Passed
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onOpenGlossary && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenGlossary();
              }}
              className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors p-0.5"
              title="Open Accounts Payable Glossary"
            >
              <HelpCircle className="w-3.5 h-3.5" />
            </button>
          )}
          <span className="text-[11px] font-medium text-indigo-600 dark:text-indigo-400 flex items-center gap-1 hover:underline">
            {isExpanded ? 'Collapse' : 'Explain Case'}
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </div>
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="p-4 space-y-3.5 text-xs">
          {/* Top Grid: Asking For vs Verified */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* What Invoice Asks For */}
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200/80 dark:border-slate-800/80 space-y-1.5">
              <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">
                1. What the invoice asks for
              </span>
              <div className="font-sans text-xs text-slate-800 dark:text-slate-200 space-y-0.5">
                <div>
                  Supplier <strong className="text-slate-900 dark:text-white">{invoice.vendor_name || 'Unregistered Vendor'}</strong>{' '}
                  is requesting payment of{' '}
                  <strong className="text-slate-900 dark:text-white font-mono font-bold">{formatINR(totalAmount)}</strong>.
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400">
                  Document Reference: <span className="font-mono text-slate-700 dark:text-slate-300">{invoice.invoice_number || invoice.id}</span>
                  {invoice.po_reference && (
                    <span> • Citing PO: <span className="font-mono text-slate-700 dark:text-slate-300">{invoice.po_reference}</span></span>
                  )}
                </div>
              </div>
            </div>

            {/* What Was Verified */}
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200/80 dark:border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">
                  2. What the system checked
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                  hasFailedGates
                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                    : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                }`}>
                  {passedGates.length} of {totalGates} Checks Passed
                </span>
              </div>
              <div className="text-[11px] text-slate-700 dark:text-slate-300">
                {hasFailedGates ? (
                  <div className="text-rose-700 dark:text-rose-300">
                    <strong>Failed Check:</strong> {failedGates.map((g) => g.gate_name).join(', ')}.
                    {failedGates[0]?.notes && <span className="font-mono block text-[10px] text-rose-600 dark:text-rose-400 mt-0.5">{failedGates[0].notes}</span>}
                  </div>
                ) : (
                  <div className="text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                    <span>Vendor identity, PO/GRN authorization, price tolerance (±1.50%), and GST tax arithmetic passed.</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Decision Status Banner */}
          <div className={`p-3.5 rounded-lg border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
            decisionType === 'BLOCKED'
              ? 'bg-rose-50/70 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/60 text-rose-950 dark:text-rose-200'
              : decisionType === 'COMPLETED'
              ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900/60 text-emerald-950 dark:text-emerald-200'
              : 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-900/60 text-indigo-950 dark:text-indigo-200'
          }`}>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                {decisionType === 'BLOCKED' ? (
                  <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                )}
                <h4 className="font-bold text-xs">
                  {decisionTitle}
                </h4>
              </div>
              <p className="text-[11px] opacity-90 leading-relaxed max-w-2xl pl-6">
                {decisionDescription}
              </p>
            </div>

            <div className="text-[10px] font-mono shrink-0 pl-6 sm:pl-0">
              Role: <strong className="font-sans uppercase text-slate-800 dark:text-slate-200">{userRole}</strong>
            </div>
          </div>

          {/* Transparent Evaluation Workspace Disclosure */}
          <div className="text-[10px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 px-3 py-2 rounded-lg border border-slate-200/60 dark:border-slate-800 flex items-center justify-between gap-2">
            <span>
              <strong>Evaluation Notice:</strong> Evaluated against authoritative procurement reference snapshots. Synthetic supplier & PO fixtures are used; live ERP synchronization is inactive in this evaluation workspace.
            </span>
            <span className="font-mono text-slate-400 shrink-0">Phase 2 Verification</span>
          </div>
        </div>
      )}
    </div>
  );
};
