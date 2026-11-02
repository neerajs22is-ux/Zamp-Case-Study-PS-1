import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Key, 
  CheckCircle, 
  Clock, 
  AlertCircle, 
  UserCheck,
  Send,
  Loader2,
  Info,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { api, setAuthToken } from '../api/client';
import type { AuthenticatedUser, AccessRequest } from '../types';

interface AuthScreenProps {
  user: AuthenticatedUser | null;
  loading: boolean;
  error: string | null;
  onRefreshUser: () => void;
  onLogout: () => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({
  user,
  loading,
  error,
  onRefreshUser,
  onLogout,
}) => {
  const [devTokenInput, setDevTokenInput] = useState('');
  const [inviteToken, setInviteToken] = useState('');
  const [targetOrgId, setTargetOrgId] = useState('org_default');
  const [requestedRole, setRequestedRole] = useState('AP_ASSOCIATE');
  const [accessReason, setAccessReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [myRequests, setMyRequests] = useState<AccessRequest[]>([]);
  const [authStatus, setAuthStatus] = useState<any>(null);
  const [showGoogleSetup, setShowGoogleSetup] = useState(false);

  useEffect(() => {
    api.getAuthStatus().then(setAuthStatus).catch(() => {});

    const urlParams = new URLSearchParams(window.location.search);
    const errDesc = urlParams.get('error_description') || urlParams.get('error');
    if (errDesc) {
      if (errDesc.includes('provider is not enabled') || errDesc.includes('Unsupported provider') || errDesc.includes('validation_failed')) {
        setActionMessage({
          type: 'info',
          text: 'Google OAuth provider is unconfigured in the connected Supabase Cloud project. Please select an SME Evaluation Role below for instant access.',
        });
      } else {
        setActionMessage({
          type: 'error',
          text: `Supabase Authentication notice: ${decodeURIComponent(errDesc)}`,
        });
      }
    }
  }, []);

  useEffect(() => {
    if (user && !user.is_provisioned) {
      loadMyRequests();
    }
  }, [user]);

  const loadMyRequests = async () => {
    try {
      const reqs = await api.getMyAccessRequests();
      setMyRequests(reqs);
    } catch (err: any) {
      console.warn('Failed to load user access requests:', err);
    }
  };

  const handleGoogleSignIn = () => {
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || authStatus?.supabase_url || '';
    if (!supabaseUrl) {
      setActionMessage({
        type: 'error',
        text: 'Supabase URL is not configured in environment variables (VITE_SUPABASE_URL).',
      });
      return;
    }
    const redirectUrl = `${window.location.origin}/auth/callback`;
    window.location.href = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirectUrl)}`;
  };

  const handleApplyDevToken = (token: string) => {
    if (!token.trim()) return;
    if (token.trim().startsWith('test_token:')) {
      setActionMessage({
        type: 'error',
        text: 'Test harness tokens (test_token:*) are strictly prohibited in DEVELOPMENT mode. Please use SME Quick Login or authenticate via Supabase Auth.',
      });
      return;
    }
    setAuthToken(token.trim());
    setActionMessage(null);
    onRefreshUser();
  };

  const handleQuickLogin = async (email: string, orgId = 'org_sme_eval', unprovisioned = false) => {
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.getDevSession(email, orgId, unprovisioned);
      setAuthToken(res.access_token);
      onRefreshUser();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Quick login failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAcceptInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteToken.trim()) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.acceptInvitation(inviteToken.trim());
      setActionMessage({ type: 'success', text: res.message || 'Invitation accepted successfully!' });
      setInviteToken('');
      onRefreshUser();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to accept invitation.' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitAccessRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetOrgId.trim()) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.submitAccessRequest(targetOrgId.trim(), accessReason.trim(), requestedRole);
      setActionMessage({ type: 'success', text: res.message || 'Access request submitted successfully.' });
      setAccessReason('');
      await loadMyRequests();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to submit access request.' });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 text-indigo-600 dark:text-indigo-400 animate-spin" />
        <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Verifying corporate credentials and session claims...</p>
      </div>
    );
  }

  if (!user) {
    const isGoogleEnabled = authStatus?.google_oauth_enabled === true;
    const isLocalEnv = !import.meta.env.PROD || authStatus?.dev_session_enabled || window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';

    return (
      <div className="max-w-xl mx-auto my-6 p-6 sm:p-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl transition-colors">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 rounded-xl mb-3 text-indigo-600 dark:text-indigo-400">
            <Shield className="w-7 h-7" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">AP Command Center</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Autonomous Invoice Verification, Policy Compliance & Dual Approval</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 rounded-xl flex items-start gap-2.5 text-rose-800 dark:text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Authentication Notice</p>
              <p className="mt-0.5 opacity-90">{error}</p>
            </div>
          </div>
        )}

        {actionMessage && (
          <div className={`mb-6 p-3.5 rounded-xl flex items-start gap-2.5 text-xs ${
            actionMessage.type === 'success' 
              ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300' 
              : actionMessage.type === 'info'
              ? 'bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800/60 text-sky-800 dark:text-sky-300'
              : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 text-rose-800 dark:text-rose-300'
          }`}>
            {actionMessage.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            ) : actionMessage.type === 'info' ? (
              <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            )}
            <span className="leading-relaxed">{actionMessage.text}</span>
          </div>
        )}

        <div className="space-y-5">
          {/* Section 1: Instant SME Evaluation Access (Prominent for Evaluators) */}
          {isLocalEnv && (
            <div className="border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/40 dark:bg-indigo-950/20 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-950 dark:text-indigo-200">
                  <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Instant Evaluation Access</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/60 border border-indigo-300 dark:border-indigo-700 text-indigo-800 dark:text-indigo-300 font-semibold">
                  1-Click Workspace Login
                </span>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 mb-3 leading-relaxed">
                Select a verified evaluation role to inspect genuine invoice matching, 7-point policy gates, and dual approval:
              </p>
              <div className="space-y-2">
                {[
                  { 
                    label: 'SME AP Lead', 
                    email: 'sme_lead@company.internal', 
                    desc: 'Initial review sign-off (< ₹5,00,000), exception triage, debit notes',
                    badge: 'Recommended for Demo',
                    color: 'bg-indigo-600 hover:bg-indigo-700 text-white'
                  },
                  { 
                    label: 'SME Financial Controller', 
                    email: 'sme_controller@company.internal', 
                    desc: 'Executive dual approval authority for high-value disbursements (≥ ₹5,00,000)',
                    badge: 'Dual Control Step 2',
                    color: 'bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700'
                  },
                  { 
                    label: 'SME Auditor', 
                    email: 'sme_auditor@company.internal', 
                    desc: 'Read-only compliance inspection, tamper-evident audit ledger oversight',
                    badge: 'Read-Only Oversight',
                    color: 'bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700'
                  },
                  { 
                    label: 'SME AP Associate', 
                    email: 'sme_associate@company.internal', 
                    desc: 'Operational queue intake, OCR parsing validation, discrepancy flagging',
                    badge: 'Operational Intake',
                    color: 'bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700'
                  },
                ].map((item) => (
                  <button
                    key={item.label}
                    disabled={actionLoading}
                    onClick={() => handleQuickLogin(item.email, 'org_sme_eval', false)}
                    className={`w-full text-left p-2.5 rounded-lg text-xs transition-colors flex items-center justify-between shadow-2xs ${item.color} disabled:opacity-50`}
                  >
                    <div>
                      <div className="font-semibold flex items-center gap-1.5">
                        <span>{item.label}</span>
                        <span className="text-[10px] opacity-75 font-normal">({item.badge})</span>
                      </div>
                      <div className="text-[10px] opacity-80 mt-0.5">{item.desc}</div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 shrink-0 opacity-80" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Section 2: Enterprise SSO (Google Workspace) */}
          <div className="border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                <span className="text-xs font-semibold text-slate-800 dark:text-white">Google Workspace SSO (Production IdP)</span>
              </div>
              {isGoogleEnabled ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-400 font-medium">
                  Active
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                  Optional Setup
                </span>
              )}
            </div>

            {isGoogleEnabled ? (
              <button
                onClick={handleGoogleSignIn}
                className="w-full mt-2 flex items-center justify-center gap-2.5 bg-white hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-900 dark:text-white font-semibold py-2 px-4 rounded-lg border border-slate-300 dark:border-slate-700 shadow-2xs transition-colors text-xs"
              >
                Sign in with Google Workspace
              </button>
            ) : (
              <div className="mt-1">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                  Enterprise SSO connects against Supabase Auth. For production deployments with Google Workspace, enable the Google OAuth provider in Supabase Cloud.
                </p>
                <div className="mt-2.5 flex items-center gap-2">
                  <button
                    onClick={() => setShowGoogleSetup(!showGoogleSetup)}
                    className="text-[11px] bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors flex items-center gap-1.5"
                  >
                    <Info className="w-3.5 h-3.5 text-indigo-500" />
                    {showGoogleSetup ? 'Hide Cloud Instructions' : 'View Cloud Setup Instructions'}
                  </button>
                </div>

                {showGoogleSetup && (
                  <div className="mt-3 p-3 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-xs space-y-2">
                    <p className="font-semibold text-slate-900 dark:text-slate-200 text-[11px]">To enable Google Workspace in Supabase:</p>
                    <ol className="list-decimal list-inside space-y-1 text-slate-600 dark:text-slate-400 text-[11px] leading-relaxed">
                      <li>In <span className="font-medium text-slate-800 dark:text-slate-200">Supabase Dashboard</span> &rarr; Authentication &rarr; Providers &rarr; Google: toggle Enable and enter Client ID & Secret.</li>
                      <li>In Redirect URLs, add: <code className="font-mono text-indigo-600 dark:text-indigo-400 select-all">http://localhost:8000/auth/callback</code></li>
                    </ol>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Section 3: Developer & Diagnostics Access (Collapsible) */}
          {isLocalEnv && (
            <details className="border border-slate-200 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/20 rounded-xl p-3 group">
              <summary className="text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-300 cursor-pointer flex items-center justify-between font-mono select-none">
                <span>Developer & Diagnostics Access (JWT Inspection)</span>
                <span className="text-[10px] text-slate-500 group-open:rotate-90 transition-transform">&rarr;</span>
              </summary>
              <div className="pt-3 space-y-2">
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Direct token injection for automated testing or inspecting custom Supabase JWTs.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Paste valid Supabase Bearer JWT (eyJhbGci...)"
                    value={devTokenInput}
                    onChange={(e) => setDevTokenInput(e.target.value)}
                    className="flex-1 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                  <button
                    onClick={() => handleApplyDevToken(devTokenInput)}
                    className="bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors shadow-2xs"
                  >
                    Apply Token
                  </button>
                </div>
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  // State 4+: Authenticated BUT Unprovisioned
  if (!user.is_provisioned) {
    const pendingRequest = myRequests.find((r) => r.status === 'PENDING');

    return (
      <div className="max-w-2xl mx-auto my-8 space-y-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-lg text-amber-600 dark:text-amber-400">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-900 dark:text-white">Identity Verified: Unprovisioned Employee</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">{user.email} (ID: {user.id})</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="text-xs text-slate-600 dark:text-slate-400 hover:text-rose-600 border border-slate-200 dark:border-slate-800 hover:border-rose-300 dark:hover:border-rose-900/50 bg-slate-50 dark:bg-slate-950 px-3 py-1.5 rounded-lg transition-colors"
            >
              Sign Out
            </button>
          </div>

          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            Your corporate identity has been authenticated. However, you do not currently hold an active tenant membership. Accept an invitation token or submit an access request below.
          </p>

          {actionMessage && (
            <div className={`mt-4 p-3 rounded-lg flex items-start gap-2 text-xs ${
              actionMessage.type === 'success' 
                ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300' 
                : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300'
            }`}>
              {actionMessage.type === 'success' ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}
              <span>{actionMessage.text}</span>
            </div>
          )}
        </div>

        {/* State 7: Pending */}
        {pendingRequest && (
          <div className="bg-sky-50 dark:bg-sky-500/10 border border-sky-200 dark:border-sky-500/30 rounded-xl p-4 flex items-start gap-3 text-sky-800 dark:text-sky-200">
            <Clock className="w-5 h-5 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-semibold text-slate-900 dark:text-white">Access Request Under Review</p>
              <p className="mt-1">
                Your request for organisation <span className="font-mono font-semibold text-slate-900 dark:text-white">{pendingRequest.org_id}</span> ({pendingRequest.requested_role}) is pending review.
              </p>
            </div>
          </div>
        )}

        {/* State 4 & 5: Accept Invitation */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Key className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Option 1: Accept an Invitation Token</h3>
          </div>
          <form onSubmit={handleAcceptInvitation} className="flex gap-2">
            <input
              type="text"
              placeholder="Paste 32-character single-use invitation token..."
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              className="flex-1 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-indigo-500 font-mono"
            />
            <button
              type="submit"
              disabled={actionLoading || !inviteToken.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors shadow-2xs"
            >
              {actionLoading ? 'Verifying...' : 'Accept'}
            </button>
          </form>
        </div>

        {/* State 6: Submit Access Request */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Send className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Option 2: Submit Access Request</h3>
          </div>
          <form onSubmit={handleSubmitAccessRequest} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">Target Organisation ID</label>
                <input
                  type="text"
                  value={targetOrgId}
                  onChange={(e) => setTargetOrgId(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-slate-200 font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">Requested Role</label>
                <select
                  value={requestedRole}
                  onChange={(e) => setRequestedRole(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-slate-200"
                >
                  <option value="AP_ASSOCIATE">AP Associate</option>
                  <option value="AP_LEAD">AP Lead</option>
                  <option value="CONTROLLER">Financial Controller</option>
                  <option value="AUDITOR">Auditor (Read-Only)</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">Business Reason</label>
              <textarea
                rows={2}
                value={accessReason}
                onChange={(e) => setAccessReason(e.target.value)}
                placeholder="State your department and reason for access..."
                className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-200"
              />
            </div>
            <button
              type="submit"
              disabled={actionLoading || !accessReason.trim()}
              className="px-4 py-2 bg-slate-800 dark:bg-slate-700 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors shadow-2xs"
            >
              Submit Access Request
            </button>
          </form>
        </div>
      </div>
    );
  }

  return null;
};
