import { useDialogFocus } from "../hooks/useDialogFocus";
import React, { useState } from "react";
import { api } from "../api/client";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  X,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Lock,
  Clock,
  FileText,
  ArrowRight,
} from "lucide-react";

interface FeatureShowcaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSwitchRole?: (role: string) => void;
}

interface ShowcaseScenario {
  id: string;
  number: number;
  title: string;
  badge: string;
  badgeColor: string;
  summary: string;
  whatItProves: string;
  roleRequired: string;
  targetRoute: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const FeatureShowcaseModal: React.FC<FeatureShowcaseModalProps> = ({
  isOpen,
  onClose,
  onSwitchRole,
}) => {
  const navigate = useNavigate();

  const [launchMessage, setLaunchMessage] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const dialogRef = useDialogFocus(isOpen, onClose);
  if (!isOpen) return null;

  const scenarios: ShowcaseScenario[] = [
    {
      id: "touchless-match",
      number: 1,
      title: "Touchless 3-Way Match & Clean Sign-Off",
      badge: "Golden Path",
      badgeColor:
        "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
      summary:
        "Invoice AP-26-009 matches PO-26-2001 and GRN-26-601 perfectly. All 7 deterministic policy gates pass.",
      whatItProves:
        "Autonomous verification without human intervention; single-click internal review approval for invoices < ₹5,00,000.",
      roleRequired: "AP_LEAD",
      targetRoute: "/invoices/inv_d76401c096d0",
      icon: CheckCircle2,
    },
    {
      id: "rate-variance-debit-note",
      number: 2,
      title: "Line Rate Discrepancy & Debit Note Recommendation",
      badge: "Price Variance",
      badgeColor:
        "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300 dark:border-amber-800",
      summary:
        "Invoice AP-26-011 billed at ₹2,850/unit vs contracted PO rate ₹2,450/unit (+16.33% variance).",
      whatItProves:
        "Strict ±1.50% price tolerance enforcement. System prevents payment approval and calculates an exact ₹500 debit note.",
      roleRequired: "AP_LEAD",
      targetRoute: "/invoices/inv_dbfcaf77ba9b",
      icon: AlertTriangle,
    },
    {
      id: "dual-control-governance",
      number: 3,
      title: "High-Value Dual-Approval Governance (≥ ₹5,00,000)",
      badge: "Dual Control",
      badgeColor:
        "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-300 dark:border-purple-800",
      summary:
        "Invoice INV-DUAL-SEC-001 (₹7,50,000) exceeds single-reviewer authority and requires two-person sign-off.",
      whatItProves:
        "Separation of duties: AP Lead provides initial review sign-off; Financial Controller executes secondary sign-off.",
      roleRequired: "CONTROLLER",
      targetRoute: "/invoices/inv_dual_eval_sec",
      icon: Lock,
    },
    {
      id: "msmed-statutory-urgency",
      number: 4,
      title: "MSMED Act 2006 Statutory 45-Day Deadline Priority",
      badge: "Statutory Compliance",
      badgeColor:
        "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-300 dark:border-rose-800",
      summary:
        "Executive exceptions queue tracking MSME supplier exposure and statutory compound interest penalty risks.",
      whatItProves:
        "Invoices sorted by statutory days remaining. Snoozing never resets legal deadlines. Reassignments logged to audit trail.",
      roleRequired: "AP_LEAD",
      targetRoute: "/invoices?stage=ACTION_REQUIRED",
      icon: Clock,
    },
    {
      id: "tamper-quarantine-vault",
      number: 5,
      title: "Quarantine & Tamper-Detection Vault",
      badge: "Forensic Security",
      badgeColor:
        "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 border-indigo-300 dark:border-indigo-800",
      summary:
        "Unreadable OCR scans, non-invoices (statements/receipts), and cryptographic duplicates quarantined automatically.",
      whatItProves:
        "SHA-256 digest fingerprinting and zero-trust ingestion boundary prevents fraudulent or corrupt documents entering the pipeline.",
      roleRequired: "AP_LEAD",
      targetRoute: "/settings/connections",
      icon: FileText,
    },
    {
      id: "immutable-audit-ledger",
      number: 6,
      title: "Forensic Immutability & Audit Trail Ledger",
      badge: "Append-Only Ledger",
      badgeColor:
        "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700",
      summary:
        "PostgreSQL trigger-enforced append-only audit ledger tracking 21 discrete action types, actor roles, and state diffs.",
      whatItProves:
        "Complete transparency for external auditors; 1-click JSON copy and before/after verification state comparisons.",
      roleRequired: "AUDITOR",
      targetRoute: "/audit",
      icon: ShieldCheck,
    },
  ];

  const handleLaunch = async (scenario: ShowcaseScenario) => {
    setOpening(true);
    setLaunchMessage(null);
    try {
      const match = scenario.targetRoute.match(/^\/invoices\/([^/?]+)/);
      if (match) {
        const record = await api.getInvoiceDetail(decodeURIComponent(match[1]));
        if (!record?.invoice?.id) throw new Error("Record unavailable");
      }
      if (onSwitchRole && scenario.roleRequired)
        onSwitchRole(scenario.roleRequired);
      navigate(scenario.targetRoute);
      onClose();
    } catch {
      setLaunchMessage(
        "This example invoice could not be opened in the current workspace. Use the inbox to choose an available record. The example outcome has not been verified.",
      );
    } finally {
      setOpening(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/70 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="showcase-modal-title"
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="product-dialog w-full max-w-4xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4 bg-slate-50/70 dark:bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  id="showcase-modal-title"
                  className="text-base font-bold text-slate-900 dark:text-white"
                >
                  Example evaluation scenarios
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 font-mono">
                  Example scenarios
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Examples describe an evaluation dataset. Links may not exist in
                this workspace; opening a scenario can navigate to existing
                records and switch the active role.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close showcase modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {launchMessage && (
          <div
            role="alert"
            className="p-4 text-sm text-rose-800 dark:text-rose-300"
          >
            <p>{launchMessage}</p>
            <button
              type="button"
              onClick={() => {
                navigate("/invoices");
                onClose();
              }}
              className="underline min-h-10"
            >
              Open invoice inbox
            </button>
          </div>
        )}
        {/* Scenarios Grid */}
        <div className="p-5 min-h-0 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {scenarios.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.id}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 hover:border-indigo-300 dark:hover:border-indigo-700/60 hover:shadow-xs transition-all flex flex-col justify-between space-y-3 group"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-mono font-bold text-indigo-600 dark:text-indigo-400">
                      Scenario #{s.number}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${s.badgeColor}`}
                    >
                      {s.badge}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5 group-hover:text-emerald-700 dark:group-hover:text-emerald-300 transition-colors">
                    <Icon className="w-4 h-4 shrink-0 text-slate-500 dark:text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
                    <span>{s.title}</span>
                  </h3>

                  <p className="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed">
                    {s.summary}
                  </p>

                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800/60 text-[11px] text-slate-500 dark:text-slate-400 space-y-1">
                    <div className="font-semibold text-slate-700 dark:text-slate-300">
                      Scenario description (not verified here):
                    </div>
                    <div>{s.whatItProves}</div>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between gap-2">
                  <span className="text-[10px] font-mono text-slate-400">
                    Role:{" "}
                    <strong className="text-slate-600 dark:text-slate-300">
                      {s.roleRequired}
                    </strong>
                  </span>
                  <button
                    disabled={opening}
                    onClick={() => void handleLaunch(s)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-600 hover:text-white dark:hover:bg-indigo-600 dark:hover:text-white font-semibold text-xs transition-colors border border-indigo-200 dark:border-indigo-800"
                  >
                    <span>{opening ? "Checking record…" : "Open example"}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer info banner */}
        <div className="p-3.5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 flex flex-col sm:flex-row items-center justify-between text-[11px] text-slate-500 gap-2">
          <span>
            Evaluator Guide: Comprehensive testing instructions in{" "}
            <code className="font-mono text-indigo-600 dark:text-indigo-400">
              docs/TESTING_AND_EVALUATION.md
            </code>
          </span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium hover:bg-slate-100 text-xs shadow-2xs"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
};

export { FeatureShowcaseModal as HRShowcaseModal };
