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
  RefreshCw,
  RotateCcw,
  Trash2,
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
  CardContent,
  Button,
  Badge,
  Drawer,
  Modal,
  LoadingState,
  ErrorState,
} from "../components/ui";
import { ExtractedDataCard } from "../components/ExtractedDataCard";
import { BlockingDiscrepanciesCard } from "../components/BlockingDiscrepanciesCard";
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

  // Document Operational Actions State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const [deletingDoc, setDeletingDoc] = useState(false);
  const [retryingProcessing, setRetryingProcessing] = useState(false);

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

  const rawThreshold =
    data?.policy?.dual_approval_threshold_inr ??
    data?.approval?.threshold_inr ??
    DEFAULT_POLICY.dual_approval_threshold_inr;
  const dualApprovalThreshold = Number.isFinite(Number(rawThreshold))
    ? Number(rawThreshold)
    : 500000;

  const rawTolerance =
    data?.policy?.rate_tolerance_percent ??
    DEFAULT_POLICY.rate_tolerance_percent;
  const rateTolerancePercent = Number.isFinite(Number(rawTolerance))
    ? Number(rawTolerance)
    : 1.5;

  // Always reset drawer state when switching invoices
  useEffect(() => {
    setPolicyDrawerOpen(false);
  }, [invoiceId]);

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

  const handleRetryProcessing = async () => {
    setRetryingProcessing(true);
    setActionError(null);
    try {
      await api.processNextDocument();
      await loadDetail();
      setActionSuccess("Processing job triggered for this document.");
    } catch (err: any) {
      setActionError(err.message || "Failed to trigger retry for document processing.");
    } finally {
      setRetryingProcessing(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!data?.document?.document_id) return;
    setDeletingDoc(true);
    try {
      await api.softDeleteDocument(
        data.document.document_id,
        deleteReason || "Operator requested deletion from invoice detail."
      );
      setShowDeleteModal(false);
      onBack();
    } catch (err: any) {
      setActionError(err.message || "Could not delete document.");
      setShowDeleteModal(false);
    } finally {
      setDeletingDoc(false);
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
  const canRetry = Boolean(
    !isAuditor &&
      (invoice.job_status === "QUEUED" ||
        invoice.job_status === "PROCESSING" ||
        invoice.job_status === "FAILED" ||
        invoice.decision === "FLAGGED_EXCEPTION" ||
        invoice.decision === "FLAGGED_HITL_REVIEW")
  );
  const canDelete = Boolean(!isAuditor && data?.document?.document_id);
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

      {/* 2. Compact Status Summary (Collapsed by default for completed/held/rejected invoices) */}
      <InvoiceRunView
        key={invoiceId}
        invoiceId={invoiceId}
        invoiceStage={invoice.stage}
        invoiceDecision={invoice.decision}
        onOutcome={async () => {
          try {
            const latest = await api.getInvoiceDetail(invoiceId);
            setData((previous: any) => previous?.invoice?.id === invoiceId ? latest : previous);
          }
          catch { setActionError("The processing run changed, but the invoice result could not be refreshed. Reload before taking action."); }
        }}
      />

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

      {/* 3. Balanced Two-Column Workspace (Sticky PDF + Review Hierarchy) */}
      <div
        data-tour="workspace-split"
        className="review-workspace grid grid-cols-1 lg:grid-cols-12 gap-5 items-start"
      >
        {/* Left Pane: Persistent Original Document Viewer (~42% desktop width) */}
        <div className="lg:col-span-5 xl:col-span-5 review-document-sticky sticky top-4 self-start flex flex-col h-[calc(100vh-140px)] min-h-[620px] max-h-[920px]">
          <Card className="review-document overflow-hidden flex flex-col h-full border border-slate-200 dark:border-slate-800 shadow-2xs">
            {/* Document Toolbar */}
            <div className="review-document-toolbar p-2 sm:px-3 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs shrink-0">
              <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5 truncate">
                <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span className="truncate">Original invoice</span>
              </span>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.max(70, z - 15))}
                  className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 cursor-pointer"
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
                  className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 cursor-pointer"
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
                    className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 cursor-pointer"
                    title="Open in new window"
                    aria-label="Open invoice in new window"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>

            {/* Document Render Canvas: fills available viewport height */}
            <div className="review-document-canvas flex-1 min-h-0 overflow-auto bg-slate-100 dark:bg-slate-950 flex items-center justify-center p-2 relative">
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

            {/* Sleek Document Footer */}
            <div className="review-document-footer p-2 px-3 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                {Boolean(data?.document && (data.document.sha256 || data.document.sha256_hash)) && (
                  <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-400">
                    <span
                      className="truncate max-w-[130px]"
                      title={(data?.document?.sha256 || data?.document?.sha256_hash) ?? ""}
                    >
                      SHA: {((data?.document?.sha256 || data?.document?.sha256_hash) ?? "").slice(0, 12)}...
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        handleCopySha(
                          (data?.document?.sha256 || data?.document?.sha256_hash) ?? "",
                        )
                      }
                      className="hover:text-slate-600 dark:hover:text-slate-200 p-0.5 cursor-pointer"
                      title="Copy full SHA-256 fingerprint"
                    >
                      {copiedSha ? (
                        <Check className="w-3 h-3 text-emerald-500" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2.5 shrink-0">
                {previewUrl && (
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 font-medium text-[11px]"
                  >
                    <span>Open document</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {data?.document?.document_id && (
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={handleRefreshSignedUrl}
                    isLoading={refreshingDocUrl}
                    className="text-[10.5px] h-6 px-1.5 text-slate-500"
                  >
                    Refresh link
                  </Button>
                )}
              </div>
            </div>

            {documentError && (
              <div className="p-2 bg-rose-50 dark:bg-rose-950/40 border-t border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between" role="alert">
                <span>{documentError}</span>
                <button onClick={() => setDocumentError(null)} className="text-rose-600 hover:text-rose-800 text-sm font-bold">&times;</button>
              </div>
            )}
          </Card>

          {/* Context-Sensitive Operational Document Controls Row */}
          <div className="mt-2.5 p-2 px-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex items-center justify-between gap-2 text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px] truncate">
              Document Controls:
            </span>

            <div className="flex items-center gap-1.5 flex-wrap justify-end">
              <Button
                variant="outline"
                size="xs"
                onClick={loadDetail}
                isLoading={loading}
                leftIcon={<RefreshCw className="w-3 h-3" />}
                title="Refresh complete invoice state and extraction"
              >
                Refresh
              </Button>

              {previewUrl && (
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => window.open(previewUrl, "_blank")}
                  leftIcon={<ExternalLink className="w-3 h-3" />}
                  title="Open original document in new window"
                >
                  Open
                </Button>
              )}

              {canRetry && (
                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleRetryProcessing}
                  isLoading={retryingProcessing}
                  leftIcon={<RotateCcw className="w-3 h-3 text-amber-500" />}
                  className="text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800"
                  title="Retry or resume extraction pipeline for this invoice"
                >
                  Retry Run
                </Button>
              )}

              {canDelete && (
                <Button
                  variant="danger"
                  size="xs"
                  onClick={() => setShowDeleteModal(true)}
                  leftIcon={<Trash2 className="w-3 h-3" />}
                  title="Soft delete document"
                >
                  Delete
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Right Pane: Scrollable Invoice Review Workspace (~58% desktop width) */}
        <div className="lg:col-span-7 xl:col-span-7 space-y-4">
          {/* Top Full-Width Verification Overview & All Seven Policy Gates */}
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
            hideDiscrepancyList={true}
          />

          {/* Directly Below: Two Side-by-Side Subcolumns (Extracted Data on Left, Blocking Issues on Right) */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-stretch">
            {/* Left Subcolumn (~50-55%): Extracted Document Data */}
            <div className="xl:col-span-6 flex flex-col">
              <ExtractedDataCard
                invoice={invoice}
                extractedFields={data?.extracted_fields}
                lines={invoiceLines}
                poSnapshot={poSnapshot}
              />
            </div>

            {/* Right Subcolumn (~45-50%): Blocking Discrepancies */}
            <div className="xl:col-span-6 flex flex-col">
              <BlockingDiscrepanciesCard
                invoice={invoice}
                matchGates={matchGates}
                hasFailedGates={hasFailedGates}
                onOpenPolicyDrawer={() => setPolicyDrawerOpen(true)}
              />
            </div>
          </div>

          {/* Step 2: Line-by-Line Invoice vs PO Comparison & Procurement Evidence */}
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

          {/* Step 3: Unified Decision, Discrepancy Context & Operator Actions */}
          <Card className="review-decision-card border border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 rounded-xl overflow-hidden">
            {/* Verdict Header */}
            <div className="p-4 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    Recorded Decision Verdict
                  </span>
                  <Badge
                    tone={
                      invoice.decision === "INTERNAL_APPROVAL_COMPLETE"
                        ? "success"
                        : hasFailedGates
                        ? "error"
                        : "warning"
                    }
                    size="sm"
                    className="font-bold"
                  >
                    {invoice.decision
                      ? invoice.decision.replace(/_/g, " ")
                      : "DECISION PENDING"}
                  </Badge>
                  {isDualApprovalRequired && (
                    <Badge tone="purple" size="sm">
                      Dual approval ≥ {formatINR(dualApprovalThreshold)}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-800 dark:text-slate-200 font-medium">
                  {invoice.decision_reason ||
                    "Read the original document, compare the figures and inspect named records before recording an internal decision."}
                </p>
              </div>

              {(invoice.job_status === "QUEUED" ||
                invoice.job_status === "PROCESSING") &&
                currentUser?.role &&
                [
                  "AP_ASSOCIATE",
                  "AP_LEAD",
                  "CONTROLLER",
                  "SYSTEM_ADMIN",
                ].includes(currentUser.role) && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={actionLoading}
                    onClick={async () => {
                      setActionLoading(true);
                      setActionError(null);
                      try {
                        await api.processNextDocument();
                        await loadDetail();
                      } catch (err: any) {
                        setActionError(
                          err.message ||
                            "Could not resume processing. Try again.",
                        );
                      } finally {
                        setActionLoading(false);
                      }
                    }}
                  >
                    Resume workspace queue
                  </Button>
                )}
            </div>

            {/* Explanations & Truth Disclosures */}
            <div className="p-4 space-y-2.5 text-xs text-slate-600 dark:text-slate-300 border-b border-slate-200/60 dark:border-slate-800/60">
              {invoice.workflow_substatus === "SUPPLIER_CORRECTION_REQUESTED" && (
                <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200">
                  <strong>Supplier follow-up recorded internally:</strong> Your
                  team must contact the supplier outside this app; no correction
                  email or revised-document link is created automatically.
                </div>
              )}

              <p className="text-[11.5px] text-slate-500 dark:text-slate-400 leading-relaxed">
                Evaluated against authoritative procurement reference snapshots. Live SAP S/4HANA synchronization is not configured. Processing checkpoints above show only persisted events; missing events do not establish completion. Read the original document, compare the figures and inspect named records before recording an internal decision.
              </p>
            </div>

            {/* Operator Actions Bar */}
            {!isAuditor ? (
              <div className="p-3.5 bg-white dark:bg-slate-900 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="text-xs text-slate-500 hidden sm:block">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Next Action:
                  </span>{" "}
                  Choose an action based on verified evidence.
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  {/* Secondary Actions Dropdown */}
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
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 cursor-pointer"
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
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 cursor-pointer"
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
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 cursor-pointer"
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
                          className="w-full text-left px-3.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 text-purple-700 dark:text-purple-300 cursor-pointer"
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
                          className="w-full text-left px-3.5 py-2 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-700 dark:text-rose-400 font-semibold cursor-pointer"
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
            ) : (
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950 text-xs text-slate-500">
                Read-only role: inspect evidence and history.
              </div>
            )}
          </Card>

          {/* Step 4: Collapsible Audit Trail & Activity Log */}
          <Card className="border border-slate-200 dark:border-slate-800 shadow-2xs rounded-xl overflow-hidden">
            <div className="p-3.5 bg-slate-50/70 dark:bg-slate-850 flex items-center justify-between gap-2 border-b border-slate-200/60 dark:border-slate-800/60">
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-slate-800 dark:text-slate-200">
                  Invoice Activity & Audit Log ({auditEvents.length} events)
                </span>
                <span className="text-[11px] text-slate-400 hidden sm:inline">
                  • Verified by automatic checks • Verification Status
                </span>
              </div>
              <Button
                variant="ghost"
                size="xs"
                onClick={() =>
                  setActiveTab(
                    activeTab === "history" ? "reconciliation" : "history",
                  )
                }
                className="text-xs cursor-pointer"
              >
                {activeTab === "history" ? "Collapse Audit Trail" : "View Audit Trail"}
              </Button>
            </div>

            {activeTab === "history" && (
              <CardContent className="p-0">
                {auditEvents.length === 0 ? (
                  <div className="text-center py-6 text-xs text-slate-400">
                    No recorded events for this invoice yet.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs max-h-80 overflow-auto">
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
            )}
          </Card>
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

      {/* Delete Document Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Confirm Document Deletion"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
            Are you sure you want to delete invoice document{" "}
            <strong className="text-slate-900 dark:text-white">
              {data?.document?.filename || invoice.invoice_number || "this document"}
            </strong>
            ? This will soft-delete the document file while preserving immutable audit logs.
          </p>
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Reason for deletion (optional):
            </label>
            <input
              type="text"
              value={deleteReason}
              onChange={(e) => setDeleteReason(e.target.value)}
              placeholder="e.g. Duplicate scan, superseded by vendor..."
              className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-xs"
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeleteModal(false)}
              disabled={deletingDoc}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleConfirmDelete}
              isLoading={deletingDoc}
            >
              Confirm Soft Delete
            </Button>
          </div>
        </div>
      </Modal>

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
