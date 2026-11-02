import React from 'react';
import { 
  AlertTriangle, X, AlertOctagon, ShieldCheck
} from 'lucide-react';

export interface ActionConsequenceInfo {
  action: string;
  label: string;
  badgeColor: string;
  targetStage: string;
  targetSubstatus?: string;
  requiresSecondPerson: (totalAmount: number, threshold: number) => {
    required: boolean;
    explanation: string;
  };
  whatHappens: string;
  whatHappensNext: string;
  whatItDoesNOTDo: string[];
}

export const ACTION_CONSEQUENCES: Record<string, ActionConsequenceInfo> = {
  APPROVE_AP_REVIEW: {
    action: 'APPROVE_AP_REVIEW',
    label: 'Approve Invoice (Internal Sign-Off)',
    badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
    targetStage: 'INTERNAL_APPROVAL_COMPLETE (or ACTION_REQUIRED if dual-control active)',
    targetSubstatus: 'None (or PENDING_SECOND_APPROVAL if >= threshold)',
    requiresSecondPerson: (totalAmount, threshold) => {
      if (totalAmount >= threshold) {
        return {
          required: true,
          explanation: `Yes — Invoice total exceeds the ₹5,00,000 threshold. Approving now provides the initial review sign-off and flags the invoice for secondary review by a Financial Controller or System Admin.`,
        };
      }
      return {
        required: false,
        explanation: 'No — Single approval is sufficient for invoices below ₹5,00,000. Completes internal review immediately.',
      };
    },
    whatHappens: 'Records verified AP review sign-off in the append-only audit trail and advances the invoice stage.',
    whatHappensNext: 'If single approval: marked ready for external payment batching. If dual approval: moves to dedicated Approvals queue for secondary Controller sign-off.',
    whatItDoesNOTDo: [
      'Does NOT execute payment or transfer bank funds.',
      'Does NOT post entries to SAP S/4HANA or the General Ledger.',
      'Does NOT automatically clear vendor liability in ERP.',
      'CANNOT be executed if any policy validation check failed (overrides disabled).',
    ],
  },
  HOLD_PENDING_EVIDENCE: {
    action: 'HOLD_PENDING_EVIDENCE',
    label: 'Hold for Evidence',
    badgeColor: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
    targetStage: 'ACTION_REQUIRED',
    targetSubstatus: 'ON_HOLD',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'No — An AP clerk or lead can place an invoice on hold independently.',
    }),
    whatHappens: 'Suspends processing without rejecting the invoice, keeping active exception records in IN_REVIEW status.',
    whatHappensNext: 'The invoice remains visible in the Exceptions queue while the team collects missing PO, GRN, or QC evidence from warehouse or procurement.',
    whatItDoesNOTDo: [
      'Does NOT reject, void, or cancel the invoice.',
      'Does NOT penalize vendor standing or send automated notices.',
      'Does NOT remove the invoice from MSME statutory deadline tracking.',
    ],
  },
  REQUEST_SUPPLIER_CORRECTION: {
    action: 'REQUEST_SUPPLIER_CORRECTION',
    label: 'Request Supplier Correction',
    badgeColor: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300',
    targetStage: 'ACTION_REQUIRED',
    targetSubstatus: 'SUPPLIER_CORRECTION_REQUESTED',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'No — Can be initiated directly by the AP operator.',
    }),
    whatHappens: 'Flags the invoice internally as requiring supplier outreach for an amended tax invoice or credit note.',
    whatHappensNext: 'AP clerk contacts the vendor with the exact discrepancy details (e.g. rate variance, missing PO reference).',
    whatItDoesNOTDo: [
      'Does NOT send an automated email or external message to the vendor in this workspace (no vendor email integration configured).',
      'Does NOT void the invoice record until an amended replacement or credit note is received and processed.',
    ],
  },
  RAISE_DEBIT_NOTE: {
    action: 'RAISE_DEBIT_NOTE',
    label: 'Raise Debit Note',
    badgeColor: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300',
    targetStage: 'ACTION_REQUIRED',
    targetSubstatus: 'DEBIT_NOTE_PENDING',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'No — Initiated by AP clerk; formal debit note posting handled by billing operations.',
    }),
    whatHappens: 'Flags the invoice for commercial deduction due to unapproved rate markups or short-shipped quantities.',
    whatHappensNext: 'Billing operations drafts a formal commercial debit note against the vendor account balance.',
    whatItDoesNOTDo: [
      'Does NOT automatically debit vendor sub-ledger in SAP.',
      'Does NOT approve the remaining disputed balance.',
    ],
  },
  ESCALATE: {
    action: 'ESCALATE',
    label: 'Escalate to Senior Stakeholder',
    badgeColor: 'bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300',
    targetStage: 'ACTION_REQUIRED',
    targetSubstatus: 'ESCALATED',
    requiresSecondPerson: () => ({
      required: true,
      explanation: 'Yes — Escalation reassigns the case to a Procurement Category Manager or Financial Controller for resolution.',
    }),
    whatHappens: 'Reassigns the invoice out of the standard AP queue to executive management.',
    whatHappensNext: 'The designated manager reviews procurement contracts, evaluates commercial trade-offs, and provides written instructions.',
    whatItDoesNOTDo: [
      'Does NOT approve the invoice.',
      'Does NOT override validation checks without authorized sign-off.',
    ],
  },
  REJECT_INVOICE: {
    action: 'REJECT_INVOICE',
    label: 'Reject Invoice Permanently',
    badgeColor: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
    targetStage: 'ACTION_REQUIRED (Decision: REJECTED)',
    targetSubstatus: 'None',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'Restricted Action — Strictly requires AP Lead, Financial Controller, or System Admin role.',
    }),
    whatHappens: 'Permanently rejects and archives the invoice, closing all associated exception records with resolution notes.',
    whatHappensNext: 'The invoice is moved to the Archived/Rejected registry. Re-submission requires a completely new invoice file.',
    whatItDoesNOTDo: [
      'This action is PERMANENT and CANNOT be reversed or approved later.',
      'Does NOT send an automated rejection email to the vendor in this workspace.',
    ],
  },
};

interface ConsequenceAwareActionModalProps {
  isOpen: boolean;
  action: string | null;
  invoice: any;
  policy: {
    dual_approval_threshold_inr: number;
    rate_tolerance_percent: number;
    rounding_tolerance_inr: number;
  };
  reason: string;
  onReasonChange: (val: string) => void;
  reasonTemplates: string[];
  isLoading: boolean;
  errorMessage: string | null;
  onConfirm: () => void;
  onClose: () => void;
  hasFailedGates: boolean;
}

export const ConsequenceAwareActionModal: React.FC<ConsequenceAwareActionModalProps> = ({
  isOpen,
  action,
  invoice,
  policy,
  reason,
  onReasonChange,
  reasonTemplates,
  isLoading,
  errorMessage,
  onConfirm,
  onClose,
  hasFailedGates,
}) => {
  if (!isOpen || !action) return null;

  const info = ACTION_CONSEQUENCES[action] || {
    action,
    label: action,
    badgeColor: 'bg-slate-100 text-slate-800',
    targetStage: 'Updated Stage',
    requiresSecondPerson: () => ({ required: false, explanation: 'Standard review permissions.' }),
    whatHappens: 'Updates invoice state and records append-only audit event.',
    whatHappensNext: 'Processes according to standard operational workflow.',
    whatItDoesNOTDo: ['Does not execute payment.'],
  };

  const totalAmount = invoice.total_amount || 0;
  const secondPersonCheck = info.requiresSecondPerson(totalAmount, policy.dual_approval_threshold_inr);
  const isApproveBlocked = action === 'APPROVE_AP_REVIEW' && hasFailedGates;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div 
        className="w-full max-w-xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[90vh] overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="consequence-modal-title"
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center border border-indigo-200 dark:border-indigo-800">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="consequence-modal-title" className="text-sm font-bold text-slate-900 dark:text-white">
                  Confirm Action: {info.label}
                </h2>
                <code className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  {action}
                </code>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Review workflow consequences and state transitions before executing.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4 text-xs">
          {/* Failed-gate warning for approval attempt */}
          {isApproveBlocked && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-900 text-rose-950 dark:text-rose-200 flex items-start gap-2.5">
              <AlertOctagon className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <strong className="block font-bold">Approval Blocked by Policy Verification</strong>
                <p className="text-[11px] mt-0.5 leading-relaxed">
                  This invoice failed 1 or more policy validation checks. Policy overrides are disabled. Approval cannot proceed. Please close this modal and choose an authorized triage action (Hold, Ask Supplier to Correct, Debit Note, Escalate, or Reject).
                </p>
              </div>
            </div>
          )}

          {/* Consequence Grid */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-3">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Operational Consequence Breakdown
            </h3>

            <div className="space-y-2 text-[11px]">
              <div>
                <span className="text-slate-500 dark:text-slate-400 block font-sans">1. What this does:</span>
                <p className="text-slate-800 dark:text-slate-200 font-medium mt-0.5">
                  {info.whatHappens}
                </p>
              </div>

              <div>
                <span className="text-slate-500 dark:text-slate-400 block font-sans">2. Resulting workflow state:</span>
                <code className="text-indigo-700 dark:text-indigo-300 font-mono text-[10px] bg-indigo-50 dark:bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-200/60 dark:border-indigo-800/60 inline-block mt-0.5">
                  Stage: {info.targetStage}
                </code>
              </div>

              <div>
                <span className="text-slate-500 dark:text-slate-400 block font-sans">3. Does this require another person?</span>
                <p className="text-slate-800 dark:text-slate-200 font-medium mt-0.5">
                  {secondPersonCheck.explanation}
                </p>
              </div>

              <div>
                <span className="text-slate-500 dark:text-slate-400 block font-sans">4. What happens next:</span>
                <p className="text-slate-800 dark:text-slate-200 font-medium mt-0.5">
                  {info.whatHappensNext}
                </p>
              </div>
            </div>

            {/* Explicit "What It Does NOT Do" Panel */}
            <div className="p-2.5 rounded-lg bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-amber-950 dark:text-amber-200 space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-[11px] text-amber-900 dark:text-amber-300">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                <span>What this action does NOT do:</span>
              </div>
              <ul className="list-disc list-inside space-y-0.5 text-[10px] pl-1 opacity-90 leading-relaxed font-sans">
                {info.whatItDoesNOTDo.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Operational Justification Input */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor="action-reason" className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Audit Justification Reason <span className="text-rose-500">*</span>
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {reason.length >= 3 ? 'Valid' : 'Min 3 chars required'}
              </span>
            </div>

            {/* Quick pre-populated reason templates */}
            {reasonTemplates.length > 0 && (
              <div className="space-y-1">
                <span className="text-[10px] text-slate-400 font-medium">Quick Templates:</span>
                <div className="flex flex-wrap gap-1.5">
                  {reasonTemplates.map((t, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onReasonChange(t)}
                      className="text-[10px] px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-left transition-colors truncate max-w-full"
                    >
                      "{t}"
                    </button>
                  ))}
                </div>
              </div>
            )}

            <textarea
              id="action-reason"
              rows={3}
              value={reason}
              onChange={(e) => onReasonChange(e.target.value)}
              placeholder="Explain the operational rationale for this decision (recorded permanently in the append-only audit trail)..."
              className="w-full p-2.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {errorMessage && (
            <div className="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs">
              {errorMessage}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 sm:p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex flex-col-reverse sm:flex-row sm:items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading || reason.trim().length < 3 || isApproveBlocked}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold text-white shadow-xs transition-colors flex items-center gap-1.5 ${
              isApproveBlocked
                ? 'bg-slate-400 cursor-not-allowed opacity-60'
                : action === 'REJECT_INVOICE'
                ? 'bg-rose-600 hover:bg-rose-500'
                : action === 'HOLD_PENDING_EVIDENCE'
                ? 'bg-amber-600 hover:bg-amber-500'
                : 'bg-indigo-600 hover:bg-indigo-500'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isLoading ? 'Recording...' : `Confirm ${info.label}`}
          </button>
        </div>
      </div>
    </div>
  );
};
