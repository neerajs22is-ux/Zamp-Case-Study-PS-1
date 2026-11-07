import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  FileText,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle2,
  ZoomIn,
  ZoomOut,
  ExternalLink,
  ShieldCheck,
  CheckCircle,
  MoreVertical,
} from "lucide-react";
import { api } from "../api/client";
import { InvoiceRunView } from "../components/InvoiceRunView";
import { StatusBadge } from "../components/StatusBadge";
import { summarizeCheckResults } from "../utils/checkResults";
import { DEFAULT_POLICY } from "../content/policy";
import "./InvoiceDetailPage.css";
import { GlossaryModal } from "../components/GlossaryModal";
import { CaseSummaryCard } from "../components/CaseSummaryCard";
import { ProcurementVerificationFlow } from "../components/ProcurementVerificationFlow";
import { PolicyChecksGrouped } from "../components/PolicyChecksGrouped";
import { ConsequenceAwareActionModal } from "../components/ConsequenceAwareActionModal";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  Badge,
  Drawer,
  LoadingState,
  ErrorState,
} from "../components/ui";
import type { AuthenticatedUser, InvoiceDetailData, MatchGateItem } from "../types";

interface InvoiceDetailPageProps {
  invoiceId: string;
  onBack: () => void;
  currentUser?: AuthenticatedUser | null;
}

type TabType = "reconciliation" | "history";

export const InvoiceDetailPage: React.FC<InvoiceDetailPageProps> = ({
  invoiceId,
  onBack,
  currentUser,
}) => {
  const [data, setData] = useState<InvoiceDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correctionRefreshRequired, setCorrectionRefreshRequired] =
    useState(false);

  // Navigation & Tabs
  const [activeTab, setActiveTab] = useState<TabType>("reconciliation");
  const [policyDrawerOpen, setPolicyDrawerOpen] = useState(false);
  const [actionsMenuOpen, setActionsMenuOpen] = useState(false);

  // Document Viewer State
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [copiedSha, setCopiedSha] = useState(false);
  const [refreshingDocUrl, setRefreshingDocUrl] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  // Decision & Action State
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Glossary Modal State
  const [showGlossary, setShowGlossary] = useState(false);
  const [glossaryTerm, setGlossaryTerm] = useState<string | undefined>(
    undefined,
  );

  const openGlossaryWithTerm = (term?: string) => {
    setGlossaryTerm(term);
    setShowGlossary(true);
  };

  const dualApprovalThreshold =
    data?.policy?.dual_approval_threshold_inr ||
    data?.approval?.threshold_inr ||
    DEFAULT_POLICY.dual_approval_threshold_inr;
  const rateTolerancePercent =
    data?.policy?.rate_tolerance_percent ||
    DEFAULT_POLICY.rate_tolerance_percent;

  const loadDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getInvoiceDetail(invoiceId);
      setData(res);
      setCorrectionRefreshRequired(false);
      setPreviewUrl(res.document?.preview_url || null);
      setDocumentError(null);
    } catch (err: any) {
      setError(err.message || "Failed to retrieve invoice detail.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [invoiceId]);

  const handleRefreshSignedUrl = async () => {
    if (!data?.document?.document_id) return;
    setRefreshingDocUrl(true);
    setDocumentError(null);
    try {
      const res = await api.getDocumentSignedUrl(
        data.document.document_id,
        300,
      );
      setPreviewUrl(res.signed_url);
    } catch (err: any) {
      console.error("Failed to refresh document signed URL:", err);
      setDocumentError(
        "Could not refresh the document link. Please try again.",
      );
    } finally {
      setRefreshingDocUrl(false);
    }
  };

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2000);
  };

  const handleExecuteAction = async () => {
    if (!selectedAction) return;
    if (actionReason.trim().length < 3) {
      setActionError(
        "Operational justification reason must be at least 3 characters.",
      );
      return;
    }

    const checks = data?.match_gates || [];
    const hasFailedGate = checks.length < 7 || checks.some((g: MatchGateItem) => g.status !== "PASS");
    if (selectedAction === "APPROVE_AP_REVIEW" && hasFailedGate) {
      setActionError(
        "Approval blocked: this invoice failed policy validation checks. Please resolve discrepancies first.",
      );
      return;
    }

    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await api.executeAction(invoiceId, selectedAction, actionReason.trim());
      setActionSuccess("Action recorded successfully.");
      setSelectedAction(null);
      setActionReason("");
      await loadDetail();
    } catch (err: any) {
      setActionError(err.message || "Action execution failed.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCorrectLine = async (
    lineId: string,
    payload: {
      billed_quantity: number;
      billed_unit_rate: number;
      correction_reason: string;
    },
  ) => {
    if (!data?.invoice) return;
    const ifMatch = data.invoice.updated_at;
    await api.correctInvoiceLine(data.invoice.id, lineId, payload, ifMatch);
    setCorrectionRefreshRequired(true);
    await loadDetail();
  };

  const formatINR = (val?: number | null) => {
    if (val === undefined || val === null) return "—";
    if (data?.invoice?.currency !== "INR") return "INR equivalent unavailable";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);
  };

  if (correctionRefreshRequired && loading) {
    return (
      <LoadingState
        label="Correction saved. Refreshing invoice review..."
        size="lg"
        className="py-24"
      />
    );
  }

  if (correctionRefreshRequired && error) {
    return (
      <ErrorState
        title="Correction saved, but review could not be refreshed"
        message="The displayed review may be out of date. Retry loading the invoice before making another decision; do not submit the correction again."
        onRetry={loadDetail}
        className="my-12"
      />
    );
  }

  if (loading && !data) {
    return (
      <LoadingState
        label="Loading invoice verification workspace..."
        size="lg"
        className="py-24"
      />
    );
  }

  if (error && !data) {
    return (
      <ErrorState message={error} onRetry={loadDetail} className="my-12" />
    );
  }

  const invoice = (data?.invoice || {}) as InvoiceDetailData['invoice'];
  const matchGates = Array.isArray(data?.match_gates) ? data.match_gates : [];
  const poSnapshot = data?.po_snapshot || null;
  const auditEvents = data?.timeline ?? data?.audit_events ?? [];
  const invoiceLines = data?.lines ?? invoice.lines ?? [];
  const isAuditor = currentUser?.role === "AUDITOR";
  const isController =
    currentUser?.role === "CONTROLLER" || currentUser?.role === "SYSTEM_ADMIN";
  const totalAmount = invoice.total_amount || 0;
  const isDualApprovalRequired = totalAmount >= dualApprovalThreshold;
  const hasFailedGates = matchGates.length < 7 || matchGates.some((g: any) => g.status !== "PASS");
  const isApproved = invoice.stage === "INTERNAL_APPROVAL_COMPLETE";
  const isPendingSecondApproval =
    invoice.workflow_substatus === "PENDING_SECOND_APPROVAL";

  // Determine Primary Action Button
  let primaryActionBtn = null;
  if (!isAuditor) {
    if (isApproved) {
      primaryActionBtn = (
        <Badge
          tone="success"
          size="lg"
          icon={<CheckCircle2 className="w-4 h-4" />}
        >
          Invoice Review Complete (Internal Sign-Off)
        </Badge>
      );
    } else if (isPendingSecondApproval) {
      if (isController) {
        primaryActionBtn = (
          <Button
            variant="primary"
            size="md"
            onClick={() => {
              setSelectedAction("APPROVE_AP_REVIEW");
              setActionReason("Second internal sign-off.");
            }}
            leftIcon={<ShieldCheck className="w-4 h-4" />}
          >
            Review Second Sign-Off
          </Button>
        );
      } else {
        primaryActionBtn = (
          <Badge tone="warning" size="md">
            Pending Financial Controller Review
          </Badge>
        );
      }
    } else if (!hasFailedGates) {
      primaryActionBtn = (
        <Button
          variant="primary"
          size="md"
          onClick={() => {
            setSelectedAction("APPROVE_AP_REVIEW");
            setActionReason("Internal AP review approved.");
          }}
          leftIcon={<CheckCircle className="w-4 h-4" />}
        >
          {isDualApprovalRequired
            ? "Review first sign-off"
            : "Review internal sign-off"}
        </Button>
      );
    } else {
      primaryActionBtn = (
        <Button
          variant="secondary"
          size="md"
          onClick={() => {
            setSelectedAction("REQUEST_SUPPLIER_CORRECTION");
            setActionReason("");
          }}
          leftIcon={<AlertTriangle className="w-4 h-4 text-amber-500" />}
        >
          Request Supplier Correction
        </Button>
      );
    }
  }

  return (
    <div className="review-page space-y-4">
      {/* 1. Header Toolbar */}
      <div className="review-header flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            leftIcon={<ArrowLeft className="w-4 h-4" />}
          >
            Back to Invoices
          </Button>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-sm sm:text-base text-slate-900 dark:text-white">
                {invoice.invoice_number || invoice.id}
              </span>
              <StatusBadge invoice={invoice} size="sm" />
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400 truncate block">
              {invoice.vendor_name || "Vendor Pending Extraction"} • Date:{" "}
              {invoice.invoice_date || "Pending"}
            </span>
          </div>
        </div>

        {/* Header Right: Grand Total & Policy Gates Trigger */}
        <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
          {hasFailedGates && (
            <Badge tone="error" size="sm" className="hidden md:inline-flex">
              Approval blocked until the failed checks are resolved
            </Badge>
          )}

          <div className="text-right">
            <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
              Billed Total
            </span>
            <span className="text-lg font-bold font-mono text-slate-900 dark:text-white tabular-nums">
              {invoice.total_amount == null
                ? "Amount unavailable"
                : formatINR(invoice.total_amount)}
            </span>
          </div>

          <div
            data-tour="policy-gates-trigger"
            className="flex flex-col items-end gap-1"
          >
            <span
              className="text-xs text-slate-600 dark:text-slate-300"
              role="status"
            >
              {summarizeCheckResults(matchGates)}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPolicyDrawerOpen(true)}
              leftIcon={<ShieldCheck className="w-3.5 h-3.5" />}
            >
              View checks
            </Button>
          </div>
        </div>
      </div>

      <InvoiceRunView key={invoiceId} invoiceId={invoiceId} onOutcome={async () => {
        try {
          const latest = await api.getInvoiceDetail(invoiceId);
          setData((previous: any) => previous?.invoice?.id === invoiceId ? latest : previous);
        }
        catch { setActionError("The processing run changed, but the invoice result could not be refreshed. Reload before taking action."); }
      }} />
      <p className="text-xs text-slate-600 dark:text-slate-300" role="note">
        Matching uses workspace procurement snapshots. Their source and freshness are not independently verified; confirm current records before deciding.
      </p>
      <section
        className="review-recorded-outcome"
        aria-label="Recorded decision and next step"
      >
        <div>
          <h2>Recorded decision</h2>
          {(invoice.job_status === "QUEUED" || invoice.job_status === "PROCESSING") && currentUser?.role && ["AP_ASSOCIATE", "AP_LEAD", "CONTROLLER", "SYSTEM_ADMIN"].includes(currentUser.role) && (
            <Button variant="outline" disabled={actionLoading} onClick={async () => {
              setActionLoading(true);
              setActionError(null);
              try {
                await api.processNextDocument();
                await loadDetail();
              } catch (err: any) {
                setActionError(err.message || "Could not resume processing. Try again.");
              } finally {
                setActionLoading(false);
              }
            }}>Resume workspace queue</Button>
          )}
          <strong>
            {invoice.decision
              ? invoice.decision.toLowerCase().replace(/_/g, " ")
              : "Decision unavailable"}
          </strong>
          {invoice.decision_reason?.startsWith("Processing failed:") ? (
            <>
              <p>
                The document could not be processed. Inspect the source and
                available check results.
              </p>
              <details>
                <summary>Technical processing details</summary>
                <p>{invoice.decision_reason}</p>
              </details>
            </>
          ) : (
            <p>
              {invoice.decision_reason ||
                "No decision reason was returned. Inspect the available checks and evidence before making a decision."}
            </p>
          )}
          <p>
            Read the original document, compare the figures and inspect named
            blockers. Processing checkpoints above show only persisted events;
            missing events do not establish completion.
          </p>
          {invoice.workflow_substatus === "SUPPLIER_CORRECTION_REQUESTED" && (
            <p>
              Supplier follow-up is recorded internally. Your team must contact
              the supplier outside this app; no correction email or
              revised-document link is created automatically.
            </p>
          )}
        </div>
        <div>
          <Button variant="outline" onClick={() => setPolicyDrawerOpen(true)}>
            Inspect all checks
          </Button>
          {isAuditor && <p>Read-only role: inspect evidence and history.</p>}
        </div>
      </section>
      {/* Success Banner */}
      {actionSuccess && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>{actionSuccess}</span>
          </div>
          <button
            onClick={() => setActionSuccess(null)}
            className="text-emerald-600 hover:text-emerald-800"
          >
            &times;
          </button>
        </div>
      )}

      {/* 2. Main 50/50 Workspace (Rossum Split Layout) */}
      <div
        data-tour="workspace-split"
        className="review-workspace grid grid-cols-1 lg:grid-cols-12 gap-5 items-start"
      >
        {/* Left Pane: Original Document Viewer (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-2">
          <Card className="review-document overflow-hidden flex flex-col h-[650px]">
            {/* Document Toolbar */}
            <div className="review-document-toolbar p-2 sm:px-3 bg-slate-50 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5 truncate">
                <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span className="truncate">Original invoice</span>
              </span>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.max(70, z - 15))}
                  className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
                  title="Zoom Out"
                  aria-label="Zoom out"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <span className="text-[10px] font-mono text-slate-500 w-9 text-center">
                  {zoomLevel}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.min(180, z + 15))}
                  className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
                  title="Zoom In"
                  aria-label="Zoom in"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
                {previewUrl && (
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
                    title="Open in new window"
                    aria-label="Open invoice in new window"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>

            {/* Document Render Area */}
            <div className="review-document-canvas flex-1 overflow-auto bg-slate-100 dark:bg-slate-950 flex items-center justify-center p-2 relative">
              {previewUrl ? (
                previewUrl.endsWith(".pdf") || previewUrl.includes(".pdf?") ? (
                  <iframe
                    src={previewUrl}
                    title="Invoice Document"
                    className="w-full h-full border-none rounded bg-white shadow-xs"
                    style={{
                      transform: `scale(${zoomLevel / 100})`,
                      transformOrigin: "top center",
                    }}
                  />
                ) : (
                  <img
                    src={previewUrl}
                    alt="Invoice scan"
                    className="max-w-full max-h-full object-contain rounded shadow-xs"
                    style={{
                      transform: `scale(${zoomLevel / 100})`,
                      transformOrigin: "top center",
                    }}
                    onError={() =>
                      setDocumentError(
                        "The document image could not be displayed. Try refreshing the link or opening it separately.",
                      )
                    }
                  />
                )
              ) : (
                <div className="text-center p-6 text-slate-400">
                  <FileText className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <span className="text-xs font-medium block">
                    Document preview unavailable
                  </span>
                  <span className="text-[11px] block mt-1">
                    No document link is available.
                  </span>
                </div>
              )}
            </div>

            <div className="review-document-help">
              <span>
                If the preview is blank or unavailable, open the document
                separately or refresh its link.
              </span>
              <div>
                {previewUrl && (
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open document
                  </a>
                )}
                {data?.document?.document_id && (
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={handleRefreshSignedUrl}
                    isLoading={refreshingDocUrl}
                  >
                    Refresh link
                  </Button>
                )}
              </div>
              {documentError && <span role="alert">{documentError}</span>}
            </div>

            {/* Document Fingerprint Footer */}
            {Boolean(data?.document && (data.document.sha256 || data.document.sha256_hash)) && (
              <div className="review-document-hash p-2 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span
                  className="truncate max-w-[200px]"
                  title={(data?.document?.sha256 || data?.document?.sha256_hash) ?? ""}
                >
                  SHA:{" "}
                  {((data?.document?.sha256 || data?.document?.sha256_hash) ?? "").slice(
                    0,
                    16,
                  )}
                  ...
                </span>
                <button
                  type="button"
                  onClick={() =>
                    handleCopySha(
                      (data?.document?.sha256 || data?.document?.sha256_hash) ?? "",
                    )
                  }
                  className="flex items-center gap-1 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                >
                  {copiedSha ? (
                    <Check className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>{copiedSha ? "Copied" : "Copy"}</span>
                </button>
              </div>
            )}
          </Card>
        </div>

        {/* Right Pane: Structured Verification & Reconciliation (7 cols on lg) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Verdict Strip */}
          <CaseSummaryCard
            invoice={invoice}
            matchGates={matchGates}
            userRole={currentUser?.role}
            policy={{
              dual_approval_threshold_inr: dualApprovalThreshold,
              rate_tolerance_percent: rateTolerancePercent,
              rounding_tolerance_inr:
                data?.policy?.rounding_tolerance_inr ||
                DEFAULT_POLICY.rounding_tolerance_inr,
            }}
            onOpenGlossary={openGlossaryWithTerm}
            onOpenPolicyDrawer={() => setPolicyDrawerOpen(true)}
          />

          {/* Tab Navigation: Line Matching vs History */}
          <div className="review-tabs flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-1">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("reconciliation")}
                aria-pressed={activeTab === "reconciliation"}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                  activeTab === "reconciliation"
                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                Compare line items ({invoiceLines.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("history")}
                aria-pressed={activeTab === "history"}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                  activeTab === "history"
                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                Audit Trail ({auditEvents.length})
              </button>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-400 hidden sm:inline">
                Verified by automatic checks • Verification Status
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => openGlossaryWithTerm()}
                className="text-slate-500"
              >
                Glossary
              </Button>
            </div>
          </div>

          {/* Tab Content 1: 4-Way Reconciliation Table */}
          {activeTab === "reconciliation" && (
            <div data-tour="reconciliation-flow" className="space-y-4">
              <ProcurementVerificationFlow
                invoice={invoice}
                lines={invoiceLines}
                poSnapshot={poSnapshot}
                rateTolerancePercent={rateTolerancePercent}
                onOpenGlossary={openGlossaryWithTerm}
                onCorrectLine={handleCorrectLine}
                isAuditor={isAuditor}
              />
            </div>
          )}

          {/* Tab Content 2: Immutable Audit Trail */}
          {activeTab === "history" && (
            <Card>
              <CardHeader>
                <CardTitle>Invoice Activity & Audit Log</CardTitle>
                <CardDescription>
                  Chronological record of OCR extraction, policy checks,
                  corrections, and approvals.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {auditEvents.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">
                    No recorded events for this invoice yet.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                    {auditEvents.map((event: any) => (
                      <div
                        key={event.event_id || event.id}
                        className="review-audit-event p-3.5 flex items-start justify-between gap-3"
                      >
                        <div className="space-y-0.5">
                          <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                            {event.description ||
                              event.action?.replace(/_/g, " ")}
                          </span>
                          {event.reason && <p>{event.reason}</p>}
                          <div className="flex items-center gap-2 text-[11px] text-slate-400">
                            <span>
                              Actor: {event.actor_name || event.actor_id}
                            </span>
                            <span>•</span>
                            <span className="font-mono">
                              {new Date(event.timestamp).toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <Badge tone="neutral" size="sm">
                          {event.action}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Sticky Decision & Action Footer */}
          {!isAuditor && (
            <Card className="review-decision sticky bottom-3 shadow-lg border-indigo-200/80 dark:border-indigo-900/50 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md">
              <div className="p-3.5 flex items-center justify-between gap-3">
                <div className="text-xs text-slate-500 hidden sm:block">
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    Next action:
                  </span>{" "}
                  Inspect the evidence before recording an internal decision.
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  {/* Secondary Actions Dropdown Trigger */}
                  <div className="relative">
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => setActionsMenuOpen(!actionsMenuOpen)}
                      aria-expanded={actionsMenuOpen}
                      rightIcon={<MoreVertical className="w-3.5 h-3.5" />}
                    >
                      Other Actions
                    </Button>

                    {actionsMenuOpen && (
                      <div
                        className="absolute right-0 bottom-full mb-2 w-56 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl py-1 z-30 text-xs"
                        onMouseLeave={() => setActionsMenuOpen(false)}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setActionsMenuOpen(false);
                            setSelectedAction("HOLD_PENDING_EVIDENCE");
                            setActionReason("");
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        >
                          Hold Pending Evidence
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActionsMenuOpen(false);
                            setSelectedAction("REQUEST_SUPPLIER_CORRECTION");
                            setActionReason("");
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        >
                          Request Supplier Correction
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActionsMenuOpen(false);
                            setSelectedAction("RAISE_DEBIT_NOTE");
                            setActionReason("");
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                        >
                          Raise Debit Note
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActionsMenuOpen(false);
                            setSelectedAction("QUARANTINE");
                            setActionReason("");
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-purple-700 dark:text-purple-300"
                        >
                          Set Aside (Quarantine Non-Invoice)
                        </button>
                        <div className="border-t border-slate-100 dark:border-slate-800 my-1" />
                        <button
                          type="button"
                          onClick={() => {
                            setActionsMenuOpen(false);
                            setSelectedAction("REJECT_INVOICE");
                            setActionReason("");
                          }}
                          className="w-full text-left px-3.5 py-2 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-700 dark:text-rose-400 font-semibold"
                        >
                          Reject Invoice
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Primary Action Button */}
                  {primaryActionBtn}
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Slide-Over Drawer: Policy Validation Gates */}
      <Drawer
        isOpen={policyDrawerOpen}
        onClose={() => setPolicyDrawerOpen(false)}
        title={
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>All invoice checks & evidence</span>
          </div>
        }
        description="Checks compare the invoice with available order, receipt and inspection records. A failed check needs attention; unavailable or not evaluated does not mean passed."
        width="xl"
        className="policy-checks-drawer"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-1">
            <span className="font-semibold block text-slate-800 dark:text-slate-200">
              Procurement System Truth & Provenance
            </span>
            <p>
              Evaluated against authoritative procurement reference snapshots.
              Live SAP S/4HANA synchronization is not configured.
            </p>
            <p className="text-[11px] font-mono text-slate-500">
              {`Allowed price variance: ±${rateTolerancePercent.toFixed(2)}% | Strict 0.00% quantity tolerance.`}
            </p>
          </div>

          <PolicyChecksGrouped
            matchGates={matchGates}
            onOpenGlossary={openGlossaryWithTerm}
          />
        </div>
      </Drawer>

      {/* Action Consequence Modal */}
      {selectedAction && (
        <ConsequenceAwareActionModal
          isOpen={Boolean(selectedAction)}
          onClose={() => {
            setSelectedAction(null);
            setActionError(null);
          }}
          onConfirm={handleExecuteAction}
          action={selectedAction}
          invoice={invoice}
          hasFailedGates={hasFailedGates}
          reason={actionReason}
          onReasonChange={setActionReason}
          isLoading={actionLoading}
          errorMessage={actionError}
          policy={{
            dual_approval_threshold_inr: dualApprovalThreshold,
            rate_tolerance_percent: rateTolerancePercent,
            rounding_tolerance_inr:
              data?.policy?.rounding_tolerance_inr ||
              DEFAULT_POLICY.rounding_tolerance_inr,
          }}
        />
      )}

      {/* Glossary Modal */}
      <GlossaryModal
        isOpen={showGlossary}
        onClose={() => setShowGlossary(false)}
        initialTerm={glossaryTerm}
      />
    </div>
  );
};
