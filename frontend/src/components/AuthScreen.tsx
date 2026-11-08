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
} from "lucide-react";

import { api, setAuthToken } from "../api/client";

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

  const [authStatusFailed, setAuthStatusFailed] = useState(false);

  const [showGoogleSetup, setShowGoogleSetup] = useState(false);
  const [emailOtp, setEmailOtp] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [otpStep, setOtpStep] = useState<"input" | "verify">("input");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpSuccessMessage, setOtpSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatusFailed(true));

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
        setAuthToken(res.accessToken);
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
      <div
        className={`auth-screen mx-auto w-full rounded-xl border ${canShowQuickLogin ? "auth-screen--split" : "auth-screen--single"}`}
      >
        <div className="auth-intro">
          <div className="auth-brand flex items-center gap-3">
            <span className="auth-mark flex h-11 w-11 items-center justify-center rounded-lg">
              <Shield className="h-5 w-5" aria-hidden="true" />
            </span>

            <span className="text-sm font-semibold">AP Command Center</span>
          </div>

          <h1 className="auth-title mt-7 font-semibold tracking-tight">
            Sign in to your workspace
          </h1>

          <p className="auth-muted mt-2 text-sm leading-relaxed">
            Sign in to review supplier invoices and manage internal approvals.
          </p>

          {error && (
            <div
              role="alert"
              className="auth-error mt-6 rounded-lg border p-4 text-sm"
            >
              <p className="font-semibold">Could not sign in</p>

              <p className="mt-1 break-words">{error}</p>

              <p className="mt-2">
                Retry your session or sign in again. If the problem continues,
                contact your workspace administrator.
              </p>

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
              className="auth-notice mt-6 rounded-lg border p-4 text-sm break-words"
            >
              {actionMessage.text}
            </div>
          )}

          <ul
            className="auth-journey"
            aria-label="What you can do in the workspace"
          >
            <li>
              <strong>Submit</strong>
              <span>Bring in a supplier’s bill as a document.</span>
            </li>

            <li>
              <strong>Inspect</strong>
              <span>Compare the bill with orders, receipts and checks.</span>
            </li>

            <li>
              <strong>Explain</strong>
              <span>Follow the recorded decision and its evidence.</span>
            </li>
          </ul>

          <section className="auth-sign-in mt-7 space-y-4" aria-label="Sign in">
            <div className="auth-email-flow space-y-3">
              {otpStep === "input" ? (
                <form onSubmit={handleSendOtp} className="space-y-3">
                  <div>
                    <label htmlFor="evaluator-email" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      Evaluator or Work Email
                    </label>
                    <input
                      id="evaluator-email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="evaluator@company.com"
                      value={emailOtp}
                      onChange={(e) => setEmailOtp(e.target.value)}
                      disabled={otpLoading}
                      className="auth-input w-full rounded-lg border px-3 py-2.5 text-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={otpLoading || !emailOtp.trim()}
                    className="auth-primary w-full rounded-lg px-4 py-2.5 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {otpLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Sending code…</span>
                      </>
                    ) : (
                      <>
                        <Mail className="w-4 h-4" />
                        <span>Send Verification Code</span>
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-3">
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800">
                    {otpSuccessMessage || `Code sent to ${emailOtp}`}
                  </div>
                  <div>
                    <label htmlFor="otp-code" className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                      Enter 6-Digit Verification Code
                    </label>
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
                      className="auth-input w-full text-center tracking-widest font-mono text-lg rounded-lg border px-3 py-2"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setOtpStep("input");
                        setVerificationCode("");
                      }}
                      disabled={otpLoading}
                      className="auth-option px-3 py-2 text-xs font-medium rounded-lg border"
                    >
                      Change Email
                    </button>
                    <button
                      type="submit"
                      disabled={otpLoading || verificationCode.length < 6}
                      className="auth-primary flex-1 rounded-lg px-4 py-2 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {otpLoading ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Verifying…</span>
                        </>
                      ) : (
                        <span>Verify & Sign In</span>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>

            <div className="relative my-3 flex items-center justify-center">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-200"></div></div>
              <span className="relative bg-white dark:bg-slate-900 px-3 text-xs uppercase text-slate-400">or</span>
            </div>

            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={!isGoogleEnabled}
              aria-describedby={
                !isGoogleEnabled ? "google-sign-in-status" : undefined
              }
              className="auth-option w-full rounded-lg px-4 py-2.5 text-sm font-semibold border flex items-center justify-center gap-2 disabled:cursor-not-allowed"
            >
              Continue with Google
            </button>

            {!isGoogleEnabled && (
              <p
                id="google-sign-in-status"
                className="auth-muted text-sm leading-relaxed"
                role="status"
              >
                {authStatusFailed
                  ? "Sign-in options could not be checked. Refresh this page or contact your workspace administrator."
                  : !authStatus
                    ? "Checking available sign-in options…"
                    : "Google sign-in is not reported as available. Contact your workspace administrator."}
              </p>
            )}

            {!isGoogleEnabled && authStatus && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowGoogleSetup(!showGoogleSetup)}
                  aria-expanded={showGoogleSetup}
                  className="auth-link text-sm font-medium"
                >
                  {showGoogleSetup
                    ? "Hide administrator setup details"
                    : "Administrator setup details"}
                </button>

                {showGoogleSetup && (
                  <p className="auth-muted mt-2 text-sm leading-relaxed">
                    The administrator can configure the Google provider and
                    allowed redirect URLs in the connected identity service.
                  </p>
                )}
              </div>
            )}

            <p className="auth-muted text-sm">
              Need access? Ask your workspace administrator for an invitation.
            </p>
          </section>
        </div>

        {isLocalEnv && (
          <div className="auth-evaluation">
            {canShowQuickLogin && (
              <section
                className="auth-secondary"
                aria-labelledby="quick-access-title"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-1">
                  <h2
                    id="quick-access-title"
                    className="text-base font-semibold"
                  >
                    Evaluation workspace
                  </h2>

                  <span className="auth-muted text-xs font-medium">
                    Quick sign-in
                  </span>
                </div>

                <p className="auth-muted mt-2 text-sm leading-relaxed">
                  Choose a role for local evaluation. The server verifies
                  access; this workspace may contain imported or live records.
                </p>

                <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
                  {[
                    {
                      label: "AP Lead",
                      description: "Review invoices",
                      email: "sme_lead@company.internal",
                    },

                    {
                      label: "Financial Controller",
                      description: "Review and sign off",
                      email: "sme_controller@company.internal",
                    },

                    {
                      label: "Auditor",
                      description: "Read-only access",
                      email: "sme_auditor@company.internal",
                    },

                    {
                      label: "AP Associate",
                      description: "Review invoice details",
                      email: "sme_associate@company.internal",
                    },
                  ].map((item) => (
                    <button
                      key={item.email}
                      type="button"
                      disabled={actionLoading}
                      onClick={() =>
                        handleQuickLogin(item.email, "org_sme_eval", false)
                      }
                      className="auth-option rounded-lg border px-4 py-3 text-left disabled:opacity-50"
                    >
                      <span className="block text-sm font-semibold">
                        {item.label}
                      </span>

                      <span className="auth-muted mt-1 block text-xs">
                        {actionLoading ? "Signing in…" : item.description}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {isLocalEnv && (
              <details className="auth-developer mt-5 border-t pt-4">
                <summary className="auth-link cursor-pointer text-sm">
                  Developer token access
                </summary>

                <div className="mt-3 space-y-2">
                  <label
                    htmlFor="developer-token"
                    className="block text-sm font-medium"
                  >
                    Bearer token
                  </label>

                  <div className="flex flex-wrap gap-2">
                    <input
                      id="developer-token"
                      type="password"
                      autoComplete="off"
                      value={devTokenInput}
                      onChange={(e) => setDevTokenInput(e.target.value)}
                      className="auth-input min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm"
                    />

                    <button
                      type="button"
                      onClick={() => handleApplyDevToken(devTokenInput)}
                      className="auth-option rounded-lg border px-3 py-2 text-sm font-medium"
                    >
                      Apply token
                    </button>
                  </div>
                </div>
              </details>
            )}
          </div>
        )}
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
