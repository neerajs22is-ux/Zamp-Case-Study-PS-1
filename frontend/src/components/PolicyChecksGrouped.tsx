import React, { useState } from 'react';
import { 
  CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp, 
  HelpCircle, ShieldCheck, FileCheck, DollarSign, AlertCircle, Info
} from 'lucide-react';

export interface GateExplanation {
  gateName: string;
  questionGroup: 'A' | 'B' | 'C';
  groupTitle: string;
  whatIsChecked: string;
  whyNeeded: string;
  passMeaning: string;
  failMeaning: string;
  actionOnFail: string;
}

export const GATE_KNOWLEDGE_BASE: Record<string, GateExplanation> = {
  'Vendor Identity Registered': {
    gateName: 'Vendor Identity Registered',
    questionGroup: 'A',
    groupTitle: 'A. Is this a legitimate, new invoice?',
    whatIsChecked: 'Validates that the supplier GSTIN/PAN exists in the authorized Vendor Master with active commercial status.',
    whyNeeded: 'Prevents fraud, unauthorized purchases, and payments to fake shell companies.',
    passMeaning: 'Supplier identity is verified in the approved vendor registry.',
    failMeaning: 'Supplier GSTIN is unrecognized, unverified, or not found in vendor master records.',
    actionOnFail: 'Verify supplier registration details or request formal vendor onboarding before proceeding.',
  },
  'Duplicate Invoice Check': {
    gateName: 'Duplicate Invoice Check',
    questionGroup: 'A',
    groupTitle: 'A. Is this a legitimate, new invoice?',
    whatIsChecked: 'Scans the organization database for prior invoices sharing the same invoice number, vendor GSTIN, or SHA-256 fingerprint.',
    whyNeeded: 'Prevents the company from paying the same bill twice due to re-invoicing or duplicate mail attachments.',
    passMeaning: 'This is a unique, first-time invoice submission with zero historical collisions.',
    failMeaning: 'An invoice with the same reference number or document fingerprint was previously registered or paid.',
    actionOnFail: 'Investigate the prior invoice in the archive. If confirmed duplicate, reject or quarantine.',
  },
  'PO Authorization Valid': {
    gateName: 'PO Authorization Valid',
    questionGroup: 'B',
    groupTitle: 'B. Was this actually ordered and received?',
    whatIsChecked: 'Cross-checks the Purchase Order reference number against authorized ERP procurement contracts.',
    whyNeeded: 'Ensures that company funds are only disbursed for purchases formally authorized by procurement managers.',
    passMeaning: 'Purchase order exists, is currently open/active, and matches the billing entity.',
    failMeaning: 'The PO number is missing, closed, canceled, or does not exist in procurement snapshot records.',
    actionOnFail: 'Confirm valid PO reference with the purchasing agent or place the invoice on Hold for Evidence.',
  },
  'GRN Receipt Confirmed': {
    gateName: 'GRN Receipt Confirmed',
    questionGroup: 'B',
    groupTitle: 'B. Was this actually ordered and received?',
    whatIsChecked: 'Verifies warehouse receiving logs (Goods Receipt Note) confirming the items physically arrived at the facility.',
    whyNeeded: 'Prevents paying for goods that are still in transit, back-ordered, lost, or never shipped.',
    passMeaning: 'Warehouse receiving dock has recorded physical arrival and confirmed accepted quantities.',
    failMeaning: 'No matching Goods Receipt Note (GRN) found in warehouse records for this PO and shipment.',
    actionOnFail: 'Confirm physical delivery status with the warehouse dock or place the invoice on Hold for Evidence.',
  },
  'QC Inspection Accepted': {
    gateName: 'QC Inspection Accepted',
    questionGroup: 'B',
    groupTitle: 'B. Was this actually ordered and received?',
    whatIsChecked: 'Checks the technical quality inspection certificate from warehouse QA engineers for received materials.',
    whyNeeded: 'Protects operations from paying for defective, damaged, or non-compliant parts that were rejected at inspection.',
    passMeaning: 'Quality control inspectors have signed off and accepted the material batch as compliant.',
    failMeaning: 'Goods failed technical inspection or the QC release certificate has not been filed.',
    actionOnFail: 'Request QC release certificate from warehouse QA or request a supplier credit note/debit note.',
  },
  'PO Price & Quantity Tolerance': {
    gateName: 'PO Price & Quantity Tolerance',
    questionGroup: 'B',
    groupTitle: 'B. Was this actually ordered and received?',
    whatIsChecked: 'Line-by-line comparison enforcing 0.00% quantity variance and contracted unit rate tolerance (±1.50%).',
    whyNeeded: 'Prevents commercial price creep, unauthorized rate hikes, and billing for excess quantities beyond PO limits.',
    passMeaning: 'Billed unit rate and quantity strictly align with the contracted PO terms within permitted tolerance.',
    failMeaning: 'Billed rate exceeds PO contract rate by more than ±1.50%, or billed quantity exceeds authorized order.',
    actionOnFail: 'Contact supplier for an amended invoice or credit note, or raise an internal debit note.',
  },
  'GST Arithmetic Reconciled': {
    gateName: 'GST Arithmetic Reconciled',
    questionGroup: 'C',
    groupTitle: 'C. Are the financial and tax details correct?',
    whatIsChecked: 'Validates line-item subtotal addition, applicable GST rates (CGST/SGST/IGST), rounding (within ₹20.00), and final net total.',
    whyNeeded: 'Guarantees statutory tax compliance and ensures the business can legally claim full Input Tax Credit (ITC).',
    passMeaning: 'Document mathematical arithmetic and statutory tax schedules reconcile perfectly.',
    failMeaning: 'Line items do not add up to taxable subtotal, or tax computation deviates from statutory percentages.',
    actionOnFail: 'Request a revised tax invoice with mathematically reconciled tax schedules from the supplier.',
  },
};

interface PolicyChecksGroupedProps {
  matchGates: any[];
  onOpenGlossary?: (term?: string) => void;
}

export const PolicyChecksGrouped: React.FC<PolicyChecksGroupedProps> = ({ matchGates, onOpenGlossary }) => {
  const [expandedGates, setExpandedGates] = useState<Record<string, boolean>>({});

  const toggleGate = (gateName: string) => {
    setExpandedGates((prev) => ({
      ...prev,
      [gateName]: !prev[gateName],
    }));
  };

  const groups = [
    {
      id: 'A',
      title: 'A. Is this a legitimate, new invoice?',
      subtitle: 'Supplier identity verification and duplicate fraud prevention',
      icon: ShieldCheck,
      gateNames: ['Vendor Identity Registered', 'Duplicate Invoice Check'],
    },
    {
      id: 'B',
      title: 'B. Was this actually ordered and received?',
      subtitle: 'Three-way procurement match: Purchase Order, Goods Receipt, Quality, and Tolerance',
      icon: FileCheck,
      gateNames: [
        'PO Authorization Valid',
        'GRN Receipt Confirmed',
        'QC Inspection Accepted',
        'PO Price & Quantity Tolerance',
      ],
    },
    {
      id: 'C',
      title: 'C. Are the financial and tax details correct?',
      subtitle: 'Line-item arithmetic and statutory GST reconciliation',
      icon: DollarSign,
      gateNames: ['GST Arithmetic Reconciled'],
    },
  ];

  const totalGates = matchGates.length;
  const passedGates = matchGates.filter((g) => g.status === 'PASS').length;
  const failedGates = matchGates.filter((g) => g.status === 'FAIL');

  return (
    <div className="space-y-4">
      {/* Progress & Overview Card */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Deterministic Policy Validation Checks
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              7 automated checks grouped by key business verification questions. Failed checks appear first.
            </p>
          </div>
          <div className="text-right">
            <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded ${
              failedGates.length === 0
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
            }`}>
              {passedGates} of {totalGates} Passed
            </span>
          </div>
        </div>

        <div className="w-full bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              failedGates.length > 0 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${totalGates > 0 ? (passedGates / totalGates) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Grouped Accordions */}
      <div className="space-y-4">
        {groups.map((group) => {
          const groupGates = matchGates.filter((g) => group.gateNames.includes(g.gate_name));
          if (groupGates.length === 0) return null;

          // Order failed gates first within the group
          const sortedGates = [...groupGates].sort((a, b) =>
            a.status === 'FAIL' ? -1 : b.status === 'FAIL' ? 1 : 0
          );

          const groupFailedCount = groupGates.filter((g) => g.status === 'FAIL').length;
          const GroupIcon = group.icon;

          return (
            <div 
              key={group.id} 
              className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 overflow-hidden shadow-2xs"
            >
              {/* Group Header */}
              <div className="p-3.5 bg-slate-50/80 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                    groupFailedCount > 0
                      ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/80 dark:text-rose-400'
                      : 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-400'
                  }`}>
                    <GroupIcon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                      {group.title}
                    </h4>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">
                      {group.subtitle}
                    </p>
                  </div>
                </div>

                <div className="shrink-0">
                  {groupFailedCount > 0 ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                      {groupFailedCount} Failed
                    </span>
                  ) : groupGates.some((g) => g.status === 'NOT_EVALUATED') ? (
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      Not Evaluated
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      All Passed
                    </span>
                  )}
                </div>
              </div>

              {/* Group Gates List */}
              <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {sortedGates.map((gate) => {
                  const kb = GATE_KNOWLEDGE_BASE[gate.gate_name];
                  const isExpanded = expandedGates[gate.gate_name] ?? (gate.status === 'FAIL');
                  const isFail = gate.status === 'FAIL';
                  const isPass = gate.status === 'PASS';
                  const isNotEvaluated = gate.status === 'NOT_EVALUATED' || gate.status === 'UNKNOWN';

                  return (
                    <div
                      key={gate.gate_number || gate.gate_name}
                      className={`transition-colors duration-150 ${
                        isFail
                          ? 'bg-rose-50/30 dark:bg-rose-950/20'
                          : isPass
                          ? 'hover:bg-slate-50/60 dark:hover:bg-slate-800/30'
                          : 'bg-slate-50/40 dark:bg-slate-900/40'
                      }`}
                    >
                      {/* Gate Row Header */}
                      <div 
                        onClick={() => toggleGate(gate.gate_name)}
                        className="px-3.5 py-3 flex items-center justify-between gap-3 cursor-pointer select-none transition-colors"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          {isPass ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                          ) : isFail ? (
                            <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                          ) : isNotEvaluated ? (
                            <Info className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                                Check #{gate.gate_number}: {gate.gate_name}
                              </span>
                              {onOpenGlossary && kb && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onOpenGlossary(gate.gate_name);
                                  }}
                                  className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                                  title="Explain term in Glossary"
                                >
                                  <HelpCircle className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                            {gate.notes && (
                              <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate mt-0.5 font-mono">
                                {gate.notes}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            isPass
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : isFail
                              ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                              : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}>
                            {gate.status === 'NOT_EVALUATED' ? 'NOT EVALUATED' : gate.status}
                          </span>
                          <span className="text-slate-400">
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </span>
                        </div>
                      </div>

                      {/* Progressive Disclosure Explanation Drawer (Typographic - No Nested Cards) */}
                      {isExpanded && kb && (
                        <div className="px-4 pb-3.5 pt-1 border-t border-slate-100 dark:border-slate-800/60 space-y-2.5 text-xs bg-slate-50/50 dark:bg-slate-950/40 animate-in fade-in duration-150">
                          {/* Evidence reference */}
                          {gate.evidence_source_id && (
                            <div className="text-[10px] font-mono text-slate-500 dark:text-slate-400 flex items-center gap-1.5 pt-1">
                              <span className="font-sans font-medium text-slate-600 dark:text-slate-300">Traceable Evidence Source:</span>
                              <code className="bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-800 dark:text-slate-200 font-mono text-[10px]">
                                {gate.evidence_source_id}
                              </code>
                            </div>
                          )}

                          {/* Typographic Knowledge Grid */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2.5 pt-1 text-[11px]">
                            <div className="space-y-0.5">
                              <strong className="text-slate-900 dark:text-white block font-semibold">
                                What the system checked:
                              </strong>
                              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                                {kb.whatIsChecked}
                              </p>
                            </div>

                            <div className="space-y-0.5">
                              <strong className="text-slate-900 dark:text-white block font-semibold">
                                Why business policy requires it:
                              </strong>
                              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                                {kb.whyNeeded}
                              </p>
                            </div>

                            <div className="space-y-0.5 pt-1.5 border-t border-slate-200/60 dark:border-slate-800/60">
                              <strong className="text-emerald-700 dark:text-emerald-400 flex items-center gap-1 font-semibold">
                                <CheckCircle2 className="w-3 h-3" />
                                <span>What PASS means:</span>
                              </strong>
                              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                                {kb.passMeaning}
                              </p>
                            </div>

                            <div className="space-y-0.5 pt-1.5 border-t border-slate-200/60 dark:border-slate-800/60">
                              <strong className="text-rose-700 dark:text-rose-400 flex items-center gap-1 font-semibold">
                                <XCircle className="w-3 h-3" />
                                <span>What FAIL means:</span>
                              </strong>
                              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                                {kb.failMeaning}
                              </p>
                            </div>
                          </div>

                          {/* Next Steps for Failed Gate */}
                          {isFail && (
                            <div className="mt-2 p-2.5 rounded-md bg-rose-100/70 dark:bg-rose-950/60 border border-rose-300 dark:border-rose-900 text-rose-950 dark:text-rose-200 text-xs flex items-start gap-2">
                              <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                              <div>
                                <span className="font-bold block text-rose-950 dark:text-rose-100 mb-0.5">
                                  Required Action:
                                </span>
                                <p className="leading-relaxed text-[11px]">
                                  {kb.actionOnFail}
                                </p>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
