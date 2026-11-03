import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  ArrowLeft, 
  FileText, 
  ShieldCheck, 
  ExternalLink,
  Layers,
  RefreshCw,
  Download,
  Copy,
  Check,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Info,
  ShieldAlert,
  Lock,
  Compass,
  BookOpen
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { DEFAULT_POLICY } from '../content/policy';
import { GlossaryModal } from '../components/GlossaryModal';
import { CaseSummaryCard } from '../components/CaseSummaryCard';
import { ProcurementVerificationFlow } from '../components/ProcurementVerificationFlow';
import { PolicyChecksGrouped } from '../components/PolicyChecksGrouped';
import { ConsequenceAwareActionModal } from '../components/ConsequenceAwareActionModal';
import type { AuthenticatedUser } from '../types';

interface InvoiceDetailPageProps {
  invoiceId: string;
  onBack: () => void;
  currentUser?: AuthenticatedUser | null;
}

type TabType = 'matching' | 'checks' | 'details' | 'history';

const formatINR = (val?: number | null) => {
  if (val === undefined || val === null) return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(val);
};

export const InvoiceDetailPage: React.FC<InvoiceDetailPageProps> = ({ 
  invoiceId, 
  onBack,
  currentUser 
}) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Navigation & Tabs
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabType>('matching');
  const [workspaceLayout, setWorkspaceLayout] = useState<'split' | 'analysis_focus' | 'doc_focus'>('split');
  
  // Document Viewer State
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [copiedSha, setCopiedSha] = useState(false);
  const [refreshingDocUrl, setRefreshingDocUrl] = useState(false);

  // Decision & Action State
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Glossary Modal State
  const [showGlossary, setShowGlossary] = useState(false);
  const [glossaryTerm, setGlossaryTerm] = useState<string | undefined>(undefined);

  const openGlossaryWithTerm = (term?: string) => {
    setGlossaryTerm(term);
    setShowGlossary(true);
  };

  // Policy & Threshold Resolution
  const dualApprovalThreshold = data?.policy?.dual_approval_threshold_inr || data?.approval?.threshold_inr || DEFAULT_POLICY.dual_approval_threshold_inr;
  const rateTolerancePercent = data?.policy?.rate_tolerance_percent || DEFAULT_POLICY.rate_tolerance_percent;

  // Guided Review Tour State (6 coachmarks)
  const [showTour, setShowTour] = useState(false);
  const [tourStep, setTourStep] = useState(1);

  const tourSteps = [
    {
      step: 1,
      title: 'Original Document Pane',
      description: 'Inspect the uploaded invoice PDF with pan/zoom controls, page navigation, and on-demand 300s presigned URL refreshing for zero-trust document security.',
      onEnter: () => setZoomLevel(100),
    },
    {
      step: 2,
      title: 'Extracted Information',
      description: 'Review invoice information read by AI: Vendor Name, GSTIN, invoice date, amounts, and tax breakdowns, verified before matching against records.',
      onEnter: () => setActiveTab('details'),
    },
    {
      step: 3,
      title: 'Authoritative PO & GRN Match',
      description: `Cross-reference invoice line items against authoritative procurement reference snapshots with strict 0.00% quantity and ±${rateTolerancePercent.toFixed(2)}% price variance thresholds.`,
      onEnter: () => setActiveTab('matching'),
    },
    {
      step: 4,
      title: 'Policy Validation Checks',
      description: 'Audit the 7 policy validation checks. When checks fail, approvals are strictly blocked until exceptions are triaged or resolved.',
      onEnter: () => setActiveTab('checks'),
    },
    {
      step: 5,
      title: 'Dual Approval & Audit Trail',
      description: `Track the complete append-only audit trail. Invoices exceeding ${formatINR(dualApprovalThreshold)} enforce dual approval where two distinct approvers sign off before completion.`,
      onEnter: () => setActiveTab('history'),
    },
    {
      step: 6,
      title: 'Authorized AP Triage Actions',
      description: 'Execute authorized AP actions: Hold Pending Evidence, Request Supplier Correction, Raise Debit Note, Escalate, or Reject with mandatory audit justification.',
      onEnter: () => {},
    },
  ];

  const loadDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getInvoiceDetail(invoiceId);
      setData(res);
      setPreviewUrl(res.document?.preview_url || null);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve invoice detail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [invoiceId]);

  useEffect(() => {
    if (searchParams.get('tour') === 'true') {
      setShowTour(true);
      setTourStep(1);
      tourSteps[0].onEnter();
    }
  }, [searchParams]);

  // Review Workspace Ergonomic Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          handleExecuteAction();
        }
        if (e.key === 'Escape') {
          setSelectedAction(null);
          setActionError(null);
        }
        return;
      }

      if (e.ctrlKey || e.metaKey || e.altKey) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          handleExecuteAction();
        }
        return;
      }

      if (e.key === 'Escape') {
        setSelectedAction(null);
        setActionError(null);
        setShowTour(false);
      } else if (e.key === '1') {
        setActiveTab('matching');
      } else if (e.key === '2') {
        setActiveTab('checks');
      } else if (e.key === '3') {
        setActiveTab('details');
      } else if (e.key === '4') {
        setActiveTab('history');
      } else if (e.key.toLowerCase() === 'd') {
        setZoomLevel((prev) => (prev === 100 ? 130 : 100));
      } else if (e.key.toLowerCase() === 'a' && currentUser?.role !== 'AUDITOR' && (!data?.match_gates?.some((g: any) => g.status === 'FAIL'))) {
        setSelectedAction('APPROVE_AP_REVIEW');
        setActionReason('');
      } else if (e.key.toLowerCase() === 'h' && currentUser?.role !== 'AUDITOR') {
        setSelectedAction('HOLD_PENDING_EVIDENCE');
        setActionReason('');
      } else if (e.key.toLowerCase() === 'c' && currentUser?.role !== 'AUDITOR') {
        setSelectedAction('REQUEST_SUPPLIER_CORRECTION');
        setActionReason('');
      } else if (e.key.toLowerCase() === 's' && currentUser?.role !== 'AUDITOR') {
        setSelectedAction('QUARANTINE');
        setActionReason('');
      } else if (e.key.toLowerCase() === 'r' && currentUser?.role !== 'AUDITOR') {
        setSelectedAction('REJECT_INVOICE');
        setActionReason('');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentUser, data, selectedAction, actionReason]);

  const handleRefreshSignedUrl = async () => {
    if (!data?.document?.document_id) return;
    setRefreshingDocUrl(true);
    try {
      // Refresh pre-signed URL with 300s TTL (statutory max)
      const res = await api.getDocumentSignedUrl(data.document.document_id, 300);
      setPreviewUrl(res.signed_url);
    } catch (err: any) {
      console.error('Failed to refresh document signed URL:', err);
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
      setActionError('Operational justification reason must be at least 3 characters.');
      return;
    }

    // Strict validation check: Prevent approval if any policy check failed
    const hasFailedGate = data?.match_gates?.some((g: any) => g.status === 'FAIL');
    if (selectedAction === 'APPROVE_AP_REVIEW' && hasFailedGate) {
      setActionError('Approval blocked: this invoice failed policy validation checks. Policy overrides are disabled. Please triage via Hold, Ask Supplier to Correct, Debit Note, Escalate, Reject, or Quarantine.');
      return;
    }

    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await api.executeAction(invoiceId, selectedAction, actionReason.trim());
      const actionHumanNames: Record<string, string> = {
        APPROVE_AP_REVIEW: 'Internal AP approval recorded',
        HOLD_PENDING_EVIDENCE: 'Invoice placed on hold pending evidence',
        REQUEST_SUPPLIER_CORRECTION: 'Correction request logged for supplier',
        RAISE_DEBIT_NOTE: 'Debit note draft generated',
        ESCALATE: 'Escalation notification dispatched',
        REJECT_INVOICE: 'Invoice formally rejected by AP',
        QUARANTINE: 'Document quarantined for security review',
      };
      const toastMsg = actionHumanNames[selectedAction] || `Action '${selectedAction}' recorded`;
      setActionSuccess(`${toastMsg} successfully.`);
      setSelectedAction(null);
      setActionReason('');
      await loadDetail();
    } catch (err: any) {
      setActionError(err.message || 'Action execution failed.');
    } finally {
      setActionLoading(false);
    }
  };

  // Helper mapping gate names to human language
  const humanGateName = (rawName: string) => {
    const map: Record<string, string> = {
      'Vendor Identity Registered': 'Supplier is registered and verified',
      'PO Authorization Valid': 'Purchase order found and valid',
      'GRN Receipt Confirmed': 'Goods receipt (GRN) confirmed in ERP',
      'QC Inspection Accepted': 'Quality inspection (QC) accepted',
      'GST Arithmetic Reconciled': 'GST tax adds up mathematically',
      'PO Price & Quantity Tolerance': 'Price and quantity match the PO (±1.5%)',
      'Duplicate Invoice Check': 'Not a duplicate submission',
    };
    return map[rawName] || rawName;
  };

  // Helper providing actionable operational next steps for failed validation checks
  const getRequiredNextAction = (rawName: string): string => {
    switch (rawName) {
      case 'Vendor Identity Registered':
        return 'Verify supplier GSTIN/PAN against master reference data, or request supplier onboarding.';
      case 'PO Authorization Valid':
        return 'Verify purchase order validity and remaining balance, or request procurement amendment.';
      case 'GRN Receipt Confirmed':
        return 'Confirm delivery with warehouse receiving dock, or place invoice on Hold for Evidence.';
      case 'QC Inspection Accepted':
        return 'Obtain QC release certificate from warehouse, or place invoice on Hold for Evidence.';
      case 'GST Arithmetic Reconciled':
        return 'Request corrected tax invoice from supplier with reconciled statutory GST schedules.';
      case 'PO Price & Quantity Tolerance':
        return 'Contact supplier to amend billed price/quantity (±1.5% tolerance exceeded), or raise debit note.';
      case 'Duplicate Invoice Check':
        return 'Investigate prior invoice submission. If confirmed duplicate, execute Set Aside (Quarantine).';
      default:
        return 'Review discrepancy details and triage via Hold, Supplier Correction, or Quarantine.';
    }
  };

  // Reason templates based on selected action
  const getReasonTemplates = (action: string): string[] => {
    switch (action) {
      case 'APPROVE_AP_REVIEW':
        return [
          'All 7 policy checks verified against original PDF document.',
          'Variance within agreed commercial tolerance; approved for processing.',
          'Goods receipt and inspection certificate cross-referenced and confirmed.'
        ];
      case 'HOLD_PENDING_EVIDENCE':
        return [
          `Awaiting goods receipt note (GRN) from warehouse for PO ${data?.invoice?.po_reference || ''}.`,
          'Awaiting quality inspection (QC) release certificate.',
          'Purchase order balance exhausted; awaiting procurement amendment.'
        ];
      case 'REQUEST_SUPPLIER_CORRECTION':
        return [
          'Billed unit rate exceeds agreed PO contract rate; requesting amended invoice.',
          'GST calculation does not reconcile with statutory GSTIN rate schedule.',
          'Invoice missing mandatory purchase order reference number.'
        ];
      case 'RAISE_DEBIT_NOTE':
        return [
          'Excess quantity billed over verified GRN; debit note initiated for quantity discrepancy.',
          'Unit rate discrepancy exceeds tolerance; debit note raised for differential.'
        ];
      case 'ESCALATE':
        return [
          'Commercial price variance escalated to Head of Procurement for sign-off.',
          'Recurring supplier invoice discrepancy escalated to Financial Controller.'
        ];
      case 'REJECT_INVOICE':
        return [
          'Duplicate invoice submission with identical cryptographic hash.',
          'Invalid or unauthorized purchase order reference cited on document.'
        ];
      case 'QUARANTINE':
        return [
          'Payment receipt or commercial statement, not a payable vendor invoice.',
          'Illegible or corrupted scan; unresolvable extraction failure.'
        ];
      default:
        return [];
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-16 text-center text-slate-500 dark:text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-indigo-600 dark:text-indigo-400" />
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Retrieving authoritative invoice workspace...</p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Inspecting document storage, 7-gate validation state & audit events</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/20 p-8 text-center text-xs space-y-3">
        <AlertTriangle className="w-8 h-8 mx-auto text-red-600 dark:text-red-400" />
        <h2 className="text-sm font-bold text-red-900 dark:text-red-300">{error || 'Invoice not found.'}</h2>
        <p className="text-red-700 dark:text-red-400 max-w-md mx-auto">
          The requested invoice could not be found or you do not have permission to access it in this organization.
        </p>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 transition-colors shadow-2xs"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to Invoices
        </button>
      </div>
    );
  }

  const { invoice, document, extracted_fields, lines, match_gates, approval, timeline } = data;

  // Determine gate pass/fail statistics
  const isUnreadable = Boolean(
    invoice?.decision === 'FLAGGED_HITL_REVIEW' && (
      !invoice?.invoice_number ||
      invoice?.invoice_number === 'UNKNOWN' ||
      invoice?.invoice_number.startsWith('SCAN-') ||
      invoice?.vendor_name === 'Unidentified Supplier' ||
      invoice?.vendor_name === 'Unknown' ||
      (invoice?.total_amount === 0 && !invoice?.po_reference)
    )
  );
  const totalGates = match_gates?.length || 0;
  const passedGates = match_gates?.filter((g: any) => g.status === 'PASS').length || 0;
  const notEvaluatedGates = match_gates?.filter((g: any) => g.status === 'NOT_EVALUATED' || g.status === 'UNKNOWN').length || 0;
  const failedGates = match_gates?.filter((g: any) => g.status === 'FAIL') || [];

  const isAuditor = currentUser?.role === 'AUDITOR';
  const isApproved = invoice.stage === 'INTERNAL_APPROVAL_COMPLETE' || invoice.decision === 'AUTO_APPROVED' || invoice.decision === 'MANUALLY_APPROVED';
  const isPendingSecondApproval = invoice.workflow_substatus === 'PENDING_SECOND_APPROVAL' || approval?.status === 'PENDING_SECOND_APPROVAL';

  return (
    <div className="space-y-3 pb-48 sm:pb-32 lg:pb-24">
      {/* 1. Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            title="Return to Invoices list"
            className="p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white font-mono">
                {invoice.invoice_number || invoice.id}
              </h1>
              <StatusBadge invoice={invoice} size="sm" />
              {isPendingSecondApproval && (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                  Dual Control Active
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 flex flex-wrap items-center gap-x-2">
              <span>Supplier: <strong className="text-slate-700 dark:text-slate-200 font-medium">{invoice.vendor_name || 'Unregistered'}</strong></span>
              {invoice.vendor_gstin && <span>• <span className="font-mono">{invoice.vendor_gstin}</span></span>}
              {invoice.po_reference && <span>• PO: <span className="font-mono">{invoice.po_reference}</span></span>}
            </div>
          </div>
        </div>

        {/* Header Right: Amount & Statutory Due */}
        <div className="flex items-center gap-2 sm:gap-3 sm:text-right shrink-0">
          <button
            onClick={() => openGlossaryWithTerm()}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium transition-colors shadow-2xs"
            title="Open Accounts Payable Terminology Glossary"
          >
            <BookOpen className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span className="hidden sm:inline">Glossary</span>
          </button>
          <button
            onClick={() => {
              setShowTour(true);
              setTourStep(1);
              tourSteps[0].onEnter();
            }}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-800/80 bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 text-xs font-medium transition-colors shadow-2xs"
            title="Start Guided AP Review Tour"
          >
            <Compass className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Tour</span>
          </button>
          <div>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-white tabular-nums">
              {formatINR(invoice.total_amount)}
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400">
              {invoice.msme_statutory_deadline ? (
                <span className="inline-flex items-center gap-1 font-medium text-rose-600 dark:text-rose-400">
                  <Clock className="w-3 h-3" />
                  Due: {invoice.msme_statutory_deadline.substring(0, 10)}
                </span>
              ) : (
                'Total Billed Amount'
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Guided Review Tour Coachmark Banner */}
      {showTour && (
        <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50/90 dark:bg-indigo-950/60 shadow-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
              {tourStep}/6
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">
                  Guided AP Workspace Tour • Step {tourStep} of 6
                </span>
                <span className="text-[10px] text-slate-500 font-mono">(Esc to exit)</span>
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                {tourSteps[tourStep - 1].title}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 max-w-2xl leading-relaxed">
                {tourSteps[tourStep - 1].description}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            {tourStep > 1 && (
              <button
                onClick={() => {
                  const prev = tourStep - 1;
                  setTourStep(prev);
                  tourSteps[prev - 1].onEnter();
                }}
                className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 transition-colors shadow-2xs"
              >
                Previous
              </button>
            )}
            {tourStep < 6 ? (
              <button
                onClick={() => {
                  const next = tourStep + 1;
                  setTourStep(next);
                  tourSteps[next - 1].onEnter();
                }}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-colors shadow-xs"
              >
                Next Step &rarr;
              </button>
            ) : (
              <button
                onClick={() => {
                  setShowTour(false);
                  localStorage.setItem('ap.workspace_tour.completed', 'true');
                }}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition-colors shadow-xs"
              >
                Finish Tour &check;
              </button>
            )}
            <button
              onClick={() => setShowTour(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
              title="Close Tour"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* 2. Verdict Banner (Visual Hierarchy: Verdict First) */}
      <div className={`p-3 rounded-lg border shadow-2xs ${
        isApproved
          ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/60 text-emerald-900 dark:text-emerald-200'
          : isPendingSecondApproval
          ? 'bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-800/60 text-purple-900 dark:text-purple-200'
          : isUnreadable
          ? 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/60 text-amber-900 dark:text-amber-200'
          : failedGates.length > 0
          ? 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/60 text-amber-900 dark:text-amber-200'
          : totalGates > 0 && passedGates === totalGates && notEvaluatedGates === 0
          ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/60 text-emerald-900 dark:text-emerald-200'
          : 'bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200'
      }`}>
        <div className="flex items-center gap-2.5">
          {isApproved ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          ) : isPendingSecondApproval ? (
            <ShieldAlert className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0" />
          ) : isUnreadable || failedGates.length > 0 ? (
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          ) : totalGates > 0 && passedGates === totalGates && notEvaluatedGates === 0 ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          ) : (
            <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
          )}

          <div className="text-xs flex-1 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-semibold text-xs sm:text-sm">
                {isApproved ? (
                  'Invoice Review Complete (Internal Sign-Off)'
                ) : isPendingSecondApproval ? (
                  'Waiting for Secondary Controller Approval'
                ) : isUnreadable ? (
                  'Couldn\'t Read Document — Clearer Copy Required'
                ) : failedGates.length > 0 ? (
                  `Blocked: ${failedGates.length} Validation Check(s) Failed — Approval Blocked`
                ) : totalGates > 0 && passedGates === totalGates && notEvaluatedGates === 0 ? (
                  'All 7 Automatic Checks Passed — Ready to Approve'
                ) : (
                  `Validation Incomplete — ${passedGates} of ${totalGates} Checks Passed`
                )}
              </span>
              {(isUnreadable || failedGates.length > 0) && (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-200/80 dark:bg-amber-900/60 text-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-800">
                  {isUnreadable ? 'Document unreadable — clearer copy required.' : 'Approval blocked until the failed checks are resolved.'}
                </span>
              )}
            </div>
            <p className="text-[11px] opacity-85 hidden md:block">
              {isApproved ? (
                'Internal AP review is complete. No payment has been executed and no ERP or General Ledger posting has occurred. Approval signifies internal AP sign-off; the supplier has not yet been paid.'
              ) : isPendingSecondApproval ? (
                `First approval was rendered by ${approval?.first_approver_id || 'AP Lead'}. A distinct Financial Controller or System Admin must render secondary sign-off.`
              ) : isUnreadable ? (
                'The document scan could not be read automatically due to scan degradation. Downstream price, PO, and tax checks have not been evaluated.'
              ) : failedGates.length > 0 ? (
                'This invoice cannot be approved while policy validation checks fail. Policy overrides are disabled; approvals are strictly blocked until all discrepancies are resolved or triaged using an authorized action below.'
              ) : totalGates > 0 && passedGates === totalGates && notEvaluatedGates === 0 ? (
                'Supplier identity, PO authorization, GRN delivery, QC acceptance, arithmetic, and price tolerances all verified.'
              ) : (
                'Original document received. Waiting for asynchronous Bedrock extraction and deterministic matching engine evaluation.'
              )}
            </p>
          </div>
        </div>

        {/* Explicit failed gates listing with required next actions */}
        {(isUnreadable || failedGates.length > 0) && (
          <div className="mt-2 pt-2 border-t border-amber-200/80 dark:border-amber-800/80 space-y-1.5">
            <span className="text-[10px] font-bold text-amber-950 dark:text-amber-100 uppercase tracking-wider">
              {isUnreadable ? 'Document Issue & Required Next Action:' : 'Failing Checks & Required Next Actions:'}
            </span>
            <ul className="space-y-1">
              {isUnreadable ? (
                <li className="text-[11px] text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row sm:items-baseline gap-1">
                  <span className="font-semibold text-amber-950 dark:text-amber-100">• Document Readability:</span>
                  <span className="opacity-90">Degraded raster scan with zero machine-readable text.</span>
                  <span className="font-medium text-amber-950 dark:text-amber-100">
                    &rarr; <em>Next Action: Upload a higher-resolution or unskewed copy, or enter details manually.</em>
                  </span>
                </li>
              ) : (
                failedGates.map((g: any, i: number) => (
                  <li key={i} className="text-[11px] text-amber-900 dark:text-amber-200 flex flex-col sm:flex-row sm:items-baseline gap-1">
                    <span className="font-semibold text-amber-950 dark:text-amber-100">• {humanGateName(g.gate_name)}:</span>
                    <span className="opacity-90">{g.notes || 'Validation tolerance exceeded.'}</span>
                    <span className="font-medium text-amber-950 dark:text-amber-100">
                      &rarr; <em>Next Action: {getRequiredNextAction(g.gate_name)}</em>
                    </span>
                  </li>
                ))
              )}
            </ul>
          </div>
        )}
      </div>

      {/* 2.5 Case Explanation & Decision Guide Card */}
      <CaseSummaryCard
        invoice={invoice}
        matchGates={match_gates}
        userRole={currentUser?.role || undefined}
        policy={{
          dual_approval_threshold_inr: dualApprovalThreshold,
          rate_tolerance_percent: rateTolerancePercent,
          rounding_tolerance_inr: 20.0,
        }}
        onOpenGlossary={openGlossaryWithTerm}
      />
      {actionSuccess && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="font-mono text-xs hover:opacity-75">&times;</button>
        </div>
      )}

      {actionError && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="font-mono text-xs hover:opacity-75">&times;</button>
        </div>
      )}

      {/* 3. Split-Pane Workspace: Document (Left) + Evidence Tabs (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* PANE 1: Original Document (5 cols on lg, or 12 cols when doc_focus) */}
        <div className={`${
          workspaceLayout === 'doc_focus'
            ? 'lg:col-span-12'
            : workspaceLayout === 'analysis_focus'
            ? 'hidden'
            : 'lg:col-span-5'
        } bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs flex flex-col h-[480px] lg:h-[780px] min-w-0 transition-all duration-150`}>
          {/* Document Toolbar */}
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate" title={document?.filename || 'Document'}>
                {document?.filename || 'No document file'}
              </span>
              {document?.sha256 && (
                <button
                  onClick={() => handleCopySha(document.sha256)}
                  title="Copy full cryptographic SHA-256 hash"
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                >
                  {copiedSha ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                  <span>{document.sha256.substring(0, 8)}...</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setZoomLevel(Math.max(50, zoomLevel - 15))}
                disabled={zoomLevel <= 50}
                title="Zoom Out"
                className="p-1 rounded text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 disabled:opacity-30"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="text-[10px] font-mono font-medium text-slate-600 dark:text-slate-300 w-10 text-center">
                {zoomLevel}%
              </span>
              <button
                onClick={() => setZoomLevel(Math.min(200, zoomLevel + 15))}
                disabled={zoomLevel >= 200}
                title="Zoom In"
                className="p-1 rounded text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 disabled:opacity-30"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setZoomLevel(100)}
                title="Reset Zoom to 100%"
                className="p-1 rounded text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>

              <div className="h-3.5 w-px bg-slate-300 dark:bg-slate-700 mx-1" />

              {previewUrl && (
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noreferrer"
                  title="Open original document in new browser tab"
                  className="p-1 rounded text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
              {document?.document_id && (
                <button
                  onClick={handleRefreshSignedUrl}
                  disabled={refreshingDocUrl}
                  title="Regenerate pre-signed URL (300s TTL)"
                  className="p-1 rounded text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 disabled:opacity-40"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshingDocUrl ? 'animate-spin text-indigo-600' : ''}`} />
                </button>
              )}
              {document?.document_id && (
                <a
                  href={`/api/v1/documents/${document.document_id}/download`}
                  download={document.filename || 'invoice.pdf'}
                  title="Download verified document (SHA-256 validated)"
                  className="p-1 rounded text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/50"
                >
                  <Download className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>

          {/* Embedded Viewer Canvas */}
          <div className="flex-1 bg-slate-100 dark:bg-slate-950 p-2 overflow-auto flex items-center justify-center relative">
            {previewUrl ? (
              <div 
                className="w-full h-full transition-transform duration-150 origin-top-left"
                style={{ transform: `scale(${zoomLevel / 100})`, width: `${10000 / zoomLevel}%`, height: `${10000 / zoomLevel}%` }}
              >
                <iframe
                  src={previewUrl}
                  title={document?.filename || 'Invoice PDF Preview'}
                  className="w-full h-full rounded border border-slate-200 dark:border-slate-800 shadow-xs"
                />
              </div>
            ) : document ? (
              <div className="text-center p-8 space-y-3">
                <FileText className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto" />
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Document link expired or awaiting secure presigned authorization.
                </p>
                <button
                  onClick={handleRefreshSignedUrl}
                  disabled={refreshingDocUrl}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshingDocUrl ? 'animate-spin' : ''}`} />
                  Generate Fresh Signed URL
                </button>
              </div>
            ) : (
              <div className="text-center p-8 space-y-2 text-slate-500 dark:text-slate-400">
                <FileText className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto" />
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">No original document attached</p>
                <p className="text-[11px] max-w-xs mx-auto">
                  This record was created without an associated PDF artifact, or the document was deleted.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* PANE 2 & 3: Tabbed Analysis & Evidence Panel (7 cols on lg, or 12 cols when analysis_focus) */}
        <div className={`${
          workspaceLayout === 'analysis_focus'
            ? 'lg:col-span-12'
            : workspaceLayout === 'doc_focus'
            ? 'hidden'
            : 'lg:col-span-7'
        } bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs flex flex-col h-[520px] lg:h-[780px] min-w-0 transition-all duration-150`}>
          {/* Analysis Tab Bar */}
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 pt-1 gap-1 min-w-0">
            <div className="flex items-center gap-1 overflow-x-auto whitespace-nowrap scrollbar-none min-w-0 pb-1">
              <button
                onClick={() => setActiveTab('matching')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === 'matching'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Matching & Lines</span>
              </button>

              <button
                onClick={() => setActiveTab('checks')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === 'checks'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Policy Checks ({passedGates}/{totalGates})</span>
                {failedGates.length > 0 && (
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                )}
              </button>

              <button
                onClick={() => setActiveTab('details')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === 'details'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Extracted Information ({extracted_fields?.length || 0})</span>
              </button>

              <button
                onClick={() => setActiveTab('history')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                  activeTab === 'history'
                    ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Audit Trail ({timeline?.length || 0})</span>
              </button>
            </div>

            {/* Workspace View Mode Toggle (Expand / Split) on desktop */}
            <div className="hidden lg:flex items-center gap-1 shrink-0 pb-1 pr-1">
              <button
                type="button"
                onClick={() => setWorkspaceLayout(workspaceLayout === 'analysis_focus' ? 'split' : 'analysis_focus')}
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-200/70 dark:hover:bg-slate-800/80 transition-colors"
                title={workspaceLayout === 'analysis_focus' ? 'Restore Split View (50/50 workspace)' : 'Expand Analysis View (Full 12-column width)'}
              >
                {workspaceLayout === 'analysis_focus' ? (
                  <>
                    <Minimize2 className="w-3.5 h-3.5" />
                    <span>Split View</span>
                  </>
                ) : (
                  <>
                    <Maximize2 className="w-3.5 h-3.5" />
                    <span>Expand Analysis</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Tab Content Container */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {/* TAB 1: MATCHING & LINE ITEMS */}
            {activeTab === 'matching' && (
              <div className="space-y-4">
                {/* 4-Node Procurement Verification Flow & Line-by-Line Match */}
                <ProcurementVerificationFlow
                  invoice={invoice}
                  lines={lines}
                  poSnapshot={data?.po_snapshot}
                  rateTolerancePercent={rateTolerancePercent}
                  onOpenGlossary={openGlossaryWithTerm}
                />

                {/* Net Payable Waterfall */}
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wide border-b border-slate-200 dark:border-slate-800 pb-1 mb-2 font-sans">
                    Net Payable Waterfall
                  </div>
                  <div className="flex justify-between text-slate-600 dark:text-slate-400">
                    <span>Subtotal Billed:</span>
                    <span className="text-slate-900 dark:text-slate-200 tabular-nums">{formatINR(invoice.subtotal)}</span>
                  </div>
                  <div className="flex justify-between text-slate-600 dark:text-slate-400">
                    <span>GST Tax Reconciled:</span>
                    <span className="text-slate-900 dark:text-slate-200 tabular-nums">{formatINR(invoice.tax_amount)}</span>
                  </div>
                  <div className="flex justify-between text-slate-900 dark:text-white font-bold border-t border-slate-200 dark:border-slate-800 pt-1.5 text-sm">
                    <span>Net Authorizable Payable:</span>
                    <span className="text-emerald-600 dark:text-emerald-400 tabular-nums">{formatINR(invoice.net_payable || invoice.total_amount)}</span>
                  </div>
                </div>

                {/* Reference Comparison Honest Disclosure */}
                <div className="p-3 rounded-lg bg-sky-50 dark:bg-sky-950/20 border border-sky-200 dark:border-sky-900/40 text-xs text-sky-900 dark:text-sky-300 flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
                  <p>
                    <strong>Authoritative Reference Integrity:</strong> Evaluated against authoritative procurement reference snapshots. This evaluation workspace uses fictional procurement reference data. Live SAP S/4HANA synchronization is not configured.
                  </p>
                </div>
              </div>
            )}

            {/* TAB 2: 7 POLICY GATES GROUPED BY 3 BUSINESS QUESTIONS */}
            {activeTab === 'checks' && (
              <PolicyChecksGrouped
                matchGates={match_gates}
                onOpenGlossary={openGlossaryWithTerm}
              />
            )}

            {/* TAB 3: EXTRACTED INFORMATION */}
            {activeTab === 'details' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    Information Read by AI ({extracted_fields?.length || 0})
                  </h3>
                  <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/40 px-2 py-0.5 rounded">
                    Verified by automatic checks
                  </span>
                </div>

                {(!extracted_fields || extracted_fields.length === 0) ? (
                  <div className="text-center py-8 text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
                    Nothing has been extracted from this document yet.
                  </div>
                ) : (
                  <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                        <tr>
                          <th className="py-2.5 px-3">Field Name</th>
                          <th className="py-2.5 px-3">Extracted Value</th>
                          <th className="py-2.5 px-3">Page</th>
                          <th className="py-2.5 px-3 text-right">Verification Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                        {extracted_fields.map((f: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30">
                            <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">{f.field_name}</td>
                            <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white font-sans">{f.value || '—'}</td>
                            <td className="py-2.5 px-3 text-slate-500">{f.source_page || '1'}</td>
                            <td className="py-2.5 px-3 text-right">
                              {f.confidence !== null ? (
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                  f.confidence >= 0.9
                                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                                    : 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                                }`}>
                                  {f.confidence >= 0.9 ? 'Verified' : 'Needs Review'}
                                </span>
                              ) : (
                                <span className="text-slate-400">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: AUDIT HISTORY TIMELINE */}
            {activeTab === 'history' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    Append-Only Audit Trail
                  </h3>
                  <span className="text-[11px] font-mono text-slate-500">{timeline?.length || 0} events logged</span>
                </div>

                {(!timeline || timeline.length === 0) ? (
                  <div className="text-center py-8 text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
                    No historical events recorded for this invoice yet.
                  </div>
                ) : (
                  <div className="space-y-3 relative pl-4 border-l-2 border-slate-200 dark:border-slate-800">
                    {timeline.map((t: any) => (
                      <div key={t.event_id} className="relative space-y-1 text-xs">
                        {/* Dot indicator */}
                        <div className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-indigo-500 border-2 border-white dark:border-slate-900" />
                        
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 dark:text-white font-mono">{t.action}</span>
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                              {t.actor_role}
                            </span>
                          </div>
                          <span className="text-[11px] font-mono text-slate-500">
                            {t.timestamp.replace('T', ' ').substring(0, 19)}
                          </span>
                        </div>

                        <div className="text-[11px] text-slate-500 dark:text-slate-400">
                          Actor ID: <code className="font-mono">{t.actor_id}</code>
                        </div>

                        {t.reason && (
                          <p className="text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-950 p-2 rounded border border-slate-200 dark:border-slate-800 mt-1">
                            {t.reason}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Sticky Decision Bar (Bottom) */}
      <div className="fixed bottom-0 left-0 right-0 z-30 lg:pl-64 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 p-3 sm:px-6 transition-colors shadow-lg">
        {isAuditor ? (
          <div className="flex items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400 py-1 font-medium">
            <ShieldCheck className="w-4 h-4 text-slate-400" />
            <span>Your role (Auditor) has read-only oversight permissions. Decision actions are disabled.</span>
          </div>
        ) : isApproved ? (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 max-w-7xl mx-auto text-xs">
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Invoice review complete (Internal sign-off). Cleared for external payment batching; no disbursement or General Ledger posting has occurred.</span>
            </div>
            <button
              onClick={onBack}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium hover:bg-slate-50 text-xs shadow-2xs"
            >
              Return to Invoices
            </button>
          </div>
        ) : (
          <div className="max-w-7xl mx-auto space-y-2">
            {/* Primary Action Button Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 sm:gap-3">
              {/* Secondary Actions Group */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Triage Group */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400 dark:text-slate-500 hidden sm:inline select-none">
                    Triage:
                  </span>
                  <button
                    onClick={() => { setSelectedAction('HOLD_PENDING_EVIDENCE'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Hold for Evidence
                  </button>

                  <button
                    onClick={() => { setSelectedAction('REQUEST_SUPPLIER_CORRECTION'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Ask Supplier to Correct
                  </button>

                  <button
                    onClick={() => { setSelectedAction('RAISE_DEBIT_NOTE'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Raise Debit Note
                  </button>
                </div>

                <div className="h-4 w-px bg-slate-200 dark:bg-slate-700 hidden md:block" />

                {/* Governance Group */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400 dark:text-slate-500 hidden lg:inline select-none">
                    Governance:
                  </span>
                  <button
                    onClick={() => { setSelectedAction('ESCALATE'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Escalate
                  </button>

                  <button
                    onClick={() => { setSelectedAction('QUARANTINE'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-purple-200 dark:border-purple-900/60 bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300 hover:bg-purple-100 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Set Aside (Quarantine)
                  </button>

                  <button
                    onClick={() => { setSelectedAction('REJECT_INVOICE'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="px-2.5 py-1.5 min-h-[36px] sm:min-h-0 rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300 hover:bg-rose-100 text-xs font-medium transition-colors shadow-2xs"
                  >
                    Reject Invoice
                  </button>
                </div>
              </div>

              {/* Primary Action Button or Blocked Indicator */}
              <div className="sm:pl-2 sm:border-l border-slate-200 dark:border-slate-700 shrink-0">
                {failedGates.length > 0 ? (
                  <div
                    title={`Approval blocked: ${failedGates.length} validation check(s) failed. Policy overrides are disabled.`}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-2 sm:py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-300 dark:border-slate-700 cursor-not-allowed select-none shadow-2xs min-h-[40px] sm:min-h-0"
                  >
                    <Lock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>Approval Blocked ({failedGates.length} Failing)</span>
                  </div>
                ) : (
                  <button
                    onClick={() => { setSelectedAction('APPROVE_AP_REVIEW'); setActionReason(''); }}
                    disabled={actionLoading}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-2 sm:py-1.5 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 shadow-xs transition-colors min-h-[40px] sm:min-h-0"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve Review</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Consequence-Aware Action Modal */}
      <ConsequenceAwareActionModal
        isOpen={Boolean(selectedAction)}
        action={selectedAction}
        invoice={invoice}
        policy={{
          dual_approval_threshold_inr: dualApprovalThreshold,
          rate_tolerance_percent: rateTolerancePercent,
          rounding_tolerance_inr: 20.0,
        }}
        reason={actionReason}
        onReasonChange={setActionReason}
        reasonTemplates={selectedAction ? getReasonTemplates(selectedAction) : []}
        isLoading={actionLoading}
        errorMessage={actionError}
        onConfirm={handleExecuteAction}
        onClose={() => {
          setSelectedAction(null);
          setActionError(null);
        }}
        hasFailedGates={failedGates.length > 0}
      />

      {/* Accessible Terminology Glossary Modal */}
      <GlossaryModal
        isOpen={showGlossary}
        onClose={() => setShowGlossary(false)}
        initialTerm={glossaryTerm}
      />
    </div>
  );
};
