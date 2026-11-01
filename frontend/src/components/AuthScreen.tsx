import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Key, 
  CheckCircle, 
  Clock, 
  XCircle, 
  AlertCircle, 
  UserCheck,
  Send,
  Loader2,
  Info
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

  // Fetch IdP configuration status and check for OAuth redirect errors
  useEffect(() => {
    api.getAuthStatus().then(setAuthStatus).catch(() => {});

    const urlParams = new URLSearchParams(window.location.search);
    const errDesc = urlParams.get('error_description') || urlParams.get('error');
    if (errDesc) {
      if (errDesc.includes('provider is not enabled') || errDesc.includes('Unsupported provider') || errDesc.includes('validation_failed')) {
        setActionMessage({
          type: 'error',
          text: 'Google OAuth provider is unconfigured in the connected Supabase Cloud project (https://qxrrbyjczuqkgnexwqyh.supabase.co). Please use the SME Evaluation Quick Login or see the Manual Setup Instructions below.',
        });
        setShowGoogleSetup(true);
      } else {
        setActionMessage({
          type: 'error',
          text: `Supabase Authentication notice: ${decodeURIComponent(errDesc)}`,
        });
      }
    }
  }, []);

  // Fetch access requests if user is authenticated but not provisioned
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

  // State 2: Authentication Loading
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
        <p className="text-slate-400 text-sm font-medium">Verifying corporate credentials and session claims...</p>
      </div>
    );
  }

  // State 1 & 3: Not signed in or Auth error
  if (!user) {
    const isGoogleEnabled = authStatus?.google_oauth_enabled === true;

    return (
      <div className="max-w-xl mx-auto my-10 p-6 md:p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl">
        <div className="text-center mb-8">
          <div className="inline-flex p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl mb-3 text-indigo-400">
            <Shield className="w-7 h-7" />
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">Autonomous AP Command Center</h1>
          <p className="text-xs text-slate-400 mt-1">Enterprise Employee Authentication & Access Control</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-2.5 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Authentication Notice</p>
              <p className="mt-0.5 opacity-90">{error}</p>
            </div>
          </div>
        )}

        {actionMessage && (
          <div className={`mb-6 p-3.5 rounded-xl flex items-start gap-2.5 text-xs ${
            actionMessage.type === 'success' 
              ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' 
              : 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
          }`}>
            {actionMessage.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            )}
            <span className="leading-relaxed">{actionMessage.text}</span>
          </div>
        )}

        <div className="space-y-5">
          {/* Section 1: Enterprise SSO (Google Workspace) */}
          <div className="border border-slate-800 bg-slate-950/60 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                <span className="text-xs font-semibold text-white">Google Workspace SSO</span>
              </div>
              {isGoogleEnabled ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium">
                  Active
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 font-medium">
                  Setup Required
                </span>
              )}
            </div>

            {isGoogleEnabled ? (
              <button
                onClick={handleGoogleSignIn}
                className="w-full mt-2 flex items-center justify-center gap-2.5 bg-white hover:bg-slate-100 text-slate-900 font-semibold py-2 px-4 rounded-lg shadow transition-colors text-xs"
              >
                Sign in with Google Workspace
              </button>
            ) : (
              <div className="mt-1">
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Enterprise SSO is configured against Supabase Auth, but the Google provider is currently disabled in your Supabase Cloud dashboard (<code className="text-slate-300 font-mono text-[10px]">qxrrbyjczuqkgnexwqyh.supabase.co</code>).
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => setShowGoogleSetup(!showGoogleSetup)}
                    className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium px-3 py-1.5 rounded-lg border border-slate-700 transition-colors flex items-center gap-1.5"
                  >
                    <Info className="w-3.5 h-3.5 text-amber-400" />
                    {showGoogleSetup ? 'Hide Setup Instructions' : 'View Setup Instructions'}
                  </button>
                  <button
                    onClick={handleGoogleSignIn}
                    className="text-[11px] bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-300 font-medium px-3 py-1.5 rounded-lg border border-slate-800 transition-colors"
                  >
                    Test Supabase Redirect
                  </button>
                </div>

                {showGoogleSetup && (
                  <div className="mt-3 pt-3 border-t border-slate-800 text-xs text-slate-300 space-y-2">
                    <p className="font-semibold text-white text-[11px]">To enable Google Workspace SSO:</p>
                    <ol className="list-decimal pl-4 space-y-1.5 text-[11px] text-slate-400">
                      <li>
                        In <span className="text-slate-200 font-medium">Google Cloud Console</span>, create an OAuth 2.0 Client ID (Web Application).
                      </li>
                      <li>
                        Set <span className="text-slate-200 font-medium">Authorized Redirect URI</span> to:
                        <div className="mt-1 font-mono text-[10px] bg-slate-950 p-1.5 rounded border border-slate-800 text-indigo-300 select-all break-all">
                          {authStatus?.supabase_callback_url || 'https://qxrrbyjczuqkgnexwqyh.supabase.co/auth/v1/callback'}
                        </div>
                      </li>
                      <li>
                        In <span className="text-slate-200 font-medium">Supabase Dashboard</span> &rarr; <span className="text-slate-200">Authentication &rarr; Providers &rarr; Google</span>:
                        <br />Toggle <strong>Enable Google provider</strong> and paste your Client ID and Client Secret.
                      </li>
                      <li>
                        In Supabase <span className="text-slate-200 font-medium">Authentication &rarr; URL Configuration &rarr; Redirect URLs</span>, add:
                        <div className="mt-1 font-mono text-[10px] bg-slate-950 p-1.5 rounded border border-slate-800 text-slate-300 space-y-0.5">
                          {(authStatus?.allowed_redirect_urls || [
                            'http://localhost:8000/auth/callback',
                            'http://127.0.0.1:8000/auth/callback',
                            'http://localhost:5173/auth/callback',
                          ]).map((url: string) => (
                            <div key={url} className="text-emerald-400 select-all">{url}</div>
                          ))}
                        </div>
                      </li>
                    </ol>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Section 2: SME Acceptance Quick Login (Local Evaluation Environment Only) */}
          {(!import.meta.env.PROD || authStatus?.dev_session_enabled || window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && (
            <div className="border border-slate-800 bg-slate-950/40 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1.5">
                <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">
                  SME Evaluation Access
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-medium">
                  Local Evaluation Only
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mb-3 leading-relaxed">
                Issues authentic Supabase JWTs with verified roles. Restricted to local loopback hosts (127.0.0.1, localhost) in development mode and strictly isolated to tenant <code className="text-indigo-300 font-mono">org_sme_eval</code>.
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { label: 'SME AP Lead', email: 'sme_lead@company.internal', unprovisioned: false },
                  { label: 'SME Controller', email: 'sme_controller@company.internal', unprovisioned: false },
                  { label: 'SME AP Associate', email: 'sme_associate@company.internal', unprovisioned: false },
                  { label: 'SME Auditor (Read-Only)', email: 'sme_auditor@company.internal', unprovisioned: false },
                  { label: 'Unprovisioned Candidate', email: 'new_employee@company.internal', unprovisioned: true },
                ].map((item) => (
                  <button
                    key={item.label}
                    disabled={actionLoading}
                    onClick={() => handleQuickLogin(item.email, 'org_sme_eval', item.unprovisioned)}
                    className="text-left px-2.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg text-[11px] text-slate-200 transition-colors truncate disabled:opacity-50 font-medium"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Section 3: Developer & Diagnostics Access (Collapsible) */}
          {(!import.meta.env.PROD || authStatus?.dev_session_enabled || window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') && (
            <details className="border border-slate-800/80 bg-slate-950/20 rounded-xl p-3 group">
              <summary className="text-xs font-medium text-slate-400 hover:text-slate-300 cursor-pointer flex items-center justify-between font-mono select-none">
                <span>Developer & Diagnostics Access (JWT Inspection)</span>
                <span className="text-[10px] text-slate-500 group-open:rotate-90 transition-transform">&rarr;</span>
              </summary>
              <div className="pt-3 space-y-2">
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Direct token injection for automated testing or inspecting custom pre-generated Supabase JWTs. Test harness tokens (<code className="font-mono text-slate-400">test_token:*</code>) are strictly barred in development mode.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Paste valid Supabase Bearer JWT (eyJhbGci...)"
                    value={devTokenInput}
                    onChange={(e) => setDevTokenInput(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                  <button
                    onClick={() => handleApplyDevToken(devTokenInput)}
                    className="bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-700 transition-colors"
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

  // State 4, 5, 6, 7, 8: Authenticated BUT Unprovisioned
  if (!user.is_provisioned) {
    const pendingRequest = myRequests.find((r) => r.status === 'PENDING');
    const rejectedRequest = myRequests.find((r) => r.status === 'REJECTED');

    return (
      <div className="max-w-2xl mx-auto my-8 space-y-6">
        {/* Banner: Authenticated Identity Notice */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-white">Identity Verified: Unprovisioned Employee</h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{user.email} (ID: {user.id})</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="text-xs text-slate-400 hover:text-rose-400 border border-slate-800 hover:border-rose-900/50 bg-slate-950 px-3 py-1.5 rounded-lg transition-colors"
            >
              Sign Out
            </button>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            Your corporate Google identity has been authenticated via Supabase Auth. However, you do not currently hold an active tenant membership in any organisation. To access the AP Command Center, accept an existing single-use invitation or submit an access request for administrator review.
          </p>

          {actionMessage && (
            <div className={`mt-4 p-3 rounded-lg flex items-start gap-2 text-xs ${
              actionMessage.type === 'success' 
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' 
                : 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
            }`}>
              {actionMessage.type === 'success' ? (
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              )}
              <span>{actionMessage.text}</span>
            </div>
          )}
        </div>

        {/* State 7: Access Request Pending Banner */}
        {pendingRequest && (
          <div className="bg-sky-500/10 border border-sky-500/30 rounded-xl p-4 flex items-start gap-3 text-sky-200">
            <Clock className="w-5 h-5 text-sky-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-semibold text-white">Access Request Under Review</p>
              <p className="mt-1">
                Your request for organisation <span className="font-mono font-semibold text-white">{pendingRequest.org_id}</span> ({pendingRequest.requested_role}) submitted on {new Date(pendingRequest.created_at).toLocaleDateString()} is pending review by an authorised administrator.
              </p>
              <p className="mt-1 text-sky-300/80">You will be notified once reviewed. Automatic membership is not permitted.</p>
            </div>
          </div>
        )}

        {/* State 8: Access Request Denied Banner */}
        {rejectedRequest && !pendingRequest && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex items-start gap-3 text-rose-200">
            <XCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="text-xs">
              <p className="font-semibold text-white">Previous Access Request Declined</p>
              <p className="mt-1">
                Your previous request for organisation <span className="font-mono text-white">{rejectedRequest.org_id}</span> was not approved.
              </p>
              {rejectedRequest.review_reason && (
                <p className="mt-1 bg-slate-950/60 p-2 rounded border border-rose-500/20 font-mono text-[11px]">
                  Reason: {rejectedRequest.review_reason}
                </p>
              )}
              <p className="mt-1 text-rose-300/80">Please contact your system administrator or accounts payable controller for assistance.</p>
            </div>
          </div>
        )}

        {/* State 4 & 5: Accept Invitation Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Key className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Option 1: Accept an Invitation Token</h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            If an administrator issued you an invitation, paste the single-use token below. The invited email must strictly match your signed-in email address (<span className="text-slate-300 font-mono">{user.email}</span>).
          </p>
          <form onSubmit={handleAcceptInvitation} className="flex gap-2">
            <input
              type="text"
              placeholder="Paste 32-character single-use invitation token..."
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
            />
            <button
              type="submit"
              disabled={actionLoading || !inviteToken.trim()}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5"
            >
              {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
              Accept Invitation
            </button>
          </form>
        </div>

        {/* State 6: Request Access Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Send className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Option 2: Request Organisation Access</h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Submit an access request to be reviewed by a Controller or System Administrator. Submitting a request does not grant automatic access.
          </p>
          <form onSubmit={handleSubmitAccessRequest} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Target Organisation ID</label>
                <input
                  type="text"
                  value={targetOrgId}
                  onChange={(e) => setTargetOrgId(e.target.value)}
                  placeholder="e.g. org_default"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Requested Role</label>
                <select
                  value={requestedRole}
                  onChange={(e) => setRequestedRole(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="AP_ASSOCIATE">AP Associate (Verification & Matching)</option>
                  <option value="AP_LEAD">AP Lead (Approval & Routing)</option>
                  <option value="CONTROLLER">Controller (Financial Authorisation)</option>
                  <option value="CATEGORY_MANAGER">Category Manager (Commercials)</option>
                  <option value="AUDITOR">Auditor (Strictly Read-Only)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Business Justification / Reason</label>
              <textarea
                value={accessReason}
                onChange={(e) => setAccessReason(e.target.value)}
                placeholder="State your department, role, and business justification for accessing this AP tenant..."
                rows={2}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={actionLoading || !targetOrgId.trim()}
              className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-xs font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 border border-slate-700"
            >
              {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Submit Access Request
            </button>
          </form>
        </div>
      </div>
    );
  }

  // State 9: Provisioned & Active
  return null;
};
