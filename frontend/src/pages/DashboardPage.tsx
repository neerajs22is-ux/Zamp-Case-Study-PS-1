import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  RefreshCw, 
  ArrowRight, 
  ShieldAlert, 
  ChevronRight
} from 'lucide-react';
import { api } from '../api/client';
import { 
  PageHeader, 
  Card, 
  CardHeader, 
  CardTitle, 
  CardDescription, 
  CardContent, 
  Button, 
  Badge, 
  LoadingState, 
  ErrorState, 
  EmptyState 
} from '../components/ui';
import type { AuthenticatedUser, DashboardMetrics, HealthResponse } from '../types';

interface DashboardPageProps {
  onNavigate?: (route: string) => void;
  currentUser?: AuthenticatedUser | null;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ currentUser, onNavigate }) => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [exposure, setExposure] = useState<any | null>(null);
  const [exceptions, setExceptions] = useState<any[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [recentAudits, setRecentAudits] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAuditor = currentUser?.role === 'AUDITOR';

  const loadAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, exceptionsData, healthData, auditData, exposureData] = await Promise.allSettled([
        api.getDashboardMetrics(),
        api.getExceptions(),
        api.getHealth(),
        api.getAudit({ limit: 6 }),
        api.getDashboardExposure(),
      ]);

      if (metricsData.status === 'fulfilled') setMetrics(metricsData.value);
      if (exceptionsData.status === 'fulfilled') setExceptions(exceptionsData.value.items || []);
      if (healthData.status === 'fulfilled') setHealth(healthData.value);
      if (auditData.status === 'fulfilled') setRecentAudits((auditData.value.items || []).slice(0, 5));
      if (exposureData.status === 'fulfilled') setExposure(exposureData.value);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve operational metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const formatINR = (val?: number | null) => {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const navigateTo = (route: string) => {
    if (onNavigate) {
      onNavigate(route);
    } else {
      navigate(route);
    }
  };

  if (loading && !metrics) {
    return <LoadingState label="Loading operational dashboard..." size="lg" className="py-24" />;
  }

  if (error && !metrics) {
    return <ErrorState message={error} onRetry={loadAllData} className="my-12" />;
  }

  const summary = metrics?.summary;
  const needsActionCount = summary?.open_exceptions || exceptions.length || 0;
  const readyToPayCount = (summary as any)?.ready_to_approve || 0;
  const secondApprovalCount = (summary as any)?.pending_second_approval || 0;
  const totalApprovedINR = exposure?.cleared_for_erp_inr || 0;
  const blockedLiabilityINR = exposure?.total_blocked_liability_inr || 0;
  const autoApprovedCount = (summary as any)?.auto_approved_count || 0;
  const totalInvoices = summary?.total_invoices || (needsActionCount + readyToPayCount + 1);
  const automationRate = totalInvoices > 0 ? Math.round((autoApprovedCount / totalInvoices) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* 1. Page Header */}
      <PageHeader
        title="Today's AP Operations"
        description="Autonomous verification pulse, pending invoice workload, and financial exposure status."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={loadAllData}
              isLoading={loading}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigateTo('/invoices')}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Go to Inbox
            </Button>
          </div>
        }
      />

      {/* 2. Zone 1: The Daily Triad (Top KPI Bar) */}
      <div data-tour="today-kpi-bar" className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Needs Action Today */}
        <Card
          variant="interactive"
          onClick={() => navigateTo('/invoices?stage=ACTION_REQUIRED')}
          className="border-amber-200/80 dark:border-amber-900/50 hover:border-amber-400 dark:hover:border-amber-700 bg-gradient-to-br from-white to-amber-50/30 dark:from-slate-900 dark:to-amber-950/20"
        >
          <div className="p-4 sm:p-5 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                Needs Attention
              </span>
              <Badge tone="warning" size="sm" dot>
                Action Required
              </Badge>
            </div>
            <div className="my-3">
              <div className="text-3xl font-bold font-mono text-slate-900 dark:text-white tabular-nums">
                {needsActionCount}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Value at Risk: <span className="font-semibold font-mono text-amber-700 dark:text-amber-300">{formatINR(blockedLiabilityINR)}</span>
              </p>
            </div>
            <div className="flex items-center justify-between text-xs font-medium text-amber-700 dark:text-amber-400 pt-2 border-t border-amber-100 dark:border-amber-900/40">
              <span>Review discrepant bills</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </Card>

        {/* Card 2: Ready for Sign-Off & Payment */}
        <Card
          variant="interactive"
          onClick={() => navigateTo(isAuditor ? '/invoices' : '/approvals')}
          className="border-emerald-200/80 dark:border-emerald-900/50 hover:border-emerald-400 dark:hover:border-emerald-700 bg-gradient-to-br from-white to-emerald-50/30 dark:from-slate-900 dark:to-emerald-950/20"
        >
          <div className="p-4 sm:p-5 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                Ready to Pay
              </span>
              <Badge tone="success" size="sm" dot>
                {secondApprovalCount > 0 ? `${secondApprovalCount} Dual Approvals` : 'Clean Matches'}
              </Badge>
            </div>
            <div className="my-3">
              <div className="text-3xl font-bold font-mono text-slate-900 dark:text-white tabular-nums">
                {readyToPayCount + secondApprovalCount}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Verified Sign-Offs: <span className="font-semibold font-mono text-emerald-700 dark:text-emerald-300">{formatINR(totalApprovedINR)}</span>
              </p>
            </div>
            <div className="flex items-center justify-between text-xs font-medium text-emerald-700 dark:text-emerald-400 pt-2 border-t border-emerald-100 dark:border-emerald-900/40">
              <span>{isAuditor ? 'View verified bills' : 'Authorize payments'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </Card>

        {/* Card 3: Autonomous Automation Rate */}
        <Card
          variant="interactive"
          onClick={() => navigateTo('/audit')}
          className="border-indigo-200/80 dark:border-indigo-900/50 hover:border-indigo-400 dark:hover:border-indigo-700 bg-gradient-to-br from-white to-indigo-50/30 dark:from-slate-900 dark:to-indigo-950/20"
        >
          <div className="p-4 sm:p-5 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">
                Straight-Through Touchless
              </span>
              <Badge tone="info" size="sm">
                Efficiency
              </Badge>
            </div>
            <div className="my-3">
              <div className="text-3xl font-bold font-mono text-indigo-600 dark:text-indigo-400 tabular-nums">
                {automationRate}%
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Total Processing Volume: <span className="font-semibold font-mono text-slate-700 dark:text-slate-300">{totalInvoices} Invoices</span>
              </p>
            </div>
            <div className="flex items-center justify-between text-xs font-medium text-indigo-700 dark:text-indigo-400 pt-2 border-t border-indigo-100 dark:border-indigo-900/40">
              <span>View audit verification trail</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </Card>
      </div>

      {/* 3. Zone 2: Priority Action Queue */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <CardTitle>Invoices Requiring Attention</CardTitle>
            <CardDescription>
              Prioritized by discrepancy severity and payment due date.
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigateTo('/invoices?stage=ACTION_REQUIRED')}
            rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
          >
            View all ({exceptions.length})
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {exceptions.length === 0 ? (
            <EmptyState
              title="All caught up!"
              description="No open invoice discrepancies or blocked policy checks. All received bills are reconciled."
              className="py-10 border-none bg-transparent"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 dark:bg-slate-850/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Invoice</th>
                    <th className="px-4 py-3">Supplier</th>
                    <th className="px-4 py-3">Billed Amount</th>
                    <th className="px-4 py-3">Key Discrepancy</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                  {exceptions.slice(0, 5).map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => navigateTo(`/invoices/${item.invoice_id}`)}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors cursor-pointer group"
                    >
                      <td className="px-4 py-3 font-mono font-medium text-slate-900 dark:text-white">
                        {item.invoice_number || item.invoice_id}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">
                          {item.vendor_name || 'Unregistered Supplier'}
                        </div>
                        <div className="text-[10px] text-slate-400">PO: {item.po_number || 'None'}</div>
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                        {formatINR(item.total_amount)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone="error" size="sm">
                          {item.exception_type ? item.exception_type.replace(/_/g, ' ') : 'Verification Variance'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigateTo(`/invoices/${item.invoice_id}`);
                          }}
                          rightIcon={<ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />}
                        >
                          Review
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 4. Zone 3: Two Balanced Columns (Financial Exposure & Recent Audit Stream) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Statutory Compliance & Exposure */}
        <Card>
          <CardHeader>
            <CardTitle>Financial Liability & Compliance Overview</CardTitle>
            <CardDescription>
              Operational liabilities and statutory MSME compliance tracking.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200/80 dark:border-slate-800">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                  Cleared for ERP Posting
                </span>
                <span className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1 block">
                  {formatINR(exposure?.cleared_for_erp_inr || 0)}
                </span>
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  {exposure?.cleared_invoices_count || 0} approved bills
                </span>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200/80 dark:border-slate-800">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                  Blocked Exceptions
                </span>
                <span className="text-lg font-bold font-mono text-rose-600 dark:text-rose-400 mt-1 block">
                  {formatINR(exposure?.total_blocked_liability_inr || 0)}
                </span>
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  {exposure?.blocked_invoices_count || 0} bills on hold
                </span>
              </div>
            </div>

            {/* MSME Statutory Invariant Box */}
            <div className="p-3.5 rounded-lg bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 flex items-start gap-3">
              <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs">
                <span className="font-semibold text-amber-900 dark:text-amber-300 block">
                  Statutory MSME Compliance (45-Day Mandate)
                </span>
                <p className="text-amber-800 dark:text-amber-300/80 mt-0.5 leading-relaxed">
                  {exposure?.statutory_msme_count || 0} verified MSME invoices totaling{' '}
                  <span className="font-semibold font-mono">{formatINR(exposure?.statutory_msme_verified_due_inr || 0)}</span>{' '}
                  require timely settlement within statutory payment windows.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-800">
              <span>Overall Subsystem Health:</span>
              <Badge tone={health?.overall_status === 'READY' ? 'success' : 'warning'} size="sm" dot>
                {health?.overall_status === 'READY' ? 'All Systems Operational' : 'Setup Required'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Right Column: Immutable Audit Feed */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Activity & Audit Trail</CardTitle>
              <CardDescription>
                Cryptographically tracked events and human reviews.
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => navigateTo('/audit')}
              rightIcon={<ChevronRight className="w-3 h-3" />}
            >
              Full Ledger
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {recentAudits.length === 0 ? (
              <EmptyState
                title="No recent events"
                description="Audit events will appear as invoices are processed, corrected, or approved."
                className="py-10 border-none bg-transparent"
              />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-850 text-xs">
                {recentAudits.map((event) => (
                  <div key={event.id} className="p-3.5 sm:px-5 flex items-start justify-between gap-3 hover:bg-slate-50/50 dark:hover:bg-slate-850/40 transition-colors">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300 shrink-0 font-bold text-[10px] uppercase">
                        {(event.actor_name || event.actor_id || 'SYS').slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <span className="font-semibold text-slate-900 dark:text-white block truncate">
                          {event.description || event.action?.replace(/_/g, ' ')}
                        </span>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          <span>{event.actor_name || event.actor_id}</span>
                          <span>•</span>
                          <span className="font-mono">{new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          {event.invoice_id && (
                            <>
                              <span>•</span>
                              <span className="font-mono text-indigo-600 dark:text-indigo-400">{event.invoice_id}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <Badge tone="neutral" size="sm">
                      {event.action?.split('_')[0] || 'EVENT'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
