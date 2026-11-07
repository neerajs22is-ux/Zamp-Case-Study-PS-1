import "./OnboardingSurfaces.css";
import React from "react";
import {
  FileText,
  Sparkles,
  Search,
  AlertTriangle,
  ShieldCheck,
  ArrowRight,
  Compass,
} from "lucide-react";
import { Modal, Button, Badge } from "../ui";
import { useTour } from "../../context/TourContext";

export const WelcomeModal: React.FC = () => {
  const {
    isWelcomeOpen,
    isTourActive,
    closeWelcome,
    dismissWelcomeForever,
    startTour,
  } = useTour();

  if (!isWelcomeOpen || isTourActive) return null;

  const workflowSteps = [
    {
      num: 1,
      title: "Invoice Received",
      desc: "Mailbox sync or PDF upload",
      icon: FileText,
      tone: "bg-indigo-50 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800",
    },
    {
      num: 2,
      title: "Data Extracted",
      desc: "Supplier, tax number, totals & lines",
      icon: Sparkles,
      tone: "bg-sky-50 text-sky-600 dark:bg-sky-950 dark:text-sky-400 border-sky-200 dark:border-sky-800",
    },
    {
      num: 3,
      title: "Records Checked",
      desc: "Compare the bill with order, receipt & inspection",
      icon: Search,
      tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800",
    },
    {
      num: 4,
      title: "Issues Reviewed",
      desc: "Review differences in quantity or price",
      icon: AlertTriangle,
      tone: "bg-amber-50 text-amber-600 dark:bg-amber-950 dark:text-amber-400 border-amber-200 dark:border-amber-800",
    },
    {
      num: 5,
      title: "Approval Decision",
      desc: "Internal sign-off; payment is separate",
      icon: ShieldCheck,
      tone: "bg-purple-50 text-purple-600 dark:bg-purple-950 dark:text-purple-400 border-purple-200 dark:border-purple-800",
    },
  ];

  return (
    <Modal
      className="onboarding-surface welcome-surface"
      isOpen={isWelcomeOpen}
      onClose={closeWelcome}
      maxWidth="xl"
      title={
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
              Welcome to AP Command Center
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-normal mt-0.5">
              Accounts payable (AP) is the work of reviewing supplier bills. An
              invoice is a supplier’s bill.
            </p>
          </div>
        </div>
      }
      footer={
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 w-full pt-1">
          <button
            type="button"
            onClick={closeWelcome}
            className="text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 order-3 sm:order-1 font-medium transition-colors cursor-pointer"
          >
            Skip for now
          </button>

          <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end order-1 sm:order-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={dismissWelcomeForever}
            >
              Explore on my own
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                dismissWelcomeForever();
                startTour(0);
              }}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Start Guided Tour
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-5 py-1">
        {/* Value Proposition Hero */}
        <div className="p-4 rounded-xl bg-gradient-to-r from-indigo-50/70 via-white to-sky-50/60 dark:from-indigo-950/30 dark:via-slate-900 dark:to-sky-950/20 border border-indigo-100 dark:border-indigo-900/40 text-xs">
          <div className="flex items-start gap-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
            <div className="space-y-1">
              <span className="font-semibold text-slate-900 dark:text-white text-xs block">
                From a supplier’s bill to an explained decision
              </span>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed text-[11px]">
                Review invoices against available procurement records,
                investigate failed checks and record internal sign-off when your
                role permits.
              </p>
            </div>
          </div>
        </div>

        {/* 5-Step Visual Workflow */}
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-2.5">
            The review workflow
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-2">
            {workflowSteps.map((step, idx) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.num}
                  className="p-3 rounded-xl border bg-white dark:bg-slate-900/60 flex flex-col justify-between relative group hover:border-indigo-300 dark:hover:border-indigo-800 transition-all shadow-2xs"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div
                        className={`welcome-step-icon w-7 h-7 rounded-lg border flex items-center justify-center ${step.tone}`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-[10px] font-mono font-bold text-slate-400">
                        0{step.num}
                      </span>
                    </div>
                    <span className="font-semibold text-slate-800 dark:text-slate-200 block text-xs">
                      {step.title}
                    </span>
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 block mt-0.5 leading-snug">
                      {step.desc}
                    </span>
                  </div>

                  {/* Desktop connector arrow */}
                  {idx < workflowSteps.length - 1 && (
                    <div className="hidden sm:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-300 dark:text-slate-700 pointer-events-none">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Non-Technical Clarification Callout */}
        <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
            The tour may display live workspace data. It does not submit a
            financial decision.
          </span>
          <Badge tone="neutral" size="sm">
            Optional guided tour
          </Badge>
        </div>
      </div>
    </Modal>
  );
};
