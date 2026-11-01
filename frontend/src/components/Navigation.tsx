import React from 'react';
import { 
  LayoutDashboard, 
  Link2, 
  Inbox, 
  AlertTriangle, 
  Database, 
  ShieldCheck,
  Building2,
  Lock,
  UserCheck,
  Users,
  LogOut
} from 'lucide-react';
import type { AuthenticatedUser, HealthResponse } from '../types';

interface NavigationProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
  user: AuthenticatedUser | null;
  health: HealthResponse | null;
  onLogout?: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  currentRoute,
  onNavigate,
  user,
  health,
  onLogout,
}) => {
  const isAdmin = user && (user.role === 'SYSTEM_ADMIN' || user.role === 'CONTROLLER' || user.role === 'AP_LEAD');

  const routes = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'connections', label: 'Connections', icon: Link2 },
    { id: 'inbox', label: 'Invoice Inbox', icon: Inbox },
    { id: 'exceptions', label: 'Exceptions Queue', icon: AlertTriangle },
    { id: 'source-records', label: 'ERP Source Records', icon: Database },
    { id: 'audit', label: 'Audit Trail', icon: ShieldCheck },
    ...(isAdmin ? [{ id: 'access-management', label: 'Team & Access', icon: Users }] : []),
  ];

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'READY':
      case 'CONNECTED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'DEGRADED':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'SETUP_REQUIRED':
      case 'NOT_CONFIGURED':
        return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
      default:
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    }
  };

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
      {/* Top Banner: Enterprise Identity & Health Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center justify-between border-b border-slate-900/60 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-indigo-600 flex items-center justify-center font-bold text-white tracking-wider text-xs shadow-sm">
              AP
            </div>
            <span className="font-semibold text-slate-100 tracking-tight text-sm">
              AP Command Center
            </span>
          </div>
          <span className="text-slate-600">/</span>
          <div className="flex items-center gap-1.5 text-slate-400">
            <Building2 className="w-3.5 h-3.5 text-slate-500" />
            <span className="font-mono text-slate-300">
              {user?.org_name || user?.org_id || 'Zetwerk Manufacturing'}
            </span>
            <span className="text-slate-600 text-[10px] bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
              Co. Code 1000
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Health Pill */}
          <div 
            onClick={() => onNavigate('connections')}
            className={`cursor-pointer px-2.5 py-0.5 rounded-full border text-[11px] font-medium flex items-center gap-1.5 transition-colors ${getStatusColor(health?.overall_status)}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
            System: {health?.overall_status || 'CHECKING...'}
          </div>

          {/* Genuine Authenticated User Profile */}
          {user ? (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-md">
                <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-slate-300 font-mono text-[11px]">{user.email}</span>
                {user.role ? (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    {user.role}
                  </span>
                ) : (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                    UNPROVISIONED
                  </span>
                )}
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  title="Sign Out"
                  className="flex items-center gap-1 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-rose-400 px-2 py-1 rounded-md text-[11px] transition-colors"
                >
                  <LogOut className="w-3 h-3" />
                  <span>Logout</span>
                </button>
              )}
            </div>
          ) : (
            <div 
              onClick={() => onNavigate('connections')}
              className="cursor-pointer flex items-center gap-1.5 bg-slate-900 border border-amber-800/40 px-2.5 py-1 rounded-md text-amber-300 hover:bg-slate-800 text-[11px]"
            >
              <Lock className="w-3 h-3 text-amber-400" />
              <span>IdP Sign-In Setup Required</span>
            </div>
          )}
        </div>
      </div>

      {/* Primary Route Navigation */}
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-1 overflow-x-auto py-1">
        {routes.map((r) => {
          const Icon = r.icon;
          const isActive = currentRoute === r.id;
          return (
            <button
              key={r.id}
              onClick={() => onNavigate(r.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                isActive
                  ? 'bg-slate-800/80 text-white shadow-sm border border-slate-700/60'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
              {r.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
};
