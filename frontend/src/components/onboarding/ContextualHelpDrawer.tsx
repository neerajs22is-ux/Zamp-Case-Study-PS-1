import "./OnboardingSurfaces.css";
import React, { useState } from "react";
import { useLocation } from "react-router-dom";
import {
  HelpCircle,
  Compass,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Drawer, Button, Badge } from "../ui";
import { useTour } from "../../context/TourContext";

export const ContextualHelpDrawer: React.FC = () => {
  const {
    isHelpOpen,
    closeHelp,
    activeHelpTab,
    setActiveHelpTab,
    restartTour,
    openWelcome,
  } = useTour();
  const location = useLocation();

  // Search state for terminology
  const [searchTerm, setSearchTerm] = useState("");

  // Accordion state for FAQs
  const [expandedFaq, setExpandedFaq] = useState<number | null>(0);

  // Explain the screen using only the controls and records available here.
  const getScreenHelp = (pathname: string) => {
    if (pathname.startsWith("/today") || pathname === "/")
      return {
        title: "Today",
        summary: "Start with the workload and recent activity shown here.",
        points: [
          {
            label: "Open exceptions",
            desc: "These are issue records, not a count of invoices. Exposure is the amount recorded for an issue.",
          },
          {
            label: "Second approval",
            desc: "This queue contains invoices awaiting an independent internal sign-off; it is not a list of payments due.",
          },
          {
            label: "Touchless rate",
            desc: "The share of decided invoices approved automatically without human intervention.",
          },
          {
            label: "MSME",
            desc: "Micro, small and medium enterprises. The dashboard shows the verified invoice count returned by the service.",
          },
        ],
        actionRecommendation: "Open a queue to investigate its records.",
      };
    if (pathname.startsWith("/invoices/"))
      return {
        title: "Invoice review",
        summary:
          "Compare the supplier’s bill with available records and review the checks.",
        points: [
          {
            label: "Document",
            desc: "Use the document viewer and its available open or retry options to inspect the source.",
          },
          {
            label: "Checks",
            desc: "A failed check needs attention. Unknown or not evaluated does not mean passed.",
          },
          {
            label: "Comparison",
            desc: "PO means purchase order, GRN means goods receipt note, and QC means quality check. A variance is a difference between values.",
          },
          {
            label: "Actions",
            desc: "Available actions depend on your role and the invoice. Read the consequences before confirming; internal approval does not send payment.",
          },
        ],
        actionRecommendation:
          "Read the issue, compared amounts and prerequisites before deciding.",
      };
    if (pathname.startsWith("/invoices"))
      return {
        title: "Invoice inbox",
        summary:
          "An invoice is a supplier’s bill. The tabs group invoices by their recorded stage or decision.",
        points: [
          {
            label: "Queues",
            desc: "Needs Attention uses the action-required stage; Ready for Approval shows match candidates; Waiting on Evidence shows held invoices; Approved & Cleared shows manual approvals.",
          },
          {
            label: "Filters and search",
            desc: "Choose a financial year and month. Search checks only the current page.",
          },
          {
            label: "Add invoices",
            desc: "Use the available upload or Gmail sync controls to bring invoices into the workspace.",
          },
        ],
        actionRecommendation:
          "Open an invoice to inspect its document and checks.",
      };
    if (pathname.startsWith("/exceptions"))
      return {
        title: "Exceptions",
        summary:
          "An exception is an issue record associated with an invoice; its count is not an invoice count.",
        points: [
          {
            label: "Exposure",
            desc: "The amount recorded for the issue. Its calculation basis is not explained in this view.",
          },
          {
            label: "Owner",
            desc: "The assigned person can be changed when your role permits it. A reason may be requested.",
          },
        ],
        actionRecommendation:
          "Open the invoice to review the issue and available actions.",
      };
    if (pathname.startsWith("/approvals"))
      return {
        title: "Second approvals",
        summary: "Some invoices need an independent second internal sign-off.",
        points: [
          {
            label: "Eligibility",
            desc: "Read the record’s checks and eligibility. The second reviewer must be different from the first and have an eligible role.",
          },
          {
            label: "Payment",
            desc: "Internal sign-off records a decision; it does not send a bank payment.",
          },
        ],
        actionRecommendation:
          "Review the first sign-off and prerequisites before using an available action.",
      };
    if (pathname.startsWith("/audit"))
      return {
        title: "Audit trail",
        summary:
          "This view loads up to 100 recent events, not the complete ledger.",
        points: [
          {
            label: "Actor and reason",
            desc: "The actor is the person or system that performed an action. A reason explains why when provided.",
          },
          {
            label: "Details",
            desc: "Open an event for available identifiers and before-and-after data. Search and export apply to the loaded events.",
          },
        ],
        actionRecommendation:
          "Use the filters to find events among those loaded.",
      };
    if (pathname.startsWith("/settings/connections"))
      return {
        title: "Connections",
        summary: "Review integration and service status.",
        points: [
          {
            label: "Status",
            desc: "Check each service and its available actions. Configuration does not guarantee live synchronization.",
          },
        ],
        actionRecommendation: "Use refresh to check current status.",
      };
    if (pathname.startsWith("/settings/reference-data"))
      return {
        title: "Procurement records",
        summary: "Read the records used for invoice matching.",
        points: [
          {
            label: "Source",
            desc: "A snapshot is a saved copy that may not reflect later changes. Check its source and provenance.",
          },
        ],
        actionRecommendation:
          "Search for a supplier, order, receipt or inspection record.",
      };
    if (pathname.startsWith("/settings/team"))
      return {
        title: "Team and access",
        summary: "Review members and access requests.",
        points: [
          {
            label: "Permissions",
            desc: "Actions depend on your role; consult the role permissions view.",
          },
        ],
        actionRecommendation: "Review access before making changes.",
      };
    if (pathname.startsWith("/setup"))
      return {
        title: "Setup guide",
        summary: "Review the available setup steps.",
        points: [
          {
            label: "Workspace data",
            desc: "The tour may show existing live records. It does not submit decisions.",
          },
        ],
        actionRecommendation: "Skip steps that do not apply and return later.",
      };
    return {
      title: "AP Command Center",
      summary: "Review supplier invoices and internal decisions.",
      points: [
        {
          label: "Navigation",
          desc: "Use the sidebar to open the areas available to your role.",
        },
      ],
      actionRecommendation: "Select a menu item to begin.",
    };
  };

  const currentScreenHelp = getScreenHelp(location.pathname);
  const glossaryTerms = [
    { term: "Invoice", def: "A supplier’s bill for goods or services." },
    {
      term: "PO (Purchase Order)",
      def: "A record of what was ordered and the agreed quantities and prices.",
    },
    { term: "GRN (Goods Receipt Note)", def: "A record of goods received." },
    {
      term: "QC (Quality Check)",
      def: "An inspection record for received goods.",
    },
    {
      term: "Three-Way Match / Matching",
      def: "Comparing invoice information with available order, receipt and inspection records.",
    },
    {
      term: "Variance",
      def: "A difference between compared values, such as billed and ordered prices.",
    },
    {
      term: "Tolerance",
      def: "An allowed difference used by a check. See the displayed check and policy for the applicable limit.",
    },
    {
      term: "Exception",
      def: "An issue record associated with an invoice. Exception counts are not invoice counts.",
    },
    {
      term: "Second approval",
      def: "An independent internal sign-off required for some invoices. See the record for its requirements.",
    },
    {
      term: "MSME",
      def: "Micro, small and medium enterprises. See the invoice details for any recorded deadline.",
    },
    {
      term: "Not checked / unavailable",
      def: "A check was not run or its result is unavailable. This does not mean it passed or failed.",
    },
    {
      term: "Debit note",
      def: "An accounting document used to record an adjustment related to a supplier invoice.",
    },
  ];

  const filteredGlossary = glossaryTerms.filter(
    (g) =>
      g.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
      g.def.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  // Frequently Asked Questions
  const faqs = [
    {
      q: "Does “supplier correction needed” notify the supplier?",
      a: "No. It records follow-up inside this workspace. Your team contacts the supplier outside the app. A revised attachment is not automatically linked to the original invoice.",
    },
    {
      q: "Am I watching the process run live?",
      a: "Invoice and job statuses are recorded responses. The inbox refreshes while it sees processing records, but this is not a live stage-by-stage execution stream. Inspect check results and audit events for available evidence.",
    },
    {
      q: "Does approving an invoice pay the supplier?",
      a: "No. The application records an internal sign-off; it does not send a bank payment.",
    },
    {
      q: 'What does "Not Checked" mean?',
      a: "The relevant verification has not been completed or could not be performed (e.g. goods receipt not yet recorded). It does not automatically mean the invoice failed.",
    },
    {
      q: 'Why is an invoice marked as "Action Required"?',
      a: "The invoice is in the action-required stage. Open it to see its checks and the available next actions.",
    },
    {
      q: "Can I correct OCR misreads on invoice line items?",
      a: "Where editing is available to your role, use Edit on a line and provide a reason. Review the resulting checks before deciding.",
    },
    {
      q: "Who can authorize high-value dual approvals?",
      a: "An eligible Controller or System Admin can provide a required second sign-off, provided they are not the first reviewer. Check the invoice for its requirements.",
    },
    {
      q: 'What does "Evaluated against reference snapshots" mean?',
      a: "The checks use saved copies of procurement records. Check their displayed source and provenance; a snapshot may not include later changes.",
    },
  ];

  return (
    <Drawer
      className="onboarding-surface help-drawer"
      isOpen={isHelpOpen}
      onClose={closeHelp}
      title={
        <div className="flex items-center gap-2">
          <HelpCircle className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span>AP Assistant & Contextual Help</span>
        </div>
      }
      description="Helpful guides, screen explanations, workflow diagrams, and plain-language definitions."
      width="lg"
    >
      <div className="space-y-5 text-xs">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1.5 border-b border-slate-200 dark:border-slate-800 pb-2 overflow-x-auto">
          <button
            type="button"
            aria-pressed={activeHelpTab === "screen"}
            onClick={() => setActiveHelpTab("screen")}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === "screen"
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850"
            }`}
          >
            On This Screen
          </button>
          <button
            type="button"
            aria-pressed={activeHelpTab === "overview"}
            onClick={() => setActiveHelpTab("overview")}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === "overview"
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850"
            }`}
          >
            Workflow Overview
          </button>
          <button
            type="button"
            aria-pressed={activeHelpTab === "glossary"}
            onClick={() => setActiveHelpTab("glossary")}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === "glossary"
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850"
            }`}
          >
            Terminology ({glossaryTerms.length})
          </button>
          <button
            type="button"
            aria-pressed={activeHelpTab === "faq"}
            onClick={() => setActiveHelpTab("faq")}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === "faq"
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850"
            }`}
          >
            FAQs
          </button>
        </div>

        {/* Action Quick Launchers */}
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={restartTour}
            leftIcon={
              <RotateCcw className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            }
            className="w-full justify-center"
          >
            Restart Guided Tour
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              closeHelp();
              openWelcome();
            }}
            leftIcon={
              <Compass className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            }
            className="w-full justify-center"
          >
            Welcome Guide
          </Button>
        </div>

        {/* TAB 1: Screen Guide (Context-Aware!) */}
        {activeHelpTab === "screen" && (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 dark:text-white text-sm">
                  {currentScreenHelp.title}
                </span>
                <Badge tone="info" size="sm">
                  Current View
                </Badge>
              </div>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                {currentScreenHelp.summary}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-2">
                Key Components On This Screen:
              </span>
              <div className="space-y-2">
                {currentScreenHelp.points.map((pt, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                  >
                    <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                      {pt.label}
                    </span>
                    <p className="text-slate-600 dark:text-slate-400 mt-0.5 leading-relaxed text-[11px]">
                      {pt.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40 text-emerald-900 dark:text-emerald-300">
              <span className="font-semibold block mb-0.5">
                Recommended Next Action:
              </span>
              <p className="text-[11px] leading-relaxed">
                {currentScreenHelp.actionRecommendation}
              </p>
            </div>
          </div>
        )}

        {/* TAB 2: Workflow Overview */}
        {activeHelpTab === "overview" && (
          <div className="space-y-4">
            <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
              AP Command Center automates the end-to-end accounts payable
              process through 5 deterministic stages:
            </p>

            <div className="space-y-2">
              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 flex items-center justify-center font-bold text-[10px]">
                    1
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Invoice Ingestion
                  </span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Bills arrive via Gmail inbox synchronization or manual
                  drag-and-drop upload. Each file is cryptographically
                  fingerprinted with SHA-256 to prevent duplicates.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300 flex items-center justify-center font-bold text-[10px]">
                    2
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Data Extraction
                  </span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  OCR extracts header fields (Vendor Name, GSTIN, Date, Total
                  Amount) and individual line items with rates, quantities, and
                  GST classifications.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 flex items-center justify-center font-bold text-[10px]">
                    3
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    4-Way Matching
                  </span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Extracted lines are matched against Purchase Orders (PO),
                  Goods Receipt Notes (GRN), and Quality Certificates (QC).
                  Enforces strict 0.00% quantity and ±1.50% rate tolerance.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 flex items-center justify-center font-bold text-[10px]">
                    4
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Exception Triage
                  </span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Discrepant invoices are flagged with the exact failing gate.
                  Operators can request supplier corrections, raise debit notes,
                  or adjust OCR misreads.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300 flex items-center justify-center font-bold text-[10px]">
                    5
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Dual Governance Sign-Off
                  </span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Invoices passing all checks are cleared. High-value bills (≥
                  ₹5,00,000) route to a Financial Controller for independent
                  dual sign-off before downstream payment batching.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: Common Terminology (Searchable Glossary) */}
        {activeHelpTab === "glossary" && (
          <div className="space-y-3">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search terminology (e.g. PO, GRN, MSME)..."
              className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
            />

            <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
              {filteredGlossary.map((item, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                >
                  <span className="font-semibold text-indigo-700 dark:text-indigo-400 block font-mono text-xs">
                    {item.term}
                  </span>
                  <p className="text-slate-600 dark:text-slate-300 mt-1 leading-relaxed text-[11px]">
                    {item.def}
                  </p>
                </div>
              ))}
              {filteredGlossary.length === 0 && (
                <div className="text-center py-8 text-slate-400 text-xs">
                  No terms matched "{searchTerm}".
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: Frequently Asked Questions */}
        {activeHelpTab === "faq" && (
          <div className="space-y-2">
            {faqs.map((faq, idx) => {
              const isExpanded = expandedFaq === idx;
              return (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden"
                >
                  <button
                    type="button"
                    aria-expanded={isExpanded}
                    onClick={() => setExpandedFaq(isExpanded ? null : idx)}
                    className="w-full p-3 text-left font-semibold text-slate-800 dark:text-slate-200 flex items-center justify-between gap-2 hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors cursor-pointer"
                  >
                    <span>{faq.q}</span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-slate-400 shrink-0" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
                    )}
                  </button>
                  {isExpanded && (
                    <div className="help-faq-answer px-3 pb-3 pt-0 text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                      <p className="pt-2">{faq.a}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Drawer>
  );
};
