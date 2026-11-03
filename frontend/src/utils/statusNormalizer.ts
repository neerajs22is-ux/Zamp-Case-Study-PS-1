/**
 * Centralized Status Normalization Utility
 * Implements Section 3.3 of FRONTEND_UX_IMPLEMENTATION_SPEC.md
 * 
 * Maps all database and workflow status permutations to clear, human-understandable
 * labels, semantic tones, and action-oriented explanation copy.
 */

export type StatusTone = 'default' | 'success' | 'warning' | 'error' | 'info' | 'purple';

export interface NormalizedStatus {
  key: string;
  label: string;
  tone: StatusTone;
  badgeClass: string;
  iconName: 'clock' | 'check' | 'alert' | 'x' | 'pause' | 'refresh' | 'shield';
  reason: string;
  description?: string;
  isApprovalCandidate: boolean;
  isBlocked: boolean;
}

export interface StatusInput {
  stage?: string | null;
  decision?: string | null;
  workflow_substatus?: string | null;
  decision_reason?: string | null;
  total_amount?: number | null;
  approval_status?: string | null;
  job_status?: string | null;
  job_error?: string | null;
}

export function statusFor(invoice: StatusInput): NormalizedStatus {
  const stage = (invoice.stage || '').toUpperCase().trim();
  const decision = (invoice.decision || '').toUpperCase().trim();
  const substatus = (invoice.workflow_substatus || '').toUpperCase().trim();
  const reason = invoice.decision_reason || '';

  // 1. Terminal Rejection
  if (decision === 'REJECTED' || stage === 'REJECTED') {
    return {
      key: 'REJECTED',
      label: 'Rejected',
      tone: 'error',
      badgeClass: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/50',
      iconName: 'x',
      reason: reason || 'Invoice was rejected during internal review.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 2. Quarantined / Non-payable Document
  if (stage === 'QUARANTINED' || decision === 'QUARANTINED' || decision === 'COMMERCIAL_NON_PAYABLE_RECEIPT') {
    return {
      key: 'QUARANTINED',
      label: 'Set aside (not an invoice)',
      tone: 'purple',
      badgeClass: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-900/50',
      iconName: 'shield',
      reason: reason || 'Non-payable document, payment receipt, or corrupt file quarantined.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 3. Approved States
  if (
    stage === 'INTERNAL_APPROVAL_COMPLETE' || 
    decision === 'MANUALLY_APPROVED' || 
    decision === 'APPROVED'
  ) {
    return {
      key: 'APPROVED',
      label: 'Approved',
      tone: 'success',
      badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50',
      iconName: 'check',
      reason: 'Internal review complete (Internal sign-off). No ERP posting or payment executed.',
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  if (decision === 'AUTO_APPROVED') {
    return {
      key: 'AUTO_APPROVED',
      label: 'Approved (automatic)',
      tone: 'success',
      badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50',
      iconName: 'check',
      reason: 'Touchless straight-through matching passed all 7 policy gates.',
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 4. Dual Approval: Waiting for Controller / Second Sign-off
  if (
    stage === 'PENDING_SECOND_APPROVAL' ||
    invoice.approval_status === 'PENDING_SECOND_APPROVAL' ||
    reason.toLowerCase().includes('first approval recorded')
  ) {
    return {
      key: 'PENDING_SECOND_APPROVAL',
      label: 'Waiting for second approval',
      tone: 'purple',
      badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-900/50',
      iconName: 'pause',
      reason: 'High-value invoice (≥ ₹5,00,000) approved by AP Lead. Awaiting Controller or Administrator sign-off.',
      isApprovalCandidate: true,
      isBlocked: false,
    };
  }

  // 5. Triage & Exception Holds (Substatus or Action-Required Derivations)
  if (substatus === 'HOLD_PENDING_EVIDENCE' || reason.toLowerCase().includes('hold pending evidence')) {
    return {
      key: 'HOLD_PENDING_EVIDENCE',
      label: 'On hold',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'pause',
      reason: reason || 'Held pending external documentation or operational evidence.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (substatus === 'REQUEST_SUPPLIER_CORRECTION' || reason.toLowerCase().includes('supplier correction')) {
    return {
      key: 'REQUEST_SUPPLIER_CORRECTION',
      label: 'Waiting for supplier',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'clock',
      reason: reason || 'Discrepancy communicated to supplier. Awaiting revised invoice or credit note.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (substatus === 'RAISE_DEBIT_NOTE' || reason.toLowerCase().includes('debit note')) {
    return {
      key: 'RAISE_DEBIT_NOTE',
      label: 'Debit note pending',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'alert',
      reason: reason || 'Price or quantity variance requires debit note issuance prior to clearance.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (substatus === 'ESCALATE' || reason.toLowerCase().includes('escalated')) {
    return {
      key: 'ESCALATE',
      label: 'Escalated',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'alert',
      reason: reason || 'Escalated to senior finance or commercial management for policy review.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 6. Needs Attention: Unresolved Exceptions & Degraded Scans
  if (decision === 'FLAGGED_HITL_REVIEW') {
    return {
      key: 'FLAGGED_HITL_REVIEW',
      label: 'Needs attention — check scan',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'alert',
      reason: reason || 'Scanned or degraded document requires human-in-the-loop field verification.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    stage === 'ACTION_REQUIRED' || 
    decision === 'FLAGGED_EXCEPTION' || 
    decision === 'FLAGGED_LINE_VARIANCE' ||
    decision === 'FLAGGED_TAX_DISCREPANCY'
  ) {
    return {
      key: 'NEEDS_ATTENTION',
      label: 'Needs attention',
      tone: 'warning',
      badgeClass: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50',
      iconName: 'alert',
      reason: reason || 'Verification checks identified discrepancy against PO, GRN, or tax arithmetic.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 7. Ready to Approve: Clean 7-Gate Match Candidate
  if (decision === 'MATCH_CANDIDATE' || stage === 'PENDING_APPROVAL') {
    return {
      key: 'READY_TO_APPROVE',
      label: 'Ready to approve',
      tone: 'success',
      badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50',
      iconName: 'check',
      reason: reason || 'All 7 policy checks passed. Ready for authorized sign-off.',
      isApprovalCandidate: true,
      isBlocked: false,
    };
  }

  // 8. Processing Pipeline States
  if (
    ['VALIDATING', 'PARSING', 'EXTRACTED', 'MATCHING', 'PROCESSING'].includes(stage) ||
    ['PROCESSING', 'EXTRACTING'].includes(decision)
  ) {
    return {
      key: 'PROCESSING',
      label: 'Processing',
      tone: 'info',
      badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50',
      iconName: 'refresh',
      reason: 'Reading document and evaluating commercial policy gates...',
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 9. Initial Ingested State & Processing Jobs
  if (invoice.job_status === 'FAILED' || reason.toLowerCase().includes('processing failed')) {
    return {
      key: 'PROCESSING_FAILED',
      label: 'Processing failed',
      tone: 'error',
      badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-900/50',
      iconName: 'alert',
      reason: invoice.job_error || reason || 'Document processing encountered an error. Please retry or enter details manually.',
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (invoice.job_status === 'PROCESSING' || invoice.job_status === 'QUEUED') {
    return {
      key: 'READING',
      label: 'Reading invoice…',
      tone: 'info',
      badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50',
      iconName: 'refresh',
      reason: 'Reading invoice fields and cross-checking against procurement records…',
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  if (stage === 'RECEIVED' || decision === 'NEEDS_REVIEW' || stage === 'QUEUED') {
    return {
      key: 'RECEIVED',
      label: 'Reading invoice…',
      tone: 'info',
      badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50',
      iconName: 'refresh',
      reason: reason || 'Document received. Reading fields and evaluating policy gates…',
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 10. Fallback: Unrecognized Status (Clean, non-crashing display)
  return {
    key: 'UNKNOWN',
    label: stage || decision || 'Unknown Status',
    tone: 'default',
    badgeClass: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
    iconName: 'clock',
    reason: reason || `Unrecognized workflow status: stage="${stage}", decision="${decision}"`,
    isApprovalCandidate: false,
    isBlocked: false,
  };
}
