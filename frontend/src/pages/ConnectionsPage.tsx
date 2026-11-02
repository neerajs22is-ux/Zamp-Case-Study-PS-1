import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { 
  Mail, 
  Database, 
  HardDrive, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  RefreshCw, 
  ExternalLink,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Server,
  Key,
  Layers,
  ArrowRight,
  Copy,
  Check,
  ShieldCheck,
  FileX
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser, HealthResponse } from '../types';

interface ConnectionsPageProps {
  currentUser?: AuthenticatedUser | null;
}

export const ConnectionsPage: React.FC<ConnectionsPageProps> = ({ currentUser }) => {
  const [searchParams] = useSearchParams();
  const [oauthNotice, setOauthNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  
  const [connections, setConnections] = useState<any>(null);
  const [gmailStatus, setGmailStatus] = useState<any>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Syncing state
  const [syncingGmail, setSyncingGmail] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  // Collapsible detail panels
  const [showGmailDetails, setShowGmailDetails] = useState(false);
  const [showErpAdmin, setShowErpAdmin] = useState(false);
  const [showSystemHealth, setShowSystemHealth] = useState(true);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const canManageIntegrations = currentUser?.role && ['SYSTEM_ADMIN', 'CONTROLLER', 'AP_LEAD'].includes(currentUser.role);

  const loadData = async (isManualRefresh: boolean = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [connData, gmailData, healthData] = await Promise.allSettled([
        api.getConnections(),
        api.getGmailStatus(),
        api.getHealth()
      ]);

      if (connData.status === 'fulfilled') setConnections(connData.value);
      if (gmailData.status === 'fulfilled') setGmailStatus(gmailData.value);
      if (healthData.status === 'fulfilled') setHealth(healthData.value);

      if (connData.status === 'rejected' && gmailData.status === 'rejected') {
        setError('Failed to query subsystem and integration states.');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to query connection states.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();

    // Check OAuth return params
    const gmail = searchParams.get('gmail');
    const mailbox = searchParams.get('mailbox');
    const gmailError = searchParams.get('gmail_error') || searchParams.get('detail');

    if (gmail === 'connected' || gmail === 'authorized') {
      setOauthNotice({
        type: 'success',
        message: `Gmail ingestion connected successfully for ${mailbox || 'authorized mailbox'}.`
      });
      window.history.replaceState({}, '', window.location.pathname);
    } else if (gmailError || gmail === 'error') {
      setOauthNotice({
        type: 'error',
        message: `Gmail connection failed: ${gmailError || 'Authorization was rejected or expired.'}`
      });
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [searchParams]);

  const handleCopy = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleConnectGmail = async () => {
    try {
      const res = await api.getGmailAuthorizeUrl();
      if (res.authorization_url) {
        window.location.href = res.authorization_url;
      }
    } catch (err: any) {
      alert(`Gmail OAuth initiation failed: ${err?.message || 'Server error'}`);
    }
  };

  const handleSyncGmail = async () => {
    setSyncingGmail(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const res = await api.syncGmailMailbox(15);
      setSyncResult(`Import completed: ${res.ingested_count} invoice(s) registered into queue, ${res.duplicates_skipped} duplicate(s) skipped, ${res.quarantined_count} quarantined.`);
      await loadData(true);
    } catch (err: any) {
      setSyncError(err?.message || 'Gmail synchronization encountered an error.');
    } finally {
      setSyncingGmail(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!window.confirm('Are you sure you want to disconnect this Gmail mailbox? Automated or on-demand invoice ingestion from this inbox will stop.')) {
      return;
    }
    setDisconnecting(true);
    try {
      await api.disconnectGmailMailbox();
      setSyncResult('Mailbox disconnected successfully.');
      await loadData(true);
    } catch (err: any) {
      alert(`Disconnect failed: ${err?.message || 'Server error'}`);
    } finally {
      setDisconnecting(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'CONNECTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            Connected
          </span>
        );
      case 'SNAPSHOT_MODE':
      case 'EVALUATION_FIXTURES':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800/40">
            <Server className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
            Snapshot Fixtures
          </span>
        );
      case 'DEGRADED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            Degraded / Re-auth Required
          </span>
        );
      case 'NOT_CONFIGURED':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            Not Configured (Evaluation Mode)
          </span>
        );
    }
  };

  const quarantinedDocs = connections?.quarantined_documents || [];

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <Layers className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Integration Connections & Subsystem Health
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Verified status of invoice ingestion pipelines, ERP data boundaries, and secure infrastructure.
          </p>
        </div>

        <button
          onClick={() => loadData(true)}
          disabled={loading || refreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Run Health Diagnostics
        </button>
      </div>

      {/* Architecture Topology Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Ingestion Pipeline</span>
            <Mail className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-1.5 text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            Gmail & Upload
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">SHA-256 PDF Ingestion</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Identity & RBAC</span>
            <Key className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-1.5 text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            Supabase Auth
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">JWT Token Authority</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Storage & Ledger</span>
            <Database className="w-4 h-4 text-sky-500" />
          </div>
          <div className="mt-1.5 text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            PostgreSQL & Vault
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Encrypted Object Bucket</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>ERP Governance</span>
            <Server className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-1.5 text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-sky-500" />
            Reference Snapshots
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Live ERP Not Configured</div>
        </div>
      </div>

      {/* OAuth Banner Alerts */}
      {oauthNotice && (
        <div className={`p-4 rounded-xl border text-xs flex items-start gap-3 shadow-2xs ${
          oauthNotice.type === 'success'
            ? 'bg-emerald-50/80 border-emerald-200 text-emerald-900 dark:bg-emerald-950/30 dark:border-emerald-800/40 dark:text-emerald-200'
            : 'bg-rose-50/80 border-rose-200 text-rose-900 dark:bg-rose-950/30 dark:border-rose-800/40 dark:text-rose-200'
        }`}>
          {oauthNotice.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          ) : (
            <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          )}
          <div className="flex-1 font-medium">{oauthNotice.message}</div>
          <button
            onClick={() => setOauthNotice(null)}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            ×
          </button>
        </div>
      )}

      {/* General error alert */}
      {error && (
        <div className="p-3.5 rounded-xl border bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-950/30 dark:border-rose-800/40 dark:text-rose-200 text-xs flex items-start gap-2.5 shadow-2xs">
          <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {/* Sync Alerts */}
      {syncResult && (
        <div className="p-3.5 rounded-xl border bg-emerald-50/80 border-emerald-200 text-emerald-900 dark:bg-emerald-950/30 dark:border-emerald-800/40 dark:text-emerald-200 text-xs flex items-start gap-2.5 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium">{syncResult}</div>
          <button onClick={() => setSyncResult(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {syncError && (
        <div className="p-3.5 rounded-xl border bg-rose-50/80 border-rose-200 text-rose-900 dark:bg-rose-950/30 dark:border-rose-800/40 dark:text-rose-200 text-xs flex items-start gap-2.5 shadow-2xs">
          <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">{syncError}</div>
          <button onClick={() => setSyncError(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {/* Compliance Note */}
      <div className="bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40 rounded-xl p-3 text-xs flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="text-slate-700 dark:text-slate-300 space-y-0.5 leading-relaxed">
          <span className="font-semibold text-slate-900 dark:text-slate-100">Google Ingestion & Security Compliance:</span> Dedicated Google mailbox integration is active for on-demand synchronization. All ingested attachments undergo SHA-256 deduplication and mime-type security validation before queue registration.
        </div>
      </div>

      {/* Stacked Connection Cards */}
      <div className="space-y-4">
        
        {/* Card 1: Gmail Ingestion */}
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-800/30">
                <Mail className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  Gmail Mailbox Ingestion
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Primary email ingestion channel for supplier invoices and delivery notes.
                </p>
              </div>
            </div>
            <div>
              {getStatusBadge(gmailStatus?.status || connections?.pillars?.gmail_ingestion?.status)}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3 bg-slate-50 dark:bg-slate-950/50 rounded-lg border border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-500 dark:text-slate-400 block mb-1 font-medium">Mailbox Address</span>
              <span className="font-mono font-semibold text-slate-800 dark:text-slate-200 truncate block">
                {gmailStatus?.mailbox || connections?.pillars?.gmail_ingestion?.mailbox || 'Evaluation Mailbox Configured'}
              </span>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-950/50 rounded-lg border border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-500 dark:text-slate-400 block mb-1 font-medium">Last Synchronization</span>
              <span className="text-slate-800 dark:text-slate-200 font-medium block">
                {gmailStatus?.last_synced_at ? (
                  new Date(gmailStatus.last_synced_at).toLocaleString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                ) : gmailStatus?.status === 'CONNECTED' ? (
                  <span className="text-amber-600 dark:text-amber-400">On-demand ready</span>
                ) : (
                  'Never'
                )}
              </span>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-950/50 rounded-lg border border-slate-100 dark:border-slate-800/60">
              <span className="text-slate-500 dark:text-slate-400 block mb-1 font-medium">Import Strategy</span>
              <span className="text-slate-800 dark:text-slate-200 font-medium block">
                On-Demand & Webhook Sync
              </span>
            </div>
          </div>

          {/* Action Row */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2">
              <button
                onClick={handleSyncGmail}
                disabled={syncingGmail || gmailStatus?.status === 'NOT_CONFIGURED'}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-2xs transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncingGmail ? 'animate-spin' : ''}`} />
                {syncingGmail ? 'Importing from Gmail...' : 'Import now'}
              </button>

              {canManageIntegrations ? (
                <>
                  <button
                    onClick={handleConnectGmail}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-2xs"
                  >
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                    {gmailStatus?.status === 'CONNECTED' ? 'Reconnect' : 'Authorize Mailbox'}
                  </button>

                  {gmailStatus?.status === 'CONNECTED' && (
                    <button
                      onClick={handleDisconnectGmail}
                      disabled={disconnecting}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-rose-200 dark:border-rose-900/40 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors shadow-2xs disabled:opacity-50"
                    >
                      {disconnecting ? 'Disconnecting...' : 'Disconnect'}
                    </button>
                  )}
                </>
              ) : (
                <span className="text-[11px] text-slate-400 dark:text-slate-500 italic">
                  OAuth management requires AP Lead or Admin authority.
                </span>
              )}
            </div>

            <button
              onClick={() => setShowGmailDetails(!showGmailDetails)}
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 font-medium"
            >
              {showGmailDetails ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              Technical details
            </button>
          </div>

          {/* Technical Details Collapsible */}
          {showGmailDetails && (
            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3.5 rounded-xl text-xs space-y-2 font-mono">
              <div className="flex justify-between items-center">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Authorized Scope:</span>
                <span className="text-slate-700 dark:text-slate-300">https://www.googleapis.com/auth/gmail.readonly</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Watch Status:</span>
                <span className="text-slate-700 dark:text-slate-300">{gmailStatus?.watch_status || 'NOT_CONFIGURED'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Pub/Sub Topic:</span>
                <span className="text-slate-700 dark:text-slate-300">{gmailStatus?.pubsub_topic || 'Not provisioned'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 dark:text-slate-400 font-sans">Credential Storage:</span>
                <span className="text-slate-700 dark:text-slate-300 font-sans">PostgreSQL Encrypted Vault (Fernet token encryption)</span>
              </div>
            </div>
          )}
        </div>

        {/* Card 2: ERP Source Records Boundary (SAP S/4HANA) */}
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400 border border-sky-100 dark:border-sky-800/30">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  Enterprise ERP Integration (SAP S/4HANA)
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Read-only boundary for procurement purchase orders, goods receipts, and vendor masters.
                </p>
              </div>
            </div>
            <div>
              {getStatusBadge('SNAPSHOT_MODE')}
            </div>
          </div>

          <div className="text-xs text-slate-600 dark:text-slate-300 space-y-2.5">
            <p className="leading-relaxed">
              Direct SAP S/4HANA OData synchronization is not configured in this environment. The AP Command Center operates against verified, immutable procurement reference snapshots.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <Link
                to="/settings/reference-data"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 text-slate-800 dark:text-slate-200 font-semibold transition-colors text-xs"
              >
                <span>Inspect Procurement Records (PO, GRN, QC)</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          {/* Admin Configuration Guide */}
          <div className="pt-1">
            <button
              onClick={() => setShowErpAdmin(!showErpAdmin)}
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 font-medium"
            >
              {showErpAdmin ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              For administrators: Environment requirements
            </button>

            {showErpAdmin && (
              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3.5 rounded-xl text-xs space-y-2.5 font-mono">
                <p className="text-slate-600 dark:text-slate-400 font-sans text-xs">
                  To establish a live SAP OData connector, configure the following container environment parameters:
                </p>
                <div className="text-slate-700 dark:text-slate-300 space-y-1.5">
                  <div className="flex items-center justify-between p-1.5 bg-white dark:bg-slate-900 rounded-md border border-slate-200 dark:border-slate-800">
                    <div><span className="text-indigo-600 dark:text-indigo-400 font-bold">SAP_API_BASE_URL</span>=https://your-sap-gateway.company.internal/sap/opu/odata/sap/</div>
                    <button onClick={() => handleCopy('SAP_API_BASE_URL=https://your-sap-gateway.company.internal/sap/opu/odata/sap/', 'sap_url')} className="text-slate-400 hover:text-slate-600 p-1">
                      {copiedKey === 'sap_url' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-1.5 bg-white dark:bg-slate-900 rounded-md border border-slate-200 dark:border-slate-800">
                    <div><span className="text-indigo-600 dark:text-indigo-400 font-bold">SAP_COMPANY_CODE</span>=1000</div>
                    <button onClick={() => handleCopy('SAP_COMPANY_CODE=1000', 'sap_code')} className="text-slate-400 hover:text-slate-600 p-1">
                      {copiedKey === 'sap_code' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-1.5 bg-white dark:bg-slate-900 rounded-md border border-slate-200 dark:border-slate-800">
                    <div><span className="text-indigo-600 dark:text-indigo-400 font-bold">SAP_CLIENT_ID</span>=(Assigned RFC client)</div>
                    <button onClick={() => handleCopy('SAP_CLIENT_ID=', 'sap_client')} className="text-slate-400 hover:text-slate-600 p-1">
                      {copiedKey === 'sap_client' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Card 3: Foundational Subsystem Health */}
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-800/30">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                  Foundational Subsystem Health
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Real-time connectivity to persistent storage, database, and identity provider.
                </p>
              </div>
            </div>

            <button
              onClick={() => setShowSystemHealth(!showSystemHealth)}
              className="text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 font-medium inline-flex items-center gap-1"
            >
              {showSystemHealth ? 'Collapse' : 'Expand'}
            </button>
          </div>

          {showSystemHealth && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              {/* Database */}
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-slate-100 dark:border-slate-800/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    PostgreSQL Database
                  </span>
                  {getStatusBadge(health?.subsystems?.database?.status || connections?.pillars?.database?.status)}
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] leading-relaxed">
                  {health?.subsystems?.database?.message || connections?.pillars?.database?.message || 'Primary transactional ledger and durable job queue.'}
                </p>
              </div>

              {/* Object Storage */}
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-slate-100 dark:border-slate-800/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                    <HardDrive className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    Object Storage
                  </span>
                  {getStatusBadge(health?.subsystems?.object_storage?.status || connections?.pillars?.object_storage?.status)}
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] leading-relaxed">
                  {health?.subsystems?.object_storage?.message || connections?.pillars?.object_storage?.message || 'Encrypted PDF invoice vault with time-limited signed URLs.'}
                </p>
              </div>

              {/* Identity Provider */}
              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-slate-100 dark:border-slate-800/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    Identity Provider
                  </span>
                  {getStatusBadge(health?.subsystems?.identity_provider?.status || connections?.pillars?.identity?.status)}
                </div>
                <p className="text-slate-500 dark:text-slate-400 text-[11px] leading-relaxed">
                  {health?.subsystems?.identity_provider?.message || connections?.pillars?.identity?.message || 'Role-based access control and tenant isolation token authority.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Card 4: Quarantined Documents & Pipeline Security */}
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 border border-amber-100 dark:border-amber-800/30">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                  Quarantine & Ingestion Security Vault
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Defensive isolation of corrupted, malicious, or unreadable invoice files.
                </p>
              </div>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold">
              {quarantinedDocs.length} Quarantined
            </span>
          </div>

          {quarantinedDocs.length === 0 ? (
            <div className="p-6 text-center text-xs space-y-1.5 bg-slate-50 dark:bg-slate-950/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
              <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto" />
              <div className="font-semibold text-slate-800 dark:text-slate-200">Ingestion Pipeline Clean</div>
              <p className="text-slate-500 max-w-md mx-auto text-[11px]">
                No files are currently quarantined. All uploaded documents have passed cryptographic checksum checks and MIME validation.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[600px]">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 border-b border-slate-200 dark:border-slate-800 text-[10px] uppercase font-semibold">
                  <tr>
                    <th className="py-2 px-3">Filename</th>
                    <th className="py-2 px-3">Quarantine Reason</th>
                    <th className="py-2 px-3">SHA-256 Digest</th>
                    <th className="py-2 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {quarantinedDocs.map((doc: any) => (
                    <tr key={doc.id} className="hover:bg-slate-50/50">
                      <td className="py-2.5 px-3 font-medium text-slate-900 dark:text-white flex items-center gap-1.5">
                        <FileX className="w-3.5 h-3.5 text-rose-500" />
                        {doc.filename}
                      </td>
                      <td className="py-2.5 px-3 text-rose-600 dark:text-rose-400 font-mono text-[11px]">
                        {doc.quarantine_reason}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[10px] text-slate-500 truncate max-w-[140px]">
                        {doc.sha256}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
