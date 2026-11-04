import React, { useState, useEffect } from 'react';
import { useLocation, NavLink } from 'react-router-dom';
import { Menu, Keyboard, Sparkles, Wrench } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { ThemeToggle } from './ThemeToggle';
import { KeyboardShortcutsModal } from './KeyboardShortcutsModal';
import { HRShowcaseModal } from './HRShowcaseModal';
import { DeveloperDrawer } from './DeveloperDrawer';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { api } from '../api/client';
import type { AuthenticatedUser, HealthResponse } from '../types';

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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [showcaseOpen, setShowcaseOpen] = useState(false);
  const [devDrawerOpen, setDevDrawerOpen] = useState(false);
  const [navCounts, setNavCounts] = useState<{ exceptions: number; approvals: number }>({ exceptions: 0, approvals: 0 });
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;
    const fetchCounts = async () => {
      try {
        const metrics = await api.getDashboardMetrics();
        if (isMounted && metrics?.summary) {
          const exceptions = metrics.summary.open_exceptions || 0;
          const ready = (metrics.summary as any).ready_to_approve || 0;
          const second = (metrics.summary as any).pending_second_approval || 0;
          setNavCounts({
            exceptions: exceptions + ready,
            approvals: second,
          });
        }
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
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        setDevDrawerOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Register global shortcuts (? for help, g sequences for navigation)
  useKeyboardShortcuts({
    onToggleShortcutsHelp: () => setShortcutsOpen((prev) => !prev),
    onEscape: () => {
      setShortcutsOpen(false);
      setSidebarOpen(false);
      setDevDrawerOpen(false);
    },
  });

  // Determine current page title
  const getPageTitle = (pathname: string) => {
    if (pathname.startsWith('/today')) return 'Today';
    if (pathname.startsWith('/setup')) return 'Setup Guide';
    if (pathname.startsWith('/invoices/')) return 'Invoice Review';
    if (pathname.startsWith('/invoices')) return 'Invoices';
    if (pathname.startsWith('/approvals')) return 'Approvals Queue';
    if (pathname.startsWith('/audit')) return 'Audit Trail';
    if (pathname.startsWith('/settings/connections')) return 'Connections & Storage';
    if (pathname.startsWith('/settings/reference-data')) return 'Procurement Master Records';
    if (pathname.startsWith('/settings/team')) return 'Team & Access';
    return 'Dashboard';
  };

  const isDevMode = !import.meta.env.PROD;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#090d16] text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-150">
      {/* Global Sidebar */}
      <Sidebar
        user={user}
        health={health}
        onLogout={onLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        invoiceCount={navCounts.exceptions}
        approvalCount={navCounts.approvals}
        onOpenDevDrawer={isDevMode ? () => setDevDrawerOpen(true) : undefined}
      />

      {/* Main Content Column (offset by 64px on lg viewports for the fixed sidebar) */}
      <div className="lg:pl-64 flex flex-col flex-1 min-w-0">
        {/* Top Header Bar */}
        <header
          className="sticky top-0 z-30 h-14 border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/90 backdrop-blur-md shadow-2xs flex items-center justify-between px-4 sm:px-6 lg:px-8 transition-colors"
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
              {location.pathname.startsWith('/invoices/') ? (
                <>
                  <NavLink
                    to="/invoices"
                    className="text-slate-500 hover:text-indigo-600 dark:text-slate-400 dark:hover:text-indigo-400 transition-colors font-medium"
                  >
                    Invoices
                  </NavLink>
                  <span className="text-slate-300 dark:text-slate-700">/</span>
                  <span className="font-semibold text-slate-900 dark:text-white font-mono">
                    {location.pathname.replace('/invoices/', '')}
                  </span>
                </>
              ) : location.pathname.startsWith('/settings/') ? (
                <>
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Management</span>
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
              className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/50 select-none"
              title="Autonomous AP Review: Verifies invoices against PO, GRN, and QC. Approvals represent internal review sign-off; bank disbursements and ERP General Ledger postings are strictly performed downstream by treasury."
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
              <span>AP Sign-Off Only • No Bank Disbursements</span>
            </div>

            {/* Evaluator Tools Quarantined Trigger Pill */}
            {isDevMode && (
              <button
                type="button"
                onClick={() => setDevDrawerOpen(true)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 transition-colors cursor-pointer"
                title="Open Evaluator & Developer Controls (Ctrl+Shift+D)"
              >
                <Wrench className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span className="hidden sm:inline">Evaluator Tools</span>
              </button>
            )}

            {/* Interactive Showcase Tour Launcher */}
            <button
              onClick={() => setShowcaseOpen(true)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/80 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors shadow-2xs cursor-pointer"
              title="Open Evaluation Scenarios Tour"
              aria-label="Open evaluation scenarios tour"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span className="hidden sm:inline">Showcase Tour</span>
            </button>

            {/* Keyboard Shortcuts Trigger Button */}
            <button
              onClick={() => setShortcutsOpen(true)}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg transition-colors cursor-pointer"
              title="Keyboard Shortcuts (Press ?)"
              aria-label="Open keyboard shortcuts cheat sheet"
            >
              <Keyboard className="w-3.5 h-3.5" />
              <kbd className="font-mono text-[10px] font-semibold bg-white dark:bg-slate-800 px-1 py-0.2 rounded border border-slate-300 dark:border-slate-700">?</kbd>
            </button>

            {/* High-Contrast Light / Dark Theme Switcher */}
            <ThemeToggle />
          </div>
        </header>

        {/* Dynamic Route Viewport */}
        <main
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
        <HRShowcaseModal
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

        {/* Global Footer */}
        <footer className="border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/40 py-3 text-center text-xs text-slate-500 dark:text-slate-400">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>Autonomous AP Command Center &copy; 2026. Enterprise Financial Operations.</span>
            <span className="text-[11px] font-mono text-slate-400 dark:text-slate-600">
              Environment: {isDevMode ? 'Local Dev / Evaluation Mode' : 'Production'}
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
};
