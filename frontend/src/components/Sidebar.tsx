import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  CheckCircle2,
  ShieldCheck,
  Link2,
  Database,
  Users,
  Building2,
  LogOut,
  X,
  ChevronRight
} from 'lucide-react';
import type { AuthenticatedUser, HealthResponse } from '../types';

interface SidebarProps {
  user: AuthenticatedUser | null;
  health: HealthResponse | null;
  onLogout?: () => void;
  isOpen: boolean;
  onClose: () => void;
  invoiceCount?: number;
  approvalCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  user,
  health,
  onLogout,
  isOpen,
  onClose,
  invoiceCount,
  approvalCount,
}) => {
  const navigate = useNavigate();

  // Role permissions based on server RBAC rules
  const isAuditor = user?.role === 'AUDITOR';
  const isAdminOrController = user?.role === 'SYSTEM_ADMIN' || user?.role === 'CONTROLLER';
  const isLead = user?.role === 'AP_LEAD';
  const canAccessTeam = isAdminOrController || isLead;

  const navItems = [
    { to: '/today', label: 'Today', icon: LayoutDashboard },
    { to: '/invoices', label: 'Invoices', icon: FileText, badge: invoiceCount },
    ...(!isAuditor ? [{ to: '/approvals', label: 'Approvals', icon: CheckCircle2, badge: approvalCount }] : []),
    { to: '/audit', label: 'Audit', icon: ShieldCheck },
  ];

  const settingsItems = [
    { to: '/setup', label: 'Setup Checklist', icon: CheckCircle2 },
    { to: '/settings/connections', label: 'Connections & Storage', icon: Link2 },
    { to: '/settings/reference-data', label: 'Procurement Records', icon: Database },
    ...(canAccessTeam ? [{ to: '/settings/team', label: 'Team & Access', icon: Users }] : []),
  ];

  const getHealthBadge = () => {
    const status = health?.overall_status;
    switch (status) {
      case 'READY':
        return {
          text: 'All systems normal',
          className: 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-950/40 dark:border-emerald-800/50',
          dot: 'bg-emerald-500',
        };
      case 'SETUP_REQUIRED':
        return {
          text: 'Setup required',
          className: 'text-sky-700 bg-sky-50 border-sky-200 dark:text-sky-400 dark:bg-sky-950/40 dark:border-sky-800/50',
          dot: 'bg-sky-500',
        };
      case 'BLOCKED':
        return {
          text: 'Subsystem blocked',
          className: 'text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-400 dark:bg-rose-950/40 dark:border-rose-800/50',
          dot: 'bg-rose-500',
        };
      default:
        return {
          text: 'Checking status...',
          className: 'text-slate-600 bg-slate-100 border-slate-200 dark:text-slate-400 dark:bg-slate-800/40 dark:border-slate-700',
          dot: 'bg-slate-400 animate-pulse',
        };
    }
  };

  const healthBadge = getHealthBadge();

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs lg:hidden"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Sidebar Navigation"
        role="navigation"
      >
        {/* Brand & Workspace Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white tracking-wider text-xs shadow-xs">
                AP
              </div>
              <div>
                <span className="font-semibold text-sm text-slate-900 dark:text-white tracking-tight block">
                  AP Command Center
                </span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 tracking-wider uppercase font-medium">
                  Autonomous Engine
                </span>
              </div>
            </div>

            {/* Mobile close button */}
            <button
              onClick={onClose}
              className="p-1 rounded-md text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 lg:hidden"
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Workspace Pill */}
          <div className="mt-3.5 p-2 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Building2 className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0" />
              <div className="min-w-0">
                <span className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate block">
                  {user?.org_name || user?.org_id || 'Primary Workspace'}
                </span>
                <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block truncate">
                  ID: {user?.org_id || 'org_default'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Primary Navigation List */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {/* Main Group */}
          <div className="space-y-1">
            <div className="px-3 pb-1 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Operations
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => {
                    if (window.innerWidth < 1024) onClose();
                  }}
                  className={({ isActive }) =>
                    `group relative flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-semibold shadow-2xs before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-1 before:rounded-r-md before:bg-indigo-600 dark:before:bg-indigo-400'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900/80 hover:text-slate-900 dark:hover:text-white'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <div className="flex items-center gap-2.5 min-w-0">
                        <Icon
                          className={`w-4 h-4 shrink-0 transition-colors ${
                            isActive
                              ? 'text-indigo-600 dark:text-indigo-400'
                              : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300'
                          }`}
                        />
                        <span className="truncate">{item.label}</span>
                      </div>
                      {typeof item.badge === 'number' && item.badge > 0 && (
                        <span
                          className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold tabular-nums border ${
                            item.label === 'Invoices'
                              ? 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/80 dark:text-amber-300 dark:border-amber-800'
                              : 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950/80 dark:text-purple-300 dark:border-purple-800'
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>

          {/* Settings & Admin Group */}
          <div className="space-y-1 pt-2 border-t border-slate-100 dark:border-slate-900">
            <div className="px-3 pb-1 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
              Management
            </div>
            {settingsItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => {
                    if (window.innerWidth < 1024) onClose();
                  }}
                  className={({ isActive }) =>
                    `group relative flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-semibold shadow-2xs before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-1 before:rounded-r-md before:bg-indigo-600 dark:before:bg-indigo-400'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900/80 hover:text-slate-900 dark:hover:text-white'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`w-4 h-4 shrink-0 transition-colors ${
                          isActive
                            ? 'text-indigo-600 dark:text-indigo-400'
                            : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300'
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </div>
                  )}
                </NavLink>
              );
            })}
          </div>
        </div>

        {/* Sidebar Footer: Health, Onboarding & User */}
        <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-2.5 bg-slate-50/50 dark:bg-slate-950">
          {/* Health Pill Indicator */}
          <button
            type="button"
            onClick={() => {
              navigate('/settings/connections');
              if (window.innerWidth < 1024) onClose();
            }}
            className={`w-full px-2.5 py-1.5 rounded-lg border text-left text-xs font-medium flex items-center justify-between transition-colors ${healthBadge.className}`}
          >
            <div className="flex items-center gap-2 truncate">
              <span className={`w-2 h-2 rounded-full shrink-0 ${healthBadge.dot}`} />
              <span className="truncate">{healthBadge.text}</span>
            </div>
            <ChevronRight className="w-3.5 h-3.5 opacity-60 shrink-0" />
          </button>

          {/* User Profile Card */}
          {user && (
            <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2 shadow-2xs">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-7 h-7 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 flex items-center justify-center font-bold text-xs uppercase shrink-0">
                  {user.name ? user.name.slice(0, 2) : user.email.slice(0, 2)}
                </div>
                <div className="min-w-0">
                  <span className="text-xs font-semibold text-slate-900 dark:text-white truncate block">
                    {user.name || user.email.split('@')[0]}
                  </span>
                  <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 truncate block">
                    {user.role || 'MEMBER'}
                  </span>
                </div>
              </div>

              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  className="p-1.5 rounded-md text-slate-400 hover:text-red-600 dark:text-slate-500 dark:hover:text-red-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                  aria-label="Sign out"
                  title="Sign out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
