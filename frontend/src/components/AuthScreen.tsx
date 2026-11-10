import React, { useState, useEffect } from "react";

import {
  Shield,
  Key,
  CheckCircle,
  Clock,
  AlertCircle,
  UserCheck,
  Send,
  Loader2,
  Mail,
  Sparkles,
  PlayCircle,
  Compass,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

import { api, setAuthToken, setSession } from "../api/client";

import type { AuthenticatedUser, AccessRequest } from "../types";

import "./AuthScreen.css";

import { googleAuthorizeUrl, oauthCallbackParams, sendEmailOtp, verifyEmailOtp } from "../utils/oauth";

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
  const [devTokenInput, setDevTokenInput] = useState("");

  const [inviteToken, setInviteToken] = useState("");

  const [targetOrgId, setTargetOrgId] = useState("org_default");

  const [requestedRole, setRequestedRole] = useState("AP_ASSOCIATE");

  const [accessReason, setAccessReason] = useState("");

  const [actionLoading, setActionLoading] = useState(false);

  const [actionMessage, setActionMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  const [myRequests, setMyRequests] = useState<AccessRequest[]>([]);

  const [requestsError, setRequestsError] = useState(false);

  const [authStatus, setAuthStatus] = useState<any>(null);
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [emailOtp, setEmailOtp] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [otpStep, setOtpStep] = useState<"input" | "verify">("input");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpSuccessMessage, setOtpSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus(null));

    const { error: errDesc } = oauthCallbackParams(
      window.location.search,
      window.location.hash,
    );

    if (errDesc) {
      if (
        errDesc.includes("provider is not enabled") ||
        errDesc.includes("Unsupported provider")
      ) {
        setActionMessage({
          type: "info",

          text: "Google sign-in is not available. Contact your workspace administrator for help.",
        });
      } else {
        setActionMessage({
          type: "error",

          text: `Sign-in failed: ${errDesc}`,
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
    setRequestsError(false);

    try {
      const reqs = await api.getMyAccessRequests();

      setMyRequests(reqs);
    } catch (err: any) {
      console.warn("Failed to load user access requests:", err);

      setRequestsError(true);
    }
  };

  const getSupabaseCredentials = () => {
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || authStatus?.supabase_url || "";
    const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || authStatus?.supabase_anon_key || "";
    return { supabaseUrl, anonKey };
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailOtp.trim()) return;

    const { supabaseUrl, anonKey } = getSupabaseCredentials();
    if (!supabaseUrl || !anonKey) {
      setActionMessage({
        type: "error",
        text: "Identity Provider service is not configured (missing Supabase URL or anon key).",
      });
      return;
    }

    try {
      setOtpLoading(true);
      setActionMessage(null);
      const res = await sendEmailOtp(supabaseUrl, anonKey, emailOtp.trim());
      if (!res.success) {
        setActionMessage({
          type: "error",
          text: res.error || "Failed to send verification code.",
        });
      } else {
        setOtpStep("verify");
        setOtpSuccessMessage(res.message || `Code sent to ${emailOtp.trim()}`);
      }
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "An unexpected error occurred sending OTP.",
      });
    } finally {
      setOtpLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verificationCode.trim()) return;

    const { supabaseUrl, anonKey } = getSupabaseCredentials();
    try {
      setOtpLoading(true);
      setActionMessage(null);
      const res = await verifyEmailOtp(supabaseUrl, anonKey, emailOtp.trim(), verificationCode.trim());
      if (!res.success || !res.accessToken) {
        setActionMessage({
          type: "error",
          text: res.error || "Invalid or expired verification code.",
        });
      } else {
        setSession(res.accessToken, res.refreshToken, res.expiresIn);
        setActionMessage({
          type: "success",
          text: "Verification successful! Opening workspace...",
        });
        onRefreshUser();
      }
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "An unexpected error occurred verifying OTP.",
      });
    } finally {
      setOtpLoading(false);
    }
  };

  const handleGoogleSignIn = () => {
    const supabaseUrl =
      import.meta.env.VITE_SUPABASE_URL || authStatus?.supabase_url || "";

    if (!supabaseUrl) {
      setActionMessage({
        type: "error",

        text: "Supabase URL is not configured in environment variables (VITE_SUPABASE_URL).",
      });

      return;
    }

    window.location.href = googleAuthorizeUrl(
      supabaseUrl,
      window.location.origin,
    );
  };

  const handleApplyDevToken = (token: string) => {
    if (!token.trim()) return;

    if (token.trim().startsWith("test_token:")) {
      setActionMessage({
        type: "error",

        text: "This token type is not accepted. Use an authorized sign-in method.",
      });

      return;
    }

    setAuthToken(token.trim());

    setActionMessage(null);

    onRefreshUser();
  };

  const handleTryLiveDemo = async () => {
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.createDemoSession();
      setAuthToken(res.access_token);
      onRefreshUser();
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "Failed to launch demo session. Please try again.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleQuickLogin = async (
    email: string,
    orgId = "org_sme_eval",
    unprovisioned = false,
  ) => {
    try {
      setActionLoading(true);

      setActionMessage(null);

      const res = await api.getDevSession(email, orgId, unprovisioned);

      setAuthToken(res.access_token);

      onRefreshUser();
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "Quick login failed.",
      });
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

      setActionMessage({
        type: "success",
        text: res.message || "Invitation accepted successfully!",
      });

      setInviteToken("");

      onRefreshUser();
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "Failed to accept invitation.",
      });
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

      const res = await api.submitAccessRequest(
        targetOrgId.trim(),
        accessReason.trim(),
        requestedRole,
      );

      setActionMessage({
        type: "success",
        text: res.message || "Access request submitted successfully.",
      });

      setAccessReason("");

      await loadMyRequests();
    } catch (err: any) {
      setActionMessage({
        type: "error",
        text: err.message || "Failed to submit access request.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div
        className="auth-loading flex flex-col items-center justify-center min-h-[60vh] gap-4"
        role="status"
      >
        <Loader2 className="w-8 h-8 animate-spin" />

        <p className="text-sm font-medium">Checking your session...</p>
      </div>
    );
  }

  if (!user) {
    const isGoogleEnabled = authStatus?.google_oauth_enabled === true;

    const isLocalEnv =
      !import.meta.env.PROD ||
      authStatus?.dev_session_enabled ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "localhost";

    const canShowQuickLogin =
      isLocalEnv && authStatus?.dev_session_enabled === true;

    return (
      <div className="auth-screen auth-screen--split mx-auto w-full rounded-2xl border shadow-xl overflow-hidden">
        {/* Left Column: Context & The 2 Public / Instant Entry Paths */}
        <div className="auth-intro p-6 sm:p-8 flex flex-col justify-between space-y-6">
          <div>
            <div className="auth-brand flex items-center gap-2.5">
              <span className="auth-mark flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400">
                <Shield className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <span className="text-sm font-bold tracking-tight block">Autonomous AP Command Center</span>
                <span className="text-[11px] text-slate-500 font-mono">Zamp PS-1 Evaluation Flagship</span>
              </div>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white mt-6">
              Evaluate Live AP Intelligence
            </h1>

            <p className="auth-muted mt-2 text-xs sm:text-sm leading-relaxed">
              Experience deterministic 3-way matching, Indian GST compliance arithmetic, and 7 sequential financial policy gates.
            </p>

            {error && (
              <div role="alert" className="auth-error mt-4 rounded-xl border p-3.5 text-xs">
                <p className="font-semibold">Session Issue</p>
                <p className="mt-0.5 break-words">{error}</p>
                <button
                  type="button"
                  onClick={onRefreshUser}
                  disabled={loading}
                  className="mt-2 font-semibold underline underline-offset-2 disabled:opacity-50"
                >
                  Retry session
                </button>
              </div>
            )}

            {actionMessage && (
              <div
                role={actionMessage.type === "error" ? "alert" : "status"}
                className="auth-notice mt-4 rounded-xl border p-3.5 text-xs break-words"
              >
                {actionMessage.text}
              </div>
            )}

            {/* Entry Path 1: Try Live Demo */}
            <div className="mt-6 p-4 sm:p-5 rounded-xl border border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20 space-y-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10.5px] font-bold uppercase tracking-wider bg-emerald-200 text-emerald-900 dark:bg-emerald-800 dark:text-emerald-100">
                  <Sparkles className="w-3 h-3" /> Recommended
                </span>
                <span className="text-[11px] font-mono text-emerald-800 dark:text-emerald-300">1-Click Instant</span>
              </div>

              <div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  Try Live Demo
                </h2>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                  Launch a private, isolated demo workspace pre-seeded with authentic Indian GST invoices, POs, and 7-gate match results.
                </p>
              </div>

              <div className="flex flex-wrap gap-1.5 pt-1 text-[11px] text-slate-500">
                <span className="bg-white dark:bg-slate-900 border rounded-md px-2 py-0.5">Isolated RLS Tenant</span>
                <span className="bg-white dark:bg-slate-900 border rounded-md px-2 py-0.5">Zero Sign-Up Required</span>
                <span className="bg-white dark:bg-slate-900 border rounded-md px-2 py-0.5">Custom PDF Upload</span>
              </div>

              <button
                type="button"
                onClick={handleTryLiveDemo}
                disabled={actionLoading}
                className="w-full mt-2 py-2.5 px-4 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                {actionLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Provisioning Demo Workspace…</span>
                  </>
                ) : (
                  <>
                    <PlayCircle className="w-4 h-4" />
                    <span>Launch Live Demo Workspace</span>
                    <ArrowRight className="w-4 h-4 ml-auto" />
                  </>
                )}
              </button>
            </div>

            {/* Entry Path 2: Explore Guided Sandbox */}
            <div className="mt-3.5 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-crimson" /> Explore Guided Sandbox
                </span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">No Login</span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Step through 6 verified commercial scenarios with optical grounding tripwires and 7-gate evidence without logging in.
              </p>
              <a
                href="/sandbox"
                className="w-full py-2 px-3 rounded-lg border border-slate-300 dark:border-slate-700 hover:border-slate-400 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 text-slate-700 dark:text-slate-200 font-semibold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <span>Open Guided Sandbox Experience</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>

        {/* Right Column: Entry Path 3 (Google SSO & Team Sign-In) + Local Dev (if local) */}
        <div className="auth-evaluation p-6 sm:p-8 flex flex-col justify-between space-y-6 bg-slate-50/70 dark:bg-slate-950/40 border-l border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Enterprise & Evaluator Access
              </h2>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Production</span>
            </div>

            <p className="auth-muted mt-1.5 text-xs leading-relaxed">
              For pre-authorized evaluators and enterprise AP team members.
            </p>

            {/* Google SSO Button */}
            <div className="mt-5 space-y-3">
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={!isGoogleEnabled}
                aria-describedby={!isGoogleEnabled ? "google-sign-in-status" : undefined}
                className="w-full rounded-xl py-3 px-4 text-sm font-semibold border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-800 dark:text-white flex items-center justify-center gap-2.5 shadow-xs transition-all disabled:opacity-50 cursor-pointer"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                <span>Continue with Google</span>
              </button>

              <div className="p-3 bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl text-xs text-blue-900 dark:text-blue-300 leading-relaxed">
                <span className="font-semibold block mb-0.5">Approved Evaluator Whitelist</span>
                Google accounts on the evaluator allowlist receive immediate <strong>AP_LEAD</strong> access to the shared <code>org_sme_eval</code> tenant.
              </div>

              {/* Email OTP toggle */}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowEmailForm(!showEmailForm)}
                  className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 font-medium underline underline-offset-2"
                >
                  {showEmailForm ? "Hide email code sign-in" : "Or sign in with email verification code"}
                </button>

                {showEmailForm && (
                  <div className="mt-3 p-3.5 bg-white dark:bg-slate-900 border rounded-xl space-y-3">
                    {otpStep === "input" ? (
                      <form onSubmit={handleSendOtp} className="space-y-2.5">
                        <label htmlFor="evaluator-email" className="block text-[11.5px] font-semibold text-slate-700 dark:text-slate-300">
                          Work or Evaluator Email
                        </label>
                        <input
                          id="evaluator-email"
                          type="email"
                          required
                          placeholder="name@company.com"
                          value={emailOtp}
                          onChange={(e) => setEmailOtp(e.target.value)}
                          disabled={otpLoading}
                          className="w-full rounded-lg border px-3 py-2 text-xs"
                        />
                        <button
                          type="submit"
                          disabled={otpLoading || !emailOtp.trim()}
                          className="w-full py-2 px-3 rounded-lg bg-slate-800 text-white font-semibold text-xs flex items-center justify-center gap-1.5 disabled:opacity-50"
                        >
                          {otpLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                          <span>Send Code</span>
                        </button>
                      </form>
                    ) : (
                      <form onSubmit={handleVerifyOtp} className="space-y-2.5">
                        <div className="text-xs text-emerald-700">{otpSuccessMessage || `Code sent to ${emailOtp}`}</div>
                        <input
                          id="otp-code"
                          type="text"
                          required
                          autoFocus
                          maxLength={6}
                          placeholder="123456"
                          value={verificationCode}
                          onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                          disabled={otpLoading}
                          className="w-full text-center tracking-widest font-mono text-base rounded-lg border px-3 py-2"
                        />
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => { setOtpStep("input"); setVerificationCode(""); }}
                            className="text-xs border rounded-lg px-2 py-1"
                          >
                            Change
                          </button>
                          <button
                            type="submit"
                            disabled={otpLoading || verificationCode.length < 6}
                            className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-700 text-white font-semibold text-xs"
                          >
                            Verify
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Local dev personas (only when canShowQuickLogin is true) */}
            {canShowQuickLogin && (
              <div className="mt-6 pt-5 border-t border-slate-200 dark:border-slate-800">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
                  Local Development Personas (1-Click)
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "AP Lead", email: "sme_lead@company.internal" },
                    { label: "Controller", email: "sme_controller@company.internal" },
                    { label: "Auditor", email: "sme_auditor@company.internal" },
                    { label: "Associate", email: "sme_associate@company.internal" },
                  ].map((p) => (
                    <button
                      key={p.email}
                      type="button"
                      disabled={actionLoading}
                      onClick={() => handleQuickLogin(p.email, "org_sme_eval", false)}
                      className="py-1.5 px-2.5 rounded-lg border text-xs font-medium text-left hover:bg-white dark:hover:bg-slate-900 truncate"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Collapsed / Relocated Bearer Token Drawer */}
          <details className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-800 text-xs">
            <summary className="cursor-pointer text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 select-none">
              Advanced: Authenticate with Bearer Token
            </summary>
            <div className="mt-2.5 flex gap-2">
              <input
                type="password"
                placeholder="Paste JWT token..."
                value={devTokenInput}
                onChange={(e) => setDevTokenInput(e.target.value)}
                className="flex-1 rounded-lg border px-2.5 py-1.5 text-xs font-mono"
              />
              <button
                type="button"
                onClick={() => handleApplyDevToken(devTokenInput)}
                className="px-3 py-1.5 rounded-lg border text-xs font-semibold bg-white dark:bg-slate-900"
              >
                Apply
              </button>
            </div>
          </details>
        </div>
      </div>
    );
  }

  // State 4+: Authenticated BUT Unprovisioned

  if (!user.is_provisioned) {
    const pendingRequest = myRequests.find((r) => r.status === "PENDING");

    return (
      <div className="workspace-access max-w-2xl mx-auto my-8 space-y-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-lg text-amber-600 dark:text-amber-400">
                <UserCheck className="w-5 h-5" />
              </div>

              <div>
                <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                  Workspace access needed
                </h2>

                <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                  {user.email}
                </p>
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
            Your identity is signed in. Workspace access is a separate step:
            accept an invitation, or ask an administrator to review your access
            request. The app will check membership before opening workspace
            records.
          </p>

          {actionMessage && (
            <div
              className={`mt-4 p-3 rounded-lg flex items-start gap-2 text-xs ${
                actionMessage.type === "success"
                  ? "bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
                  : "bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300"
              }`}
            >
              {actionMessage.type === "success" ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              )}

              <span>{actionMessage.text}</span>
            </div>
          )}
        </div>

        {requestsError && (
          <div
            role="alert"
            className="rounded-lg border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40 p-3 text-sm text-rose-800 dark:text-rose-300"
          >
            Could not load your access requests.{" "}
            <button
              type="button"
              onClick={loadMyRequests}
              className="underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* State 7: Pending */}

        {pendingRequest && (
          <div className="bg-sky-50 dark:bg-sky-500/10 border border-sky-200 dark:border-sky-500/30 rounded-xl p-4 flex items-start gap-3 text-sky-800 dark:text-sky-200">
            <Clock className="w-5 h-5 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />

            <div className="text-xs">
              <p className="font-semibold text-slate-900 dark:text-white">
                Access Request Under Review
              </p>

              <p className="mt-1">
                Your request for organisation{" "}
                <span className="font-mono font-semibold text-slate-900 dark:text-white">
                  {pendingRequest.org_id}
                </span>{" "}
                ({pendingRequest.requested_role}) is pending review.
              </p>
            </div>
          </div>
        )}

        <p className="text-sm">
          An invitation token comes from your workspace administrator.
          Requesting a role does not grant it automatically.
        </p>

        {/* State 4 & 5: Accept Invitation */}

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Key className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />

            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Accept an invitation
            </h3>
          </div>

          <form onSubmit={handleAcceptInvitation} className="flex gap-2">
            <input
              type="text"
              aria-label="Invitation token"
              placeholder="Paste your invitation token"
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              className="flex-1 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-indigo-500 font-mono"
            />

            <button
              type="submit"
              disabled={actionLoading || !inviteToken.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors shadow-2xs"
            >
              {actionLoading ? "Verifying..." : "Accept"}
            </button>
          </form>
        </div>

        {/* State 6: Submit Access Request */}

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Send className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />

            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Request workspace access
            </h3>
          </div>

          <form onSubmit={handleSubmitAccessRequest} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="access-workspace-id"
                  className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1"
                >
                  Workspace ID from your administrator
                </label>

                <input
                  type="text"
                  id="access-workspace-id"
                  value={targetOrgId}
                  onChange={(e) => setTargetOrgId(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-slate-200 font-mono"
                />
              </div>

              <div>
                <label
                  htmlFor="access-role"
                  className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1"
                >
                  Requested role
                </label>

                <select
                  id="access-role"
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
              <label
                htmlFor="access-reason"
                className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1"
              >
                Why do you need access?
              </label>

              <textarea
                id="access-reason"
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
