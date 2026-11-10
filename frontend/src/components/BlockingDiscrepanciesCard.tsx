import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { Card, Badge } from "./ui";
import type { InvoiceDetailInvoice, MatchGateItem } from "../types";

interface BlockingDiscrepanciesCardProps {
  invoice: InvoiceDetailInvoice;
  matchGates?: MatchGateItem[];
  hasFailedGates?: boolean;
  onOpenPolicyDrawer?: () => void;
}

function getRemediation(gate: MatchGateItem, invoice: InvoiceDetailInvoice): string {
  const num = gate.gate_number;
  const name = (gate.gate_name || "").toLowerCase();

  if (num === 1 || name.includes("vendor")) {
    return "Verify vendor legal identity and GST credentials in ERP master vendor ledger.";
  }
  if (num === 2 || name.includes("po auth")) {
    return invoice.po_reference
      ? "PO not found in active ERP contracts. Link a registered purchase order."
      : "Non-PO invoice: Obtain departmental approval or register an approved PO.";
  }
  if (num === 3 || name.includes("grn") || name.includes("goods receipt")) {
    return "Check warehouse receiving records or wait for Goods Receipt Note (GRN) posting.";
  }
  if (num === 4 || name.includes("qc") || name.includes("quality")) {
    return "Physical material inspection required. Request quality certificate sign-off from plant manager.";
  }
  if (num === 5 || name.includes("gst") || name.includes("tax")) {
    return "Tax calculation mismatch. Reconcile GST percentage, taxable value, and line sums.";
  }
  if (num === 6 || name.includes("tolerance") || name.includes("price")) {
    return "Billed rate exceeds PO schedule tolerance. Request vendor credit note or Controller override.";
  }
  if (num === 7 || name.includes("duplicate")) {
    return "Potential duplicate document. Compare voucher history and SHA-256 fingerprint in audit ledger.";
  }
  return "Grounding tripwire tripped on unverified tokens. Verify scan coordinates against source document.";
}

export const BlockingDiscrepanciesCard: React.FC<BlockingDiscrepanciesCardProps> = ({
  invoice,
  matchGates = [],
  hasFailedGates: _hasFailedGates = false,
  onOpenPolicyDrawer,
}) => {
  const [expandedGates, setExpandedGates] = useState<Set<number>>(new Set());

  const toggleGate = (num: number) => {
    setExpandedGates((prev) => {
      const next = new Set(prev);
      if (next.has(num)) next.delete(num);
      else next.add(num);
      return next;
    });
  };

  const failedGates = matchGates.filter((g) => g.status === "FAIL");
  const incompleteGates = matchGates.filter(
    (g) => g.status !== "PASS" && g.status !== "FAIL"
  );
  const issuesList = [...failedGates, ...incompleteGates];
  const totalIssues = issuesList.length;
  const allPassed = matchGates.length >= 7 && matchGates.every((g) => g.status === "PASS");

  return (
    <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs rounded-xl overflow-hidden transition-all">
      {/* 1. Header */}
      <div className="px-3.5 py-2.5 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {totalIssues > 0 ? (
            <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
          ) : (
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
          )}
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-100 truncate">
            Blocking Discrepancies
          </h3>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {totalIssues > 0 ? (
            <Badge tone="error" size="sm" className="font-bold">
              {totalIssues} {totalIssues === 1 ? "Issue" : "Issues"}
            </Badge>
          ) : allPassed ? (
            <Badge tone="success" size="sm">
              All Clear
            </Badge>
          ) : (
            <Badge tone="warning" size="sm">
              Not verified
            </Badge>
          )}
        </div>
      </div>

      {/* 2. Main Content */}
      <div className="p-3.5 sm:p-4 space-y-2.5">
        {totalIssues > 0 ? (
          <>
            {/* Concise Blocked Notice */}
            <div className="p-2.5 rounded-lg bg-rose-50/70 dark:bg-rose-950/30 border border-rose-200/80 dark:border-rose-900/50 text-xs flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
              <span className="text-[11px] text-rose-900 dark:text-rose-200 font-medium leading-tight">
                Approval blocked until failed checks are resolved or overridden by an authorized reviewer.
              </span>
            </div>

            {/* List of Issue Rows with Expandable Evidence */}
            <div className="space-y-1.5 pt-0.5">
              {issuesList.map((gate, idx) => {
                const gateId = gate.gate_number ?? idx;
                const isExpanded = expandedGates.has(gateId);
                const isSafeguard =
                  gate.gate_number >= 8 ||
                  gate.gate_name?.toLowerCase().includes("extraction evidence");
                const gateTag = isSafeguard ? "SAFEGUARD" : `G${gate.gate_number}`;
                const isFail = gate.status === "FAIL";
                const remediation = getRemediation(gate, invoice);

                return (
                  <div
                    key={gateId}
                    className="rounded-lg border border-slate-200/80 dark:border-slate-800/80 bg-slate-50/60 dark:bg-slate-850/50 overflow-hidden text-xs transition-colors"
                  >
                    {/* Compact Primary Row */}
                    <div
                      onClick={() => toggleGate(gateId)}
                      className="p-2 sm:px-2.5 flex items-start justify-between gap-2 cursor-pointer hover:bg-slate-100/70 dark:hover:bg-slate-800/70"
                    >
                      <div className="min-w-0 space-y-0.5 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`font-mono text-[9px] px-1 py-0.2 rounded font-bold ${
                              isSafeguard
                                ? "bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-300"
                                : "bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300"
                            }`}
                          >
                            {gateTag}
                          </span>
                          <span className="font-semibold text-slate-900 dark:text-slate-100 truncate text-[11.5px]">
                            {gate.gate_name}
                          </span>
                        </div>
                        <p className="text-[10.5px] text-slate-600 dark:text-slate-300 line-clamp-1">
                          {gate.evidence_notes || (gate as any).notes || "Deterministic policy rule failed automated threshold."}
                        </p>
                      </div>

                      <div className="flex items-center gap-1 shrink-0 pt-0.5">
                        <Badge tone={isFail ? "error" : "warning"} size="sm" className="text-[9px] px-1.5 py-0 font-bold">
                          {isFail ? "FAIL" : "PENDING"}
                        </Badge>
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                        )}
                      </div>
                    </div>

                    {/* Expandable Calculation, Evidence & Remediation */}
                    {isExpanded && (
                      <div className="p-2.5 pt-1.5 border-t border-slate-200/60 dark:border-slate-800 bg-white dark:bg-slate-900/80 text-[11px] space-y-1.5">
                        <div>
                          <span className="text-[9.5px] font-bold uppercase text-slate-400 block">
                            Evidence & Notes:
                          </span>
                          <p className="text-slate-700 dark:text-slate-300 font-mono text-[10px] leading-relaxed mt-0.5">
                            {gate.evidence_notes || (gate as any).notes || "No detailed calculations logged."}
                          </p>
                        </div>

                        <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
                          <span className="text-[9.5px] font-bold uppercase text-indigo-600 dark:text-indigo-400 flex items-center gap-1">
                            <ArrowRight className="w-2.5 h-2.5" /> Remediation Guidance:
                          </span>
                          <p className="text-slate-600 dark:text-slate-400 text-[10.5px] mt-0.5 leading-normal">
                            {remediation}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Concise Footer with Action & Rules */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
              <span className="text-[10.5px] text-slate-500 dark:text-slate-400 truncate">
                Action: <strong className="text-slate-700 dark:text-slate-300">{invoice.po_reference ? "Request vendor rate correction" : "Route for exception sign-off"}</strong>
              </span>

              {onOpenPolicyDrawer && (
                <button
                  type="button"
                  onClick={onOpenPolicyDrawer}
                  className="text-[10.5px] text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer shrink-0 ml-2"
                >
                  View policy rules
                </button>
              )}
            </div>
          </>
        ) : allPassed ? (
          /* Verified clear state: only after every recorded gate passed. */
          <div className="py-6 text-center space-y-1.5">
            <div className="w-8 h-8 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Zero Blocking Discrepancies
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
              All recorded policy validation gates passed with zero tolerance violations.
              Document is cleared for straight-through approval.
            </p>
          </div>
        ) : (
          /* No completed verification: never imply that checks passed. */
          <div className="py-6 text-center space-y-1.5">
            <div className="w-8 h-8 mx-auto rounded-full bg-amber-100 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <Clock className="w-5 h-5" />
            </div>
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Verification Not Complete
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
              No completed seven-gate result is available. Approval remains blocked until
              processing succeeds and recorded checks are available.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};
