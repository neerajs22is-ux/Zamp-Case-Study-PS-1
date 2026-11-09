import React, { useState, useEffect } from "react";
import { useLocation, NavLink } from "react-router-dom";
import { Menu, Keyboard, Sparkles, Wrench, HelpCircle } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ThemeToggle } from "./ThemeToggle";
import { KeyboardShortcutsModal } from "./KeyboardShortcutsModal";
import { FeatureShowcaseModal } from "./FeatureShowcaseModal";
import { DeveloperDrawer } from "./DeveloperDrawer";
import { WelcomeModal, GuidedTour, ContextualHelpDrawer } from "./onboarding";
import { useTour } from "../context/TourContext";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { api } from "../api/client";
import type { AuthenticatedUser, HealthResponse } from "../types";
import "./AppShell.css";

interface AppShellProps {
  user: AuthenticatedUser | null;
  health: HealthResponse | null;
  onLogout?: () => void;
  children: React.ReactNode;
  onSwitchRole?: (role: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({
  user,
  health,
  onLogout,
  children,
  onSwitchRole,
}) => {
  const { openHelp } = useTour();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [showcaseOpen, setShowcaseOpen] = useState(false);
  const [devDrawerOpen, setDevDrawerOpen] = useState(false);
  const [navCounts, setNavCounts] = useState<{
    exceptions?: number;
    approvals?: number;
  }>({});
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;
    const fetchCounts = async () => {
      try {
        const [metrics, exceptions] = await Promise.allSettled([
          api.getDashboardMetrics(),
          api.getExceptions(),
        ]);
        if (isMounted)
          setNavCounts({
            exceptions:
              exceptions.status === "fulfilled" && !exceptions.value.message
                ? exceptions.value.total_count
                : undefined,
            approvals:
              metrics.status === "fulfilled" &&
              metrics.value.status === "active"
                ? (metrics.value.summary as any)?.pending_second_approval
                : undefined,
          });
      } catch {
        // Silently skip if session not ready
      }
    };
    fetchCounts();
    const interval = setInterval(fetchCounts, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [location.pathname]);

  // Global key listener for Developer Drawer (Ctrl+Shift+D)
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (
        (e.ctrlKey || e.metaKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "d"
      ) {
        e.preventDefault();
        setDevDrawerOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  // Register global shortcuts (? for help, g sequences for navigation)
  useKeyboardShortcuts({
    onToggleShortcutsHelp: () => openHelp("faq"),
    onEscape: () => {
      setShortcutsOpen(false);
      setSidebarOpen(false);
      setDevDrawerOpen(false);
    },
  });

  // Determine current page title
  const getPageTitle = (pathname: string) => {
    if (pathname.startsWith("/today")) return "Today";
    if (pathname.startsWith("/setup")) return "Setup Guide";
    if (pathname.startsWith("/invoices/")) return "Invoice Review";
    if (pathname.startsWith("/invoices")) return "Invoices";
    if (pathname.startsWith("/exceptions")) return "Exceptions";
    if (pathname.startsWith("/approvals")) return "Approvals Queue";
    if (pathname.startsWith("/audit")) return "Audit Trail";
    if (pathname.startsWith("/settings/connections"))
      return "Connections & Storage";
    if (pathname.startsWith("/settings/reference-data"))
      return "Procurement Master Records";
    if (pathname.startsWith("/settings/team")) return "Team & Access";
    return "Dashboard";
  };

  const isDevMode = !import.meta.env.PROD;

  return (
    <div className="app-shell min-h-screen bg-slate-50 dark:bg-[#17191c] text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-150">
      <a className="shell-skip-link" href="#workspace-content">
        Skip to workspace content
      </a>
      {/* Global Sidebar */}
      <Sidebar
        user={user}
        health={health}
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        exceptionCount={navCounts.exceptions}
        approvalCount={navCounts.approvals}
        onOpenDevDrawer={isDevMode ? () => setDevDrawerOpen(true) : undefined}
      />

      {/* Main Content Column (offset by 64px on lg viewports for the fixed sidebar) */}
      <div className="lg:pl-64 flex flex-col flex-1 min-w-0">
        {/* Top Header Bar */}
        <header
          className="shell-header sticky top-0 z-30 h-14 border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/90 backdrop-blur-md shadow-2xs flex items-center justify-between px-4 sm:px-6 lg:px-8 transition-colors"
          role="banner"
        >
          {/* Left: Mobile hamburger & breadcrumbs */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 lg:hidden cursor-pointer"
              aria-label="Open sidebar menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-1.5 text-xs sm:text-sm">
              {location.pathname.startsWith("/invoices/") ? (
                <>
                  <NavLink
                    to="/invoices"
                    className="text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400 transition-colors font-medium"
                  >
                    Invoices
                  </NavLink>
                  <span className="text-slate-300 dark:text-slate-700">/</span>
                  <span className="font-semibold text-slate-900 dark:text-white font-mono truncate max-w-[100px] xs:max-w-[160px] sm:max-w-xs block" title={location.pathname.replace("/invoices/", "")}>
                    {location.pathname.replace("/invoices/", "")}
                  </span>
                </>
              ) : location.pathname.startsWith("/settings/") ? (
                <>
                  <span className="text-slate-500 dark:text-slate-400 font-medium">
                    Management
                  </span>
                  <span className="text-slate-300 dark:text-slate-700">/</span>
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {getPageTitle(location.pathname)}
                  </span>
                </>
              ) : (
                <span className="font-semibold text-slate-900 dark:text-white">
                  {getPageTitle(location.pathname)}
                </span>
              )}
            </div>
          </div>

          {/* Right Controls: Operational Boundary, Showcase, Evaluator Tools, Shortcuts, Theme */}
          <div className="flex items-center gap-2 sm:gap-2.5">
            {/* Operational Boundary Badge (Informs Non-Technical Buyers What the System Does & Does NOT Do) */}
            <div
              className="shell-boundary hidden lg:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/50 select-none"
              title="Accounts payable (AP) review records internal decisions. It does not send bank payments."
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              <span>AP review only • Does not send payments</span>
            </div>

            {/* Evaluator Tools Quarantined Trigger Pill */}
            {isDevMode && (
              <button
                type="button"
                onClick={() => setDevDrawerOpen(true)}
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer"
                title="Open evaluator and developer controls"
                aria-label="Open evaluator and developer controls"
              >
                <Wrench className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span className="hidden sm:inline">Evaluator Tools</span>
              </button>
            )}

            {/* AP Command Center Sandbox Link */}
            <a
              href="/sandbox"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors cursor-pointer"
              title="Switch to the Simplified AP Decision Sandbox experience"
              aria-label="Open Sandbox Experience"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
              <span className="hidden sm:inline">Sandbox</span>
              <span className="sm:hidden">Sandbox</span>
            </a>

            {/* Interactive Showcase Tour Launcher */}
            <button
              onClick={() => setShowcaseOpen(true)}
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              title="Open Evaluation Scenarios Tour"
              aria-label="Open evaluation scenarios tour"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span className="hidden sm:inline">Example scenarios</span>
            </button>

            {/* Keyboard Shortcuts Trigger Button */}
            <button
              onClick={() => setShortcutsOpen(true)}
              className="hidden md:inline-flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg transition-colors cursor-pointer"
              title="Keyboard Shortcuts (Press ?)"
              aria-label="Open keyboard shortcuts cheat sheet"
            >
              <Keyboard className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">Shortcuts</span>
            </button>

            {/* Contextual Help Trigger Button */}
            <button
              onClick={() => openHelp("screen")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/80 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors shadow-2xs cursor-pointer"
              title="Open AP Assistant & Contextual Help (?)"
              aria-label="Open AP assistant and contextual help"
            >
              <HelpCircle className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span className="hidden sm:inline">Help</span>
            </button>

            {/* High-Contrast Light / Dark Theme Switcher */}
            <ThemeToggle />
          </div>
        </header>

        {/* Dynamic Route Viewport */}
        <main
          id="workspace-content"
          tabIndex={-1}
          className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5"
          role="main"
        >
          {children}
        </main>

        {/* Keyboard Shortcuts Help Dialog */}
        <KeyboardShortcutsModal
          isOpen={shortcutsOpen}
          onClose={() => setShortcutsOpen(false)}
        />

        {/* HR Showcase Tour Dialog */}
        <FeatureShowcaseModal
          isOpen={showcaseOpen}
          onClose={() => setShowcaseOpen(false)}
          onSwitchRole={onSwitchRole}
        />

        {/* Developer & Evaluator Slide-Over Drawer */}
        <DeveloperDrawer
          isOpen={devDrawerOpen}
          onClose={() => setDevDrawerOpen(false)}
          user={user}
          health={health}
          onSwitchRole={onSwitchRole}
          onOpenShowcase={() => setShowcaseOpen(true)}
        />

        {/* Onboarding & Assistant Overlays */}
        <WelcomeModal />
        <GuidedTour />
        <ContextualHelpDrawer />

        {/* Global Footer */}
        <footer className="shell-footer border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/40 py-3 text-center text-xs text-slate-500 dark:text-slate-400">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>
              Autonomous AP Command Center &copy; 2026. Enterprise Financial
              Operations.
            </span>
            <span className="text-[11px] font-mono text-slate-400 dark:text-slate-600">
              Build: {isDevMode ? "Development" : "Production"}
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
};
