import { useDialogFocus } from "../hooks/useDialogFocus";
import React from "react";
import { X, Command, Navigation, CheckCircle2 } from "lucide-react";

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ShortcutItem {
  keys: string[];
  description: string;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const dialogRef = useDialogFocus(isOpen, onClose);
  if (!isOpen) return null;

  const globalShortcuts: ShortcutItem[] = [
    { keys: ["g", "then", "t"], description: "Go to Today Dashboard" },
    { keys: ["g", "then", "i"], description: "Go to Invoice Inbox" },
    { keys: ["g", "then", "a"], description: "Go to Approvals Queue" },
    { keys: ["g", "then", "u"], description: "Go to Audit Trail" },
    { keys: ["g", "then", "s"], description: "Go to Workspace Setup" },
    { keys: ["g", "then", "c"], description: "Go to Connections & Storage" },
    { keys: ["g", "then", "r"], description: "Go to Procurement Records" },
    { keys: ["g", "then", "m"], description: "Go to Team & Access" },
    { keys: ["/"], description: "Focus search / filter input" },
    { keys: ["?"], description: "Open keyboard shortcuts; Escape closes it" },
    {
      keys: ["Esc"],
      description: "Close any active modal, drawer, or help dialog",
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shortcuts-dialog-title"
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="product-dialog relative w-full max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
              <Command className="w-4 h-4" />
            </div>
            <div>
              <h2
                id="shortcuts-dialog-title"
                className="text-sm font-bold text-slate-900 dark:text-white"
              >
                Keyboard Shortcuts & Navigation
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Navigate the workspace without leaving the keyboard.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close keyboard shortcuts dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 min-h-0 overflow-y-auto space-y-6 text-xs divide-y divide-slate-100 dark:divide-slate-800/60">
          {/* Section 1: Global Navigation */}
          <div>
            <div className="flex items-center gap-2 mb-3 text-slate-800 dark:text-slate-200 font-semibold uppercase tracking-wider text-[11px]">
              <Navigation className="w-3.5 h-3.5 text-indigo-500" />
              <span>Global Navigation & Ergonomics</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {globalShortcuts.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-950/50 border border-slate-200/80 dark:border-slate-800/60"
                >
                  <span className="text-slate-600 dark:text-slate-400 text-[11px] pr-2">
                    {item.description}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    {item.keys.map((k, kIdx) =>
                      k === "then" || k === "+" ? (
                        <span
                          key={kIdx}
                          className="text-[10px] text-slate-400 px-0.5"
                        >
                          {k}
                        </span>
                      ) : (
                        <kbd
                          key={kIdx}
                          className="px-2 py-0.5 text-[11px] font-mono font-semibold text-slate-800 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded shadow-2xs"
                        >
                          {k}
                        </kbd>
                      ),
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="pt-5 text-sm text-slate-600 dark:text-slate-300">
            Use the visible invoice controls to inspect checks, read history and
            open confirmation dialogs. No keyboard shortcut submits a financial
            decision.
          </p>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 dark:bg-slate-950/80 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>
              Shortcuts are automatically paused while typing in form fields.
            </span>
          </span>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-750 font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
