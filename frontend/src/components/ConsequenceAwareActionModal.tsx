import React from 'react';
import { 
  AlertTriangle, AlertOctagon, ShieldCheck
} from 'lucide-react';
import { Modal, Button, Badge } from './ui';

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
    label: 'Approve Invoice',
    badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
    targetStage: 'INTERNAL_APPROVAL_COMPLETE',
    targetSubstatus: 'None (or PENDING_SECOND_APPROVAL if >= threshold)',
    requiresSecondPerson: (totalAmount, threshold) => {
      if (totalAmount >= threshold) {
        return {
          required: true,
          explanation: `Invoice total exceeds ₹5,00,000. Approving now records primary review and routes to Financial Controller for dual sign-off.`,
        };
      }
      return {
        required: false,
        explanation: 'Single approval sufficient. Marks invoice ready for payment batching.',
      };
    },
    whatHappens: 'Records internal review approval in the immutable audit trail.',
    whatHappensNext: 'Routes to external payment batching or secondary controller review.',
    whatItDoesNOTDo: [
      'Does NOT disburse funds from company bank accounts.',
      'Does NOT post directly to the SAP General Ledger.',
      'Cannot override hard policy verification failures.',
    ],
  },
  HOLD_PENDING_EVIDENCE: {
    action: 'HOLD_PENDING_EVIDENCE',
    label: 'Hold for Evidence',
    badgeColor: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
    targetStage: 'ACTION_REQUIRED (ON_HOLD)',
    targetSubstatus: 'ON_HOLD',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'AP reviewer can place an invoice on hold independently.',
    }),
    whatHappens: 'Suspends processing while warehouse or procurement evidence is collected.',
    whatHappensNext: 'Invoice remains flagged in Exceptions queue for follow-up.',
    whatItDoesNOTDo: [
      'Does NOT reject or void the vendor invoice.',
      'Does NOT remove from statutory MSME tracking.',
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
      explanation: 'Initiated directly by the AP operator.',
    }),
    whatHappens: 'Flags invoice as requiring revised tax invoice or credit note from supplier.',
    whatHappensNext: 'AP team contacts supplier citing the exact variance.',
    whatItDoesNOTDo: [
      'Does NOT automatically dispatch external emails without review.',
      'Does NOT void the bill until replacement is ingested.',
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
      explanation: 'Initiated by AP reviewer.',
    }),
    whatHappens: 'Flags invoice for commercial deduction due to rate markup or physical shortage.',
    whatHappensNext: 'Billing team issues debit note against vendor ledger balance.',
    whatItDoesNOTDo: [
      'Does NOT automatically post debits to ERP.',
      'Does NOT approve disputed invoice amount.',
    ],
  },
  QUARANTINE: {
    action: 'QUARANTINE',
    label: 'Set Aside (Quarantine)',
    badgeColor: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300',
    targetStage: 'QUARANTINED',
    targetSubstatus: 'QUARANTINED',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'Single operator quarantine permitted.',
    }),
    whatHappens: 'Quarantines non-payable documents, payment receipts, or corrupted scans.',
    whatHappensNext: 'Isolates file from payment queues so false balances are not generated.',
    whatItDoesNOTDo: [
      'Does NOT permanently delete the original uploaded file.',
    ],
  },
  REJECT_INVOICE: {
    action: 'REJECT_INVOICE',
    label: 'Reject Invoice',
    badgeColor: 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
    targetStage: 'REJECTED',
    targetSubstatus: 'TERMINAL_REJECTION',
    requiresSecondPerson: () => ({
      required: false,
      explanation: 'AP reviewer terminal rejection.',
    }),
    whatHappens: 'Marks invoice permanently rejected for commercial or tax non-compliance.',
    whatHappensNext: 'Supplier must issue a completely new bill if transaction is valid.',
    whatItDoesNOTDo: [
      'Cannot be undone automatically; re-opening requires administrative intervention.',
    ],
  },
};

interface ConsequenceAwareActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  action: string;
  invoice: any;
  hasFailedGates: boolean;
  reason: string;
  onReasonChange: (reason: string) => void;
  isLoading?: boolean;
  errorMessage?: string | null;
  policy: {
    dual_approval_threshold_inr: number;
    rate_tolerance_percent: number;
    rounding_tolerance_inr: number;
  };
}

export const ConsequenceAwareActionModal: React.FC<ConsequenceAwareActionModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  action,
  invoice,
  hasFailedGates,
  reason,
  onReasonChange,
  isLoading = false,
  errorMessage = null,
  policy,
}) => {
  if (!isOpen) return null;

  const info = ACTION_CONSEQUENCES[action] || {
    action,
    label: action.replace(/_/g, ' '),
    badgeColor: 'bg-slate-100 text-slate-800',
    targetStage: 'Updated Stage',
    requiresSecondPerson: () => ({ required: false, explanation: 'Standard review permissions.' }),
    whatHappens: 'Updates invoice state and records append-only audit event.',
    whatHappensNext: 'Processes according to standard operational workflow.',
    whatItDoesNOTDo: ['Does not execute payment.'],
  };

  const totalAmount = invoice.total_amount || 0;
  const isApproveBlocked = action === 'APPROVE_AP_REVIEW' && hasFailedGates;
  const isDualApproval = action === 'APPROVE_AP_REVIEW' && totalAmount >= policy.dual_approval_threshold_inr;

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const templates: Record<string, string[]> = {
    APPROVE_AP_REVIEW: [
      'Line quantities and rates reconciled against PO & GRN. Approved for payment batching.',
      'Clean 3-way match verified. Approved for settlement.',
    ],
    HOLD_PENDING_EVIDENCE: [
      'Awaiting physical GRN confirmation from warehouse.',
      'Awaiting quality inspection acceptance certificate.',
    ],
    REQUEST_SUPPLIER_CORRECTION: [
      'Invoice unit rate exceeds approved purchase order rate.',
      'Billed quantity exceeds physically received units.',
    ],
    RAISE_DEBIT_NOTE: [
      'Debit note initiated for 5 short-shipped units.',
      'Rate discrepancy difference charged back to vendor.',
    ],
    QUARANTINE: [
      'Document is a payment receipt, not a payable tax invoice.',
      'Duplicate scan of previously processed bill.',
    ],
    REJECT_INVOICE: [
      'Supplier GSTIN invalid or inactive on government portal.',
      'Unauthorized purchase order reference.',
    ],
  };

  const reasonTemplates = templates[action] || [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span>Confirm Action: {info.label}</span>
        </div>
      }
      description="Review workflow outcome and record audit justification."
      maxWidth="lg"
      footer={
        <div className="flex items-center justify-end gap-2.5 w-full">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={action === 'REJECT_INVOICE' ? 'danger' : 'primary'}
            size="sm"
            onClick={onConfirm}
            isLoading={isLoading}
            disabled={isApproveBlocked || reason.trim().length < 3}
          >
            Confirm {info.label}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {/* Failed-gate warning */}
        {isApproveBlocked && (
          <div className="p-3.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-900 text-rose-900 dark:text-rose-200 flex items-start gap-2.5">
            <AlertOctagon className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <strong className="block font-bold">Approval Blocked by Policy Verification</strong>
              <p className="mt-0.5 leading-relaxed text-[11px]">
                This invoice has unresolved discrepancies. Overrides are disabled. Please choose an authorized action (Hold for Evidence, Request Supplier Correction, or Reject).
              </p>
            </div>
          </div>
        )}

        {/* Dual-approval banner */}
        {isDualApproval && (
          <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 space-y-1.5">
            <div className="flex items-center justify-between font-semibold text-purple-900 dark:text-purple-200">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                <span>Dual-Approval Required (Amount: {formatINR(totalAmount)})</span>
              </span>
              <Badge tone="purple" size="sm">Threshold: {formatINR(policy.dual_approval_threshold_inr)}</Badge>
            </div>
            <p className="text-[11px] text-purple-800 dark:text-purple-300">
              This approval serves as Step 1 (Primary Review). The invoice will route to the Financial Controller for final dual sign-off.
            </p>
          </div>
        )}

        {/* Action Summary Card */}
        <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 font-medium">
            <span>Resulting State:</span>
            <Badge tone="neutral" size="sm">{info.targetStage}</Badge>
          </div>
          <div>
            <span className="text-slate-500 dark:text-slate-400 block font-medium">Outcome:</span>
            <p className="text-slate-800 dark:text-slate-200 mt-0.5 font-medium">{info.whatHappens}</p>
          </div>
          <div className="pt-2 border-t border-slate-200/60 dark:border-slate-750">
            <span className="text-[11px] font-semibold text-amber-800 dark:text-amber-400 flex items-center gap-1 mb-1">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Boundary Guarantee:</span>
            </span>
            <ul className="list-disc list-inside text-[11px] text-slate-600 dark:text-slate-400 space-y-0.5">
              {info.whatItDoesNOTDo.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Audit Justification */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="action-reason" className="font-semibold text-slate-800 dark:text-slate-200">
              Audit Note / Justification <span className="text-rose-500">*</span>
            </label>
            <span className="text-[10px] text-slate-400 font-mono">
              {reason.length >= 3 ? 'Valid' : 'Min 3 chars'}
            </span>
          </div>

          {reasonTemplates.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1">
              {reasonTemplates.map((t, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onReasonChange(t)}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  "{t.slice(0, 45)}..."
                </button>
              ))}
            </div>
          )}

          <textarea
            id="action-reason"
            rows={2}
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
            placeholder="Reason for this decision (recorded in the permanent audit trail)..."
            className="w-full p-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {errorMessage && (
          <div className="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs">
            {errorMessage}
          </div>
        )}
      </div>
    </Modal>
  );
};
