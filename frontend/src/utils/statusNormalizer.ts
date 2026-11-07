/**
 * Centralized Status Normalization Utility
 * Implements Section 3.3 of FRONTEND_UX_IMPLEMENTATION_SPEC.md
 *
 * Maps all database and workflow status permutations to clear, human-understandable
 * labels, semantic tones, and action-oriented explanation copy.
 */

export type StatusTone =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "purple";

export interface NormalizedStatus {
  key: string;
  label: string;
  tone: StatusTone;
  badgeClass: string;
  iconName: "clock" | "check" | "alert" | "x" | "pause" | "refresh" | "shield";
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
  const stage = (invoice.stage || "").toUpperCase().trim();
  const decision = (invoice.decision || "").toUpperCase().trim();
  const substatus = (invoice.workflow_substatus || "").toUpperCase().trim();
  const reason = invoice.decision_reason || "";

  // 1. Terminal Rejection
  if (decision === "REJECTED" || stage === "REJECTED") {
    return {
      key: "REJECTED",
      label: "Rejected",
      tone: "error",
      badgeClass:
        "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/50",
      iconName: "x",
      reason: reason || "Invoice was rejected during internal review.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 2. Quarantined / Non-payable Document
  if (
    stage === "QUARANTINED" ||
    decision === "QUARANTINED" ||
    decision === "COMMERCIAL_NON_PAYABLE_RECEIPT"
  ) {
    return {
      key: "QUARANTINED",
      label: "Set aside for investigation",
      tone: "purple",
      badgeClass:
        "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-900/50",
      iconName: "shield",
      reason:
        reason ||
        "The record is set aside. Inspect its source and recorded reason before taking further action.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 3. Approved States
  if (
    stage === "INTERNAL_APPROVAL_COMPLETE" ||
    decision === "MANUALLY_APPROVED" ||
    decision === "APPROVED"
  ) {
    return {
      key: "APPROVED",
      label: "Internal sign-off recorded",
      tone: "success",
      badgeClass:
        "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50",
      iconName: "check",
      reason:
        "Internal review complete (Internal sign-off). No ERP posting or payment executed.",
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  if (decision === "AUTO_APPROVED") {
    return {
      key: "AUTO_APPROVED",
      label: "Automatic internal approval recorded",
      tone: "success",
      badgeClass:
        "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50",
      iconName: "check",
      reason:
        reason ||
        "An automatic approval decision is recorded. Inspect the returned checks for its supporting evidence.",
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 4. Dual Approval: Waiting for Controller / Second Sign-off
  if (
    stage === "PENDING_SECOND_APPROVAL" ||
    invoice.approval_status === "PENDING_SECOND_APPROVAL" ||
    reason.toLowerCase().includes("first approval recorded")
  ) {
    return {
      key: "PENDING_SECOND_APPROVAL",
      label: "Waiting for second approval",
      tone: "purple",
      badgeClass:
        "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-900/50",
      iconName: "pause",
      reason:
        reason ||
        "A second internal sign-off is pending. Inspect the first reviewer, checks and eligibility; the server validates authorization.",
      isApprovalCandidate: true,
      isBlocked: false,
    };
  }

  // 5. Triage & Exception Holds (Substatus or Action-Required Derivations)
  if (
    ["HOLD_PENDING_EVIDENCE", "ON_HOLD"].includes(substatus) ||
    reason.toLowerCase().includes("hold pending evidence")
  ) {
    return {
      key: "HOLD_PENDING_EVIDENCE",
      label: "On hold",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "pause",
      reason:
        reason ||
        "Held pending external documentation or operational evidence.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    ["REQUEST_SUPPLIER_CORRECTION", "SUPPLIER_CORRECTION_REQUESTED"].includes(
      substatus,
    ) ||
    reason.toLowerCase().includes("supplier correction")
  ) {
    return {
      key: "REQUEST_SUPPLIER_CORRECTION",
      label: "Supplier correction needed",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "clock",
      reason:
        reason ||
        "Follow-up is recorded internally. Your team must contact the supplier outside this app; no email is sent by this action.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    ["RAISE_DEBIT_NOTE", "DEBIT_NOTE_PENDING"].includes(substatus) ||
    reason.toLowerCase().includes("debit note")
  ) {
    return {
      key: "RAISE_DEBIT_NOTE",
      label: "Debit note pending",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "alert",
      reason:
        reason ||
        "Price or quantity variance requires debit note issuance prior to clearance.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    ["ESCALATE", "ESCALATED"].includes(substatus) ||
    reason.toLowerCase().includes("escalated")
  ) {
    return {
      key: "ESCALATE",
      label: "Escalated",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "alert",
      reason:
        reason ||
        "Escalated to senior finance or commercial management for policy review.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    invoice.job_status === "FAILED" ||
    reason.toLowerCase().includes("processing failed")
  ) {
    return {
      key: "PROCESSING_FAILED",
      label: "Processing failed",
      tone: "error",
      badgeClass:
        "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-900/50",
      iconName: "alert",
      reason:
        "Document processing failed. Open the invoice to inspect available source evidence and recorded results.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 6. Needs Attention: Unresolved Exceptions & Degraded Scans
  if (decision === "FLAGGED_HITL_REVIEW") {
    return {
      key: "FLAGGED_HITL_REVIEW",
      label: "Needs attention — check scan",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "alert",
      reason:
        reason ||
        "Scanned or degraded document requires human-in-the-loop field verification.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  if (
    stage === "ACTION_REQUIRED" ||
    decision === "FLAGGED_EXCEPTION" ||
    decision === "FLAGGED_LINE_VARIANCE" ||
    decision === "FLAGGED_TAX_DISCREPANCY"
  ) {
    return {
      key: "NEEDS_ATTENTION",
      label: "Needs attention",
      tone: "warning",
      badgeClass:
        "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/50",
      iconName: "alert",
      reason:
        reason ||
        "Verification checks identified discrepancy against PO, GRN, or tax arithmetic.",
      isApprovalCandidate: false,
      isBlocked: true,
    };
  }

  // 7. Ready to Approve: Clean 7-Gate Match Candidate
  if (decision === "MATCH_CANDIDATE" || stage === "PENDING_APPROVAL") {
    return {
      key: "READY_TO_APPROVE",
      label: "Ready for review",
      tone: "success",
      badgeClass:
        "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/50",
      iconName: "check",
      reason:
        reason ||
        "A match candidate or pending-review stage is recorded. Inspect all check results and approval prerequisites before sign-off.",
      isApprovalCandidate: true,
      isBlocked: false,
    };
  }

  // 8. Processing Pipeline States
  if (
    ["VALIDATING", "PARSING", "EXTRACTED", "MATCHING", "PROCESSING"].includes(
      stage,
    ) ||
    ["PROCESSING", "EXTRACTING"].includes(decision)
  ) {
    return {
      key: "PROCESSING",
      label: "Processing reported",
      tone: "info",
      badgeClass:
        "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50",
      iconName: "refresh",
      reason:
        "A processing-related state was returned at the last refresh. This is not a live stage-by-stage execution feed.",
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 9. Initial Ingested State & Processing Jobs
  if (invoice.job_status === "PROCESSING" || invoice.job_status === "QUEUED") {
    return {
      key: "READING",
      label:
        invoice.job_status === "QUEUED"
          ? invoice.job_error
            ? "Retry queue reported"
            : "Queue reported at last refresh"
          : "Processing at last refresh",
      tone: "info",
      badgeClass:
        "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50",
      iconName: "refresh",
      reason:
        "The last response reported a queued or processing job. Earlier attempts may have failed; refresh to check its current recorded status.",
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  if (
    stage === "RECEIVED" ||
    decision === "NEEDS_REVIEW" ||
    stage === "QUEUED"
  ) {
    return {
      key: "RECEIVED",
      label:
        stage === "RECEIVED"
          ? "Received"
          : stage === "QUEUED"
            ? "Queue reported"
            : "Review needed",
      tone: "info",
      badgeClass:
        "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900/50",
      iconName: "refresh",
      reason:
        reason ||
        "A record was received, but this response does not confirm active processing. Open it to inspect available results.",
      isApprovalCandidate: false,
      isBlocked: false,
    };
  }

  // 10. Fallback: Unrecognized Status (Clean, non-crashing display)
  return {
    key: "UNKNOWN",
    label: stage || decision || "Unknown Status",
    tone: "default",
    badgeClass:
      "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700",
    iconName: "clock",
    reason:
      reason ||
      `Unrecognized workflow status: stage="${stage}", decision="${decision}"`,
    isApprovalCandidate: false,
    isBlocked: false,
  };
}
