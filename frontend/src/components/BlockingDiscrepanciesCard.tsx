import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  FileWarning,
} from "lucide-react";
import { Card, Badge } from "./ui";
import type { InvoiceDetailInvoice, MatchGateItem } from "../types";

interface BlockingDiscrepanciesCardProps {
  invoice: InvoiceDetailInvoice;
  matchGates?: MatchGateItem[];
  hasFailedGates?: boolean;
  onOpenPolicyDrawer?: () => void;
}

export const BlockingDiscrepanciesCard: React.FC<BlockingDiscrepanciesCardProps> = ({
  invoice,
  matchGates = [],
  hasFailedGates = false,
  onOpenPolicyDrawer,
}) => {
  const failedGates = matchGates.filter((g) => g.status === "FAIL");
  const incompleteGates = matchGates.filter(
    (g) => g.status !== "PASS" && g.status !== "FAIL"
  );
  const issuesList = [...failedGates, ...incompleteGates];
  const totalIssues = issuesList.length;

  return (
    <Card className="border border-rose-200 dark:border-rose-900/60 bg-white dark:bg-slate-900 shadow-sm rounded-xl overflow-hidden flex flex-col h-full transition-all">
      {/* 1. Header Bar */}
      <div className="p-3 bg-rose-50/70 dark:bg-rose-950/40 border-b border-rose-200/80 dark:border-rose-900/60 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-rose-100 dark:bg-rose-900/50 border border-rose-300 dark:border-rose-800 flex items-center justify-center text-rose-600 dark:text-rose-300 shrink-0">
            {hasFailedGates ? (
              <AlertTriangle className="w-3.5 h-3.5" />
            ) : (
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            )}
          </div>
          <div className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wider text-rose-900 dark:text-rose-200 truncate">
              Blocking Discrepancies
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {totalIssues > 0 ? (
            <Badge tone="error" size="sm" className="font-bold">
              {totalIssues} {totalIssues === 1 ? "Issue" : "Issues"}
            </Badge>
          ) : (
            <Badge tone="success" size="sm">
              All Clear
            </Badge>
          )}
        </div>
      </div>

      {/* 2. Main Body */}
      <div className="p-3.5 space-y-3 flex-1 flex flex-col">
        {totalIssues > 0 ? (
          <>
            {/* Why Approval is Blocked Summary Banner */}
            <div className="p-2.5 rounded-lg bg-rose-50/90 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900/80 text-xs shrink-0">
              <span className="font-bold text-rose-900 dark:text-rose-200 flex items-center gap-1.5 mb-0.5">
                <FileWarning className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
                Approval blocked until checks are resolved
              </span>
              <p className="text-[11px] text-rose-700 dark:text-rose-300 leading-normal">
                {invoice.decision_reason ||
                  "Policy conditions failed. Automated posting is blocked until exceptions are reviewed."}
              </p>
            </div>

            {/* List of Failed / Incomplete Checks with Detailed Explanations */}
            <div className="space-y-2 flex-1 overflow-y-auto max-h-[300px] pr-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                Failed Checks & Review Reasons:
              </span>
              {issuesList.map((gate, idx) => {
                const isFail = gate.status === "FAIL";
                return (
                  <div
                    key={gate.gate_number ?? idx}
                    className="p-2 rounded-lg bg-slate-50/80 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 text-xs transition-colors"
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5 truncate">
                        <span className="font-mono text-[9.5px] px-1 py-0.5 bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 rounded font-bold shrink-0">
                          G{gate.gate_number}
                        </span>
                        <span className="truncate" title={gate.gate_name}>
                          {gate.gate_name}
                        </span>
                      </span>
                      <Badge tone={isFail ? "error" : "warning"} size="sm" className="shrink-0 text-[9.5px] px-1.5 py-0">
                        {isFail ? "FAIL" : "PENDING"}
                      </Badge>
                    </div>

                    <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed pl-2 border-l-2 border-rose-400 dark:border-rose-600 mt-1">
                      {gate.evidence_notes ||
                        (gate as any).notes ||
                        "Deterministic check failed automated threshold."}
                    </p>
                  </div>
                );
              })}
            </div>

            {/* 3. Action Guidance Section */}
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 shrink-0">
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1">
                  <ArrowRight className="w-3 h-3 text-indigo-500" />
                  Required Action
                </span>
                {onOpenPolicyDrawer && (
                  <button
                    type="button"
                    onClick={onOpenPolicyDrawer}
                    className="text-[10.5px] text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                  >
                    View policy rules
                  </button>
                )}
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-normal">
                {invoice.po_reference
                  ? "Verify billed amounts against ERP contract or request an amended invoice from supplier."
                  : "Non-PO Invoice: Verify supplier credentials and route for departmental manual sign-off."}
              </p>
            </div>
          </>
        ) : (
          /* Empty State: All Checks Passed */
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-2">
            <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Zero Blocking Discrepancies
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-xs">
              All 7 policy validation gates passed with zero tolerance violations.
              This invoice is cleared for straight-through approval.
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};
