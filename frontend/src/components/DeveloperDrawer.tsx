import React, { useState } from "react";
import {
  RotateCcw,
  ShieldCheck,
  Database,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import { Drawer } from "./ui/Drawer";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { api } from "../api/client";
import type { AuthenticatedUser, HealthResponse } from "../types";

interface DeveloperDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  user: AuthenticatedUser | null;
  health: HealthResponse | null;
  onSwitchRole?: (role: string) => void;
  onOpenShowcase?: () => void;
}

export const DeveloperDrawer: React.FC<DeveloperDrawerProps> = ({
  isOpen,
  onClose,
  user,
  health,
  onSwitchRole,
  onOpenShowcase,
}) => {
  const [isResetting, setIsResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const handleResetDemo = async () => {
    if (isResetting) return;
    const confirmed = window.confirm(
      "Reset evaluation workspace?\n\nThis can change corrected rates, invoice totals and approval records for all invoices in the evaluation workspace, including imported records. Checks will be re-evaluated. Continue?",
    );
    if (!confirmed) return;

    try {
      setIsResetting(true);
      setResetMessage(null);
      const res = await api.resetDemoState();
      setResetMessage(
        `Successfully reset ${res.re_evaluated_invoices_count} invoices.`,
      );
      setTimeout(() => {
        window.location.reload();
      }, 800);
    } catch (err: any) {
      setResetMessage(`Failed to reset: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Wrench className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span className="font-semibold text-slate-900 dark:text-white">
            Developer & Evaluator Controls
          </span>
        </div>
      }
      description="Evaluation tools can switch the active role or change evaluation records. Use them separately from an invoice demonstration."
      width="md"
    >
      <div className="space-y-6">
        {/* Notice Card */}
        <div className="p-3.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 text-xs text-amber-900 dark:text-amber-300">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Development tools</span>
              <p className="mt-0.5 text-amber-800 dark:text-amber-300/90 leading-relaxed">
                A development build does not establish whether workspace records
                are synthetic. Check record provenance; imported invoices may be
                live. These tools can change workspace state.
              </p>
            </div>
          </div>
        </div>

        {/* Role Simulation Switcher */}
        {onSwitchRole && user && (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                <span>Simulate User Role</span>
              </span>
              <Badge tone="info" size="sm">
                {user.role || "AP_LEAD"}
              </Badge>
            </label>
            <div className="grid grid-cols-1 gap-1.5">
              {[
                {
                  role: "AP_ASSOCIATE",
                  label: "AP Associate",
                  desc: "Can review and edit lines; cannot self-approve.",
                },
                {
                  role: "AP_LEAD",
                  label: "AP Lead",
                  desc: "Can review, correct, and execute standard approvals.",
                },
                {
                  role: "CONTROLLER",
                  label: "Financial Controller",
                  desc: "Can provide eligible independent second sign-off.",
                },
                {
                  role: "AUDITOR",
                  label: "Auditor (Read-Only)",
                  desc: "View-only access; action mutations return HTTP 403.",
                },
                {
                  role: "SYSTEM_ADMIN",
                  label: "System Admin",
                  desc: "Full administration and team access.",
                },
              ].map((item) => (
                <button
                  key={item.role}
                  type="button"
                  onClick={() => onSwitchRole(item.role)}
                  className={`p-2.5 rounded-lg border text-left text-xs transition-colors cursor-pointer ${
                    user.role === item.role
                      ? "bg-indigo-50 dark:bg-indigo-950/50 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200"
                      : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{item.label}</span>
                    {user.role === item.role && (
                      <CheckCircle2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5">
                    {item.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Demo State Reset */}
        <div className="space-y-2 pt-4 border-t border-slate-100 dark:border-slate-800">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
            <Database className="w-4 h-4 text-slate-500" />
            <span>Workspace State Reset</span>
          </label>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            For the evaluation tenant, resets corrected rates and approval
            records, recalculates invoice totals and re-evaluates checks for all
            invoices, including imported records.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleResetDemo}
            isLoading={isResetting}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            className="w-full justify-center"
          >
            {isResetting
              ? "Resetting evaluation records..."
              : "Reset evaluation records"}
          </Button>
          {resetMessage && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1 font-medium">
              {resetMessage}
            </p>
          )}
        </div>

        {/* Evaluation Showcase */}
        {onOpenShowcase && (
          <div className="space-y-2 pt-4 border-t border-slate-100 dark:border-slate-800">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <span>Interactive Evaluation Tour</span>
            </label>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Open the interactive showcase walking through Scenarios 1–6.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onClose();
                onOpenShowcase();
              }}
              rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
              className="w-full justify-center"
            >
              Launch Showcase Tour
            </Button>
          </div>
        )}

        {/* Subsystem Health Snapshot */}
        {health && (
          <div className="space-y-2 pt-4 border-t border-slate-100 dark:border-slate-800 text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300 block">
              Subsystem Health Diagnostics
            </span>
            <div className="space-y-1.5 font-mono text-[11px] bg-slate-50 dark:bg-slate-950 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Overall:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {health.overall_status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Database:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {health.subsystems?.database?.status || "OK"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Storage:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {health.subsystems?.object_storage?.status || "OK"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">SAP ERP:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {health.subsystems?.sap_erp?.status || "OK"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Auth Identity:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {health.subsystems?.identity_provider?.status || "OK"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Drawer>
  );
};
