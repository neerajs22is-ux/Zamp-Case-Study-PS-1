import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { 
  HelpCircle, 
  Compass, 
  RotateCcw, 
  ChevronDown, 
  ChevronUp 
} from 'lucide-react';
import { Drawer, Button, Badge } from '../ui';
import { useTour } from '../../context/TourContext';

export const ContextualHelpDrawer: React.FC = () => {
  const { isHelpOpen, closeHelp, activeHelpTab, setActiveHelpTab, restartTour, openWelcome } = useTour();
  const location = useLocation();

  // Search state for terminology
  const [searchTerm, setSearchTerm] = useState('');
  
  // Accordion state for FAQs
  const [expandedFaq, setExpandedFaq] = useState<number | null>(0);

  // Dynamic Content for the Current Screen
  const getScreenHelp = (pathname: string) => {
    if (pathname.startsWith('/today') || pathname === '/') {
      return {
        title: "Today's AP Operations Pulse",
        summary: "Your daily command center for tracking workload, urgent discrepancies, and compliance.",
        points: [
          { label: "Zone 1 (Daily Triad)", desc: "Quick metrics showing invoices needing attention, clean matches ready for sign-off, and straight-through automation rate." },
          { label: "Zone 2 (Priority Action Queue)", desc: "Invoices requiring immediate review, prioritized by discrepancy severity and due date. Click 'Review' to open." },
          { label: "Zone 3 (Compliance & Exposure)", desc: "Tracks cleared vs blocked liability and monitors mandatory 45-day statutory MSME payment deadlines to avoid interest penalties." },
        ],
        actionRecommendation: "Check invoices in 'Needs Attention' first to resolve any blocking checks before payment batching.",
      };
    }
    if (pathname.startsWith('/invoices/')) {
      return {
        title: "50/50 Invoice Review Workspace",
        summary: "Side-by-side reconciliation interface comparing the original invoice document against procurement records.",
        points: [
          { label: "Left Pane (Document Viewer)", desc: "Inspect original invoice PDF or image with zoom controls, full-screen expansion, and SHA-256 cryptographic hash." },
          { label: "Sticky Verdict Strip (48px)", desc: "Summarizes match outcome, gate pass ratio, and whether dual approval is required for bills ≥ ₹5,00,000." },
          { label: "4-Way Match Table", desc: "Line-by-line comparison of billed amounts against Purchase Order (PO), Goods Receipt (GRN), and Quality Check (QC)." },
          { label: "Audited Line Correction", desc: "Click 'Edit' on any line to adjust OCR character misreads. Requires an audit reason and triggers immediate gate re-evaluation." },
          { label: "Sticky Decision Footer", desc: "Contextual actions (Approve, Request Correction, Debit Note, Quarantine, Reject) with lean 45-word consequence confirmations." },
        ],
        actionRecommendation: "Verify line amounts match PO and GRN. If correct, approve for payment. If discrepancies exist, request supplier correction or raise a debit note.",
      };
    }
    if (pathname.startsWith('/invoices')) {
      return {
        title: "Invoice Inbox & Work Queues",
        summary: "Pre-filtered queues for organizing invoices by their processing stage.",
        points: [
          { label: "Queue Tabs", desc: "Easily filter between 'Needs Attention', 'Ready for Approval', 'Waiting on Evidence', and 'Approved'." },
          { label: "Fiscal Period Filters", desc: "Select Indian Fiscal Year (FY 24-25, FY 25-26, etc.) and calendar month to isolate specific accounting periods." },
          { label: "Drag & Drop Ingestion", desc: "Upload new invoice PDFs directly into the automated processing pipeline." },
        ],
        actionRecommendation: "Select an invoice row to open the full 50/50 review workspace.",
      };
    }
    if (pathname.startsWith('/exceptions')) {
      return {
        title: "Exception Triage Queue",
        summary: "Focused queue of invoices blocked by policy checks, quantity shortages, or rate variances.",
        points: [
          { label: "Blocking Policy Gates", desc: "Identifies the exact gate number and reason blocking internal sign-off." },
          { label: "MSME Statutory Urgency", desc: "Highlights invoices approaching the 45-day MSMED Act 2006 statutory settlement deadline." },
          { label: "Owner Reassignment", desc: "Click 'Assign Owner' to route an exception to a buyer or AP specialist with an audit justification note." },
        ],
        actionRecommendation: "Investigate quantity shortages and price variances. Reassign to procurement buyers if purchase orders need amendments.",
      };
    }
    if (pathname.startsWith('/approvals')) {
      return {
        title: "Dual-Control Approvals Queue",
        summary: "Statutory governance queue for invoices equal to or exceeding ₹5,00,000.",
        points: [
          { label: "Two-Person Rule", desc: "Enforces separation of duties: Step 1 (AP Specialist review) + Step 2 (Financial Controller sign-off)." },
          { label: "Anti-Self-Approval", desc: "The user who conducted the initial line review cannot sign off as the secondary approver." },
          { label: "Treasury Decoupling", desc: "Approval authorizes internal AP sign-off; bank payments are executed separately by treasury." },
        ],
        actionRecommendation: "Controllers can review primary sign-off notes and authorize final AP clearance.",
      };
    }
    if (pathname.startsWith('/audit')) {
      return {
        title: "Immutable Audit Ledger",
        summary: "Cryptographically tracked, append-only log of all system transitions and human reviews.",
        points: [
          { label: "Natural Language Stream", desc: "Readable event descriptions showing who did what, when, and with what justification." },
          { label: "Cryptographic Proofs", desc: "Click 'Details' on any row to inspect correlation IDs and JSON state diffs (before vs after)." },
          { label: "CSV Export", desc: "Download full compliance reports for external and internal financial auditors." },
        ],
        actionRecommendation: "Use search and category tabs to locate specific invoice audit histories.",
      };
    }
    return {
      title: "AP Command Center Overview",
      summary: "Autonomous invoice processing and reconciliation platform.",
      points: [
        { label: "Navigation", desc: "Use the left sidebar to navigate between operational dashboards, invoices, and configuration." },
        { label: "Role Awareness", desc: "Actions are adapted to your assigned role (AP Associate, AP Lead, Controller, or Auditor)." },
      ],
      actionRecommendation: "Select a menu item in the sidebar to begin your AP workflow.",
    };
  };

  const currentScreenHelp = getScreenHelp(location.pathname);

  // Common Terminology Glossary
  const glossaryTerms = [
    {
      term: 'PO (Purchase Order)',
      def: 'A legally binding commercial document issued by a buyer to a supplier indicating types, quantities, and agreed prices for products or services.',
    },
    {
      term: 'GRN (Goods Receipt Note)',
      def: 'A document issued by the warehouse confirming physical receipt of goods, validating that items were actually delivered before invoice payment.',
    },
    {
      term: 'QC Record (Quality Certificate)',
      def: 'Inspection record confirming delivered materials passed physical quality inspection and laboratory test standards.',
    },
    {
      term: '3-Way & 4-Way Matching',
      def: 'Automated verification comparing the Vendor Invoice against the Purchase Order (PO), Goods Receipt (GRN), and Quality Certificate (QC) to prevent overpayment.',
    },
    {
      term: 'Price Variance Tolerance (±1.50%)',
      def: 'Deterministic allowance permitting unit price fluctuations up to 1.50% above contracted PO rates to accommodate statutory fuel or minor commodity adjustments.',
    },
    {
      term: 'Quantity Shortage Tolerance (0.00%)',
      def: 'Strict rule that permits zero quantity shortages. Invoices billing for more units than recorded on the Goods Receipt Note are blocked immediately.',
    },
    {
      term: 'Dual-Approval Invariant (≥ ₹5,00,000)',
      def: 'Governance rule requiring two distinct individuals (AP Specialist + Financial Controller) to sign off on invoices with totals equal to or exceeding ₹5,00,000.',
    },
    {
      term: 'Statutory MSME (Section 15)',
      def: 'Indian Micro, Small and Medium Enterprises Development Act 2006 mandate requiring invoice settlement within 45 days, carrying compound interest penalties for late payment.',
    },
    {
      term: 'Not Checked / Unavailable Status',
      def: 'Indicates the check was not run or prerequisite data (such as a GRN) was not yet uploaded. It does not automatically mean the invoice has failed.',
    },
    {
      term: 'Debit Note',
      def: 'An accounting document issued to a supplier to adjust for overbilling, rate discrepancies, or damaged goods, reducing the payable liability.',
    },
  ];

  const filteredGlossary = glossaryTerms.filter(
    (g) =>
      g.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
      g.def.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Frequently Asked Questions
  const faqs = [
    {
      q: 'Does approving an invoice pay the supplier?',
      a: 'No. AP Command Center records internal operational and financial review sign-off. Fund disbursement is strictly executed downstream by company treasury or ERP banking integration.',
    },
    {
      q: 'What does "Not Checked" mean?',
      a: 'The relevant verification has not been completed or could not be performed (e.g. goods receipt not yet recorded). It does not automatically mean the invoice failed.',
    },
    {
      q: 'Why is an invoice marked as "Action Required"?',
      a: 'One or more deterministic checks failed (e.g. price variance > 1.50%, quantity shortage, or missing PO). Discrepancies must be resolved before payment authorization.',
    },
    {
      q: 'Can I correct OCR misreads on invoice line items?',
      a: 'Yes. On the Invoice Review workspace, click "Edit" on any line item to correct quantities or rates. You must provide an audit reason, and all 7 policy gates will re-evaluate immediately.',
    },
    {
      q: 'Who can authorize high-value dual approvals?',
      a: 'Invoices ≥ ₹5,00,000 require an initial review by an AP Lead or Specialist, followed by secondary sign-off from a Financial Controller or System Admin. Anti-self-approval prevents the same user from signing both steps.',
    },
    {
      q: 'What does "Evaluated against reference snapshots" mean?',
      a: 'Verification is computed against certified procurement records stored in the database. Direct live SAP synchronization is decoupled for evaluation security.',
    },
  ];

  return (
    <Drawer
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
            onClick={() => setActiveHelpTab('screen')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === 'screen'
                ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850'
            }`}
          >
            On This Screen
          </button>
          <button
            type="button"
            onClick={() => setActiveHelpTab('overview')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === 'overview'
                ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850'
            }`}
          >
            Workflow Overview
          </button>
          <button
            type="button"
            onClick={() => setActiveHelpTab('glossary')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === 'glossary'
                ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850'
            }`}
          >
            Terminology ({glossaryTerms.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveHelpTab('faq')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              activeHelpTab === 'faq'
                ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-850'
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
            leftIcon={<RotateCcw className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />}
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
            leftIcon={<Compass className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />}
            className="w-full justify-center"
          >
            Welcome Guide
          </Button>
        </div>

        {/* TAB 1: Screen Guide (Context-Aware!) */}
        {activeHelpTab === 'screen' && (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 dark:text-white text-sm">
                  {currentScreenHelp.title}
                </span>
                <Badge tone="info" size="sm">Current View</Badge>
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
                  <div key={idx} className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
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
              <span className="font-semibold block mb-0.5">Recommended Next Action:</span>
              <p className="text-[11px] leading-relaxed">
                {currentScreenHelp.actionRecommendation}
              </p>
            </div>
          </div>
        )}

        {/* TAB 2: Workflow Overview */}
        {activeHelpTab === 'overview' && (
          <div className="space-y-4">
            <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
              AP Command Center automates the end-to-end accounts payable process through 5 deterministic stages:
            </p>

            <div className="space-y-2">
              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 flex items-center justify-center font-bold text-[10px]">1</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Invoice Ingestion</span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Bills arrive via Gmail inbox synchronization or manual drag-and-drop upload. Each file is cryptographically fingerprinted with SHA-256 to prevent duplicates.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300 flex items-center justify-center font-bold text-[10px]">2</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Data Extraction</span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  OCR extracts header fields (Vendor Name, GSTIN, Date, Total Amount) and individual line items with rates, quantities, and GST classifications.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 flex items-center justify-center font-bold text-[10px]">3</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">4-Way Matching</span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Extracted lines are matched against Purchase Orders (PO), Goods Receipt Notes (GRN), and Quality Certificates (QC). Enforces strict 0.00% quantity and ±1.50% rate tolerance.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 flex items-center justify-center font-bold text-[10px]">4</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Exception Triage</span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Discrepant invoices are flagged with the exact failing gate. Operators can request supplier corrections, raise debit notes, or adjust OCR misreads.
                </p>
              </div>

              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300 flex items-center justify-center font-bold text-[10px]">5</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Dual Governance Sign-Off</span>
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] pl-7">
                  Invoices passing all checks are cleared. High-value bills (≥ ₹5,00,000) route to a Financial Controller for independent dual sign-off before downstream payment batching.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: Common Terminology (Searchable Glossary) */}
        {activeHelpTab === 'glossary' && (
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
                <div key={idx} className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
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
        {activeHelpTab === 'faq' && (
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
                    <div className="px-3 pb-3 pt-0 text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
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
