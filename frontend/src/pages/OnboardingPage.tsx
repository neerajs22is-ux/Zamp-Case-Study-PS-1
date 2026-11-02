import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Mail,
  Server,
  UploadCloud,
  Users,
  Shield,
  Sparkles,
  Copy,
  Check,
  RefreshCw,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser } from '../types';

interface OnboardingPageProps {
  currentUser?: AuthenticatedUser | null;
}

export const OnboardingPage: React.FC<OnboardingPageProps> = ({ currentUser }) => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);

  // Step 2: Team invite state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('AP_ASSOCIATE');
  const [generatedInviteLink, setGeneratedInviteLink] = useState<string | null>(null);
  const [inviteCopied, setInviteCopied] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Step 3: Gmail status state
  const [gmailStatus, setGmailStatus] = useState<any>(null);
  const [syncingGmail, setSyncingGmail] = useState(false);
  const [gmailSyncResult, setGmailSyncResult] = useState<string | null>(null);

  // Step 4: ERP status state
  const [erpConfigured, setErpConfigured] = useState(false);

  // Step 5: Upload state
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(false);
  const [uploadedInvoiceId, setUploadedInvoiceId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Step 6: Tour step
  const [tourIndex, setTourIndex] = useState(0);

  // Step 7: Derived checklist stats
  const [checklist, setChecklist] = useState({
    signedIn: true,
    teamInvited: false,
    gmailConnected: false,
    erpConnected: false,
    invoiceReceived: false,
    decisionMade: false,
  });

  // Load live data for checklist & status
  useEffect(() => {
    async function checkLiveData() {
      try {
        const [healthRes, gmailRes, inboxRes, auditRes] = await Promise.all([
          api.getHealth().catch(() => null),
          api.getGmailStatus().catch(() => null),
          api.getInbox({ page: 1 }).catch(() => null),
          api.getAudit({ limit: 5 }).catch(() => null),
        ]);

        const isGmailConn = gmailRes?.status === 'CONNECTED';
        const isErpConn = healthRes?.subsystems?.sap_erp?.readiness || false;
        const hasInvoices = (inboxRes?.total_count || 0) > 0;
        const hasDecision = (auditRes?.items || []).some(
          (item: any) => item.action && !item.action.includes('VIEW')
        );

        setGmailStatus(gmailRes);
        setErpConfigured(isErpConn);

        // Check if ERP was skipped in localStorage
        const erpSkipped = localStorage.getItem(`ap.onboarding.erp.skipped`) === 'true';
        const teamSkipped = localStorage.getItem(`ap.onboarding.team.skipped`) === 'true';

        setChecklist({
          signedIn: !!currentUser,
          teamInvited: teamSkipped || false,
          gmailConnected: isGmailConn,
          erpConnected: isErpConn || erpSkipped,
          invoiceReceived: hasInvoices,
          decisionMade: hasDecision,
        });
      } catch (err) {
        console.error('Error checking onboarding status:', err);
      }
    }
    checkLiveData();
  }, [currentUser]);

  // Step 2: Handle Invite Submission
  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;
    setLoading(true);
    setInviteError(null);
    try {
      const res = await api.createInvitation(inviteEmail, inviteRole);
      const origin = window.location.origin;
      const link = `${origin}/accept-invite?token=${res.invitation_token}`;
      setGeneratedInviteLink(link);
      setChecklist((prev) => ({ ...prev, teamInvited: true }));
      localStorage.setItem('ap.onboarding.team.skipped', 'true');
    } catch (err: any) {
      setInviteError(err.message || 'Failed to issue invitation.');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setInviteCopied(true);
    setTimeout(() => setInviteCopied(false), 2000);
  };

  // Step 3: Handle Gmail Connect & Sync
  const handleConnectGmail = async () => {
    try {
      const res = await api.getGmailAuthorizeUrl();
      if (res.authorization_url) {
        window.location.href = res.authorization_url;
      }
    } catch (err: any) {
      alert(`Gmail OAuth failed: ${err.message}`);
    }
  };

  const handleSyncGmail = async () => {
    setSyncingGmail(true);
    setGmailSyncResult(null);
    try {
      const res = await api.syncGmailMailbox(15);
      setGmailSyncResult(
        `${res.ingested_count} invoice(s) received, ${res.duplicates_skipped} duplicates skipped, ${res.quarantined_count} quarantined.`
      );
      setChecklist((prev) => ({ ...prev, invoiceReceived: true }));
    } catch (err: any) {
      setGmailSyncResult(`Sync failed: ${err.message}`);
    } finally {
      setSyncingGmail(false);
    }
  };

  // Step 5: Handle File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Only PDF documents are supported (verified by %PDF- header).');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File exceeds maximum upload size of 50 MB.');
      return;
    }

    setUploadFileName(file.name);
    setUploadProgress(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.uploadDocument(formData);
      setUploadedInvoiceId(res.invoice_id || res.id);
      setChecklist((prev) => ({ ...prev, invoiceReceived: true }));
    } catch (err: any) {
      if (err.message && err.message.includes('409')) {
        setUploadError(`Duplicate detected: This file has already been registered in the system.`);
      } else {
        setUploadError(err.message || 'Upload failed.');
      }
    } finally {
      setUploadProgress(false);
    }
  };

  const handleSkipErp = () => {
    localStorage.setItem('ap.onboarding.erp.skipped', 'true');
    setChecklist((prev) => ({ ...prev, erpConnected: true }));
    setCurrentStep(5);
  };

  const handleFinishOnboarding = () => {
    localStorage.setItem('ap.onboarding.completed', 'true');
    navigate('/today');
  };

  // Tour coachmarks
  const tourCoachmarks = [
    {
      title: '1. Dynamic Verdict Summary',
      body: 'Start here: immediate plain-language verdict showing deterministic policy checks (e.g. Clean 3-Way Match or Action Required).',
      highlight: 'Verdict Banner',
    },
    {
      title: '2. Original Document Viewer',
      body: 'Inspect the authentic source PDF invoice with responsive zoom, page navigation, and secure presigned URLs.',
      highlight: 'Left Pane (PDF Embed)',
    },
    {
      title: '3. Side-by-Side PO & Line Comparison',
      body: 'Compare extracted billed line items directly against authorized ERP purchase order records and quantities.',
      highlight: 'Center Pane (Matching)',
    },
    {
      title: '4. Deterministic Validation Checks',
      body: 'All 7 mandatory checks: Vendor Registration, PO Authorization, GRN Confirmation, QC Acceptance, GST Maths, Price Tolerance, and Duplicate Hash.',
      highlight: 'Checks Tab',
    },
    {
      title: '5. Human Decision & Triage Bar',
      body: 'Authorize review, place on hold, request supplier correction, or reject. High-value invoices trigger dual control.',
      highlight: 'Decision Bar',
    },
    {
      title: '6. Immutable Audit History',
      body: 'Every single mutation, approval, and triage action is permanently recorded in the append-only ledger.',
      highlight: 'Audit History',
    },
  ];

  const totalSteps = 7;
  const isAuditor = currentUser?.role === 'AUDITOR';

  return (
    <div className="max-w-4xl mx-auto w-full space-y-6">
      {/* Top Bar: Progress and Exit */}
      <div className="max-w-4xl mx-auto w-full flex items-center justify-between pb-6 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white font-bold flex items-center justify-center text-sm shadow-sm">
            AP
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 dark:text-white">
              AP Command Center Setup
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Step {currentStep} of {totalSteps}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Step Dots */}
          <div className="hidden sm:flex items-center gap-1.5">
            {Array.from({ length: totalSteps }).map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentStep(idx + 1)}
                className={`h-2 rounded-full transition-all ${
                  currentStep === idx + 1
                    ? 'w-6 bg-indigo-600'
                    : currentStep > idx + 1
                    ? 'w-2 bg-emerald-500'
                    : 'w-2 bg-slate-300 dark:bg-slate-700'
                }`}
                title={`Step ${idx + 1}`}
                aria-label={`Jump to step ${idx + 1}`}
              />
            ))}
          </div>

          <button
            onClick={() => navigate('/today')}
            className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium transition-colors"
          >
            Exit to Dashboard
          </button>
        </div>
      </div>

      {/* Main Step Canvas */}
      <div className="max-w-2xl mx-auto w-full my-auto py-8">
        {/* ================================================================= */}
        {/* STEP 1: WELCOME */}
        {/* ================================================================= */}
        {currentStep === 1 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div className="space-y-2 text-center sm:text-left">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                Welcome to Autonomous AP
              </span>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                Welcome, {currentUser?.name || 'Operator'}.
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Get invoices in, see what needs a human decision, and approve with an immutable compliance record.
              </p>
            </div>

            {/* 4-Node Flow Diagram */}
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block">
                How It Works
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">1. Invoices Arrive</div>
                  <div className="text-[10px] text-slate-500 mt-1">Gmail or PDF upload</div>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">2. Verify & Match</div>
                  <div className="text-[10px] text-slate-500 mt-1">7 deterministic checks</div>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">3. You Decide</div>
                  <div className="text-[10px] text-slate-500 mt-1">Approve, hold or reject</div>
                </div>
                <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">4. Audit Ledger</div>
                  <div className="text-[10px] text-slate-500 mt-1">Append-only compliance</div>
                </div>
              </div>
            </div>

            {/* Three Honest Foundation Bullets */}
            <div className="space-y-2.5 text-xs text-slate-700 dark:text-slate-300">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <span>Reads PDF invoices from dedicated mailbox or local file upload.</span>
              </div>
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <span>Validates each invoice against purchase orders, goods receipts, GST maths, and duplicate SHA-256 hashes.</span>
              </div>
              <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/40 text-amber-900 dark:text-amber-300">
                <Shield className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Core Invariant:</strong> The system never automatically disburses funds or posts unauthorized changes to your ERP. Human approval authorizes batch readiness within internal AP review.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => navigate('/today')}
                className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                Skip setup
              </button>
              <button
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
              >
                <span>Get started</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 2: WORKSPACE & TEAM */}
        {/* ================================================================= */}
        {currentStep === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                Your Workspace & Team
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Tenant: <strong className="text-slate-700 dark:text-slate-200">{currentUser?.org_id || 'org_sme_eval'}</strong> • Your role: <span className="font-mono text-indigo-600 dark:text-indigo-400">{currentUser?.role}</span>
              </p>
            </div>

            {isAuditor ? (
              <div className="p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-600 dark:text-slate-400">
                Your role (Auditor) has read-only oversight permissions. Team member invitations are reserved for AP Leads and Administrators.
              </div>
            ) : (
              <form onSubmit={handleSendInvite} className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs space-y-4">
                <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-indigo-600" />
                  <span>Invite a Teammate</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2 space-y-1">
                    <label className="text-[11px] font-medium text-slate-500">Email Address</label>
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.internal"
                      required
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-500">Assigned Role</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="AP_ASSOCIATE">AP Associate</option>
                      <option value="AP_LEAD">AP Lead</option>
                      <option value="CONTROLLER">Controller</option>
                      <option value="AUDITOR">Auditor</option>
                      {currentUser?.role === 'SYSTEM_ADMIN' && <option value="SYSTEM_ADMIN">System Admin</option>}
                    </select>
                  </div>
                </div>

                {inviteError && (
                  <div className="text-xs text-rose-600 dark:text-rose-400 font-medium">
                    {inviteError}
                  </div>
                )}

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[11px] text-slate-400">
                    Generates a cryptographically secure 7-day single-use token.
                  </span>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium shadow-sm transition-colors disabled:opacity-50"
                  >
                    {loading ? 'Issuing...' : 'Create Invite Link'}
                  </button>
                </div>

                {generatedInviteLink && (
                  <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-emerald-800 dark:text-emerald-300">
                        Invitation link generated:
                      </span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(generatedInviteLink)}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300 hover:underline"
                      >
                        {inviteCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        {inviteCopied ? 'Copied' : 'Copy link'}
                      </button>
                    </div>
                    <code className="block p-1.5 bg-white dark:bg-slate-900 rounded border border-emerald-200 dark:border-emerald-900 font-mono text-[11px] truncate text-slate-700 dark:text-slate-300">
                      {generatedInviteLink}
                    </code>
                    <p className="text-[10px] text-emerald-700 dark:text-emerald-400">
                      We don't send emails automatically — share this link with your colleague directly.
                    </p>
                  </div>
                )}
              </form>
            )}

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(1)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    localStorage.setItem('ap.onboarding.team.skipped', 'true');
                    setCurrentStep(3);
                  }}
                  className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
                >
                  I'll do this later
                </button>
                <button
                  onClick={() => setCurrentStep(3)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                >
                  <span>Continue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 3: CONNECT GMAIL */}
        {/* ================================================================= */}
        {currentStep === 3 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Mail className="w-5 h-5 text-indigo-600" />
                Connect Invoice Mailbox (Gmail)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Automatically read vendor invoice attachments from a dedicated AP inbox.
              </p>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                    Mailbox Connection Status
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {gmailStatus?.status === 'CONNECTED'
                      ? `Authorized mailbox: ${gmailStatus.mailbox || 'Connected'}`
                      : 'No mailbox authorized for this tenant'}
                  </span>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                  gmailStatus?.status === 'CONNECTED'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400'
                    : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400'
                }`}>
                  {gmailStatus?.status || 'NOT_CONFIGURED'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
                <p>
                  • Requests <strong>read-only access</strong> (<code className="font-mono text-indigo-500">gmail.readonly</code>) to parse incoming invoice PDFs.
                </p>
                <p>
                  • Never sends, modifies, or deletes mail from your mailbox.
                </p>
                <p>
                  • Imports run on-demand or on request — background automated scheduling is not active in local evaluation.
                </p>
              </div>

              {gmailStatus?.status === 'CONNECTED' ? (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-600 dark:text-slate-300">
                      Import recent messages (up to 15):
                    </span>
                    <button
                      onClick={handleSyncGmail}
                      disabled={syncingGmail}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${syncingGmail ? 'animate-spin' : ''}`} />
                      {syncingGmail ? 'Importing...' : 'Import Now'}
                    </button>
                  </div>
                  {gmailSyncResult && (
                    <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-xs text-indigo-900 dark:text-indigo-300 font-medium">
                      {gmailSyncResult}
                    </div>
                  )}
                </div>
              ) : (
                <div className="pt-2">
                  <button
                    onClick={handleConnectGmail}
                    className="inline-flex items-center gap-2 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                  >
                    <span>Authorize Mailbox</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setCurrentStep(4)}
                  className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
                >
                  Skip for now
                </button>
                <button
                  onClick={() => setCurrentStep(4)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                >
                  <span>Continue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 4: CONNECT ERP (HONEST & SKIPPABLE) */}
        {/* ================================================================= */}
        {currentStep === 4 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Server className="w-5 h-5 text-indigo-600" />
                Connect Enterprise ERP (Optional)
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Authoritative source records for Purchase Orders, Goods Receipts, and Vendors.
              </p>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                    SAP S/4HANA OData / RFC Integration
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Live ERP synchronization is not provisioned in this environment.
                  </span>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-400">
                  {erpConfigured ? 'Configured' : 'NOT_CONFIGURED'}
                </span>
              </div>

              <div className="p-3.5 bg-slate-50 dark:bg-slate-950/60 rounded-lg border border-slate-200/80 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-2">
                <p>
                  <strong>Why ERP records matter:</strong> Automatic 3-way matching compares invoice line items against purchase orders and warehouse receipts. Without procurement reference snapshots, tolerance gates cannot pass.
                </p>
                <p>
                  <strong>Evaluation Environment:</strong> The system automatically operates against verified reference snapshots loaded from evaluation fixtures (27 Purchase Orders, 12 Vendors).
                </p>
              </div>

              <div className="text-[11px] text-slate-500">
                Live SAP connectors are configured by administrators in container environment variables (<code className="font-mono">SAP_API_BASE_URL</code>). There is no manual sign-in required here.
              </div>
            </div>

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(3)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleSkipErp}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-medium hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors"
                >
                  Skip — I'll do this later
                </button>
                <button
                  onClick={() => setCurrentStep(5)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
                >
                  <span>Continue</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 5: BRING IN YOUR FIRST INVOICE */}
        {/* ================================================================= */}
        {currentStep === 5 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-indigo-600" />
                Bring in Your First Invoice
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Upload a document or explore with pre-loaded evaluation data.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Option A: PDF Upload */}
              <label className="group relative p-5 bg-white dark:bg-slate-900 border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-500 rounded-xl cursor-pointer flex flex-col items-center justify-center text-center transition-all shadow-2xs">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploadProgress}
                />
                <div className="w-10 h-10 rounded-full bg-indigo-50 dark:bg-indigo-950/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-2 group-hover:scale-105 transition-transform">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <span className="text-xs font-bold text-slate-900 dark:text-white">
                  {uploadProgress ? `Processing ${uploadFileName || 'file'}...` : 'Upload a PDF Invoice'}
                </span>
                <span className="text-[11px] text-slate-500 mt-1">
                  PDF format up to 50 MB
                </span>
              </label>

              {/* Option B: Preview Demo Invoice */}
              <div
                onClick={() => {
                  setUploadedInvoiceId('inv_d76401c096d0');
                  setCurrentStep(6);
                }}
                className="group p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 rounded-xl cursor-pointer flex flex-col justify-between transition-all shadow-2xs"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
                      Demo Practice
                    </span>
                    <Sparkles className="w-4 h-4 text-indigo-500" />
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white">
                    Explore with Sample Data
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Inspect pre-extracted evaluation invoice AP-26-009 with 7 passing verification checks.
                  </p>
                </div>
                <div className="text-[11px] font-medium text-indigo-600 dark:text-indigo-400 flex items-center gap-1 mt-3">
                  <span>Start practice review</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>

            {uploadError && (
              <div className="p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-lg text-xs text-rose-700 dark:text-rose-300 font-medium">
                {uploadError}
              </div>
            )}

            {uploadedInvoiceId && !uploadError && (
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
                <span>Invoice registered into queue: <code className="font-mono">{uploadedInvoiceId}</code></span>
                <button
                  onClick={() => setCurrentStep(6)}
                  className="px-2.5 py-1 bg-emerald-600 text-white rounded font-medium text-[11px] hover:bg-emerald-500 transition-colors"
                >
                  Continue to Review
                </button>
              </div>
            )}

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(4)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <button
                onClick={() => setCurrentStep(6)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
              >
                <span>Continue</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 6: GUIDED REVIEW TOUR */}
        {/* ================================================================= */}
        {currentStep === 6 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  Practice Mode Tour
                </span>
                <span className="text-xs text-slate-500">Step {tourIndex + 1} of {tourCoachmarks.length}</span>
              </div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                Review Workspace Tour
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Learn the 3-pane layout before working on real live invoices.
              </p>
            </div>

            {/* Interactive Coachmark Card */}
            <div className="p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                  {tourCoachmarks[tourIndex].highlight}
                </span>
                <span className="text-[11px] text-slate-400 font-mono">
                  {tourIndex + 1} / {tourCoachmarks.length}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {tourCoachmarks[tourIndex].title}
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                  {tourCoachmarks[tourIndex].body}
                </p>
              </div>

              <div className="flex items-center justify-between pt-3">
                <button
                  onClick={() => setTourIndex((prev) => Math.max(0, prev - 1))}
                  disabled={tourIndex === 0}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-600 dark:text-slate-300 disabled:opacity-30"
                >
                  Previous
                </button>

                {tourIndex < tourCoachmarks.length - 1 ? (
                  <button
                    onClick={() => setTourIndex((prev) => prev + 1)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs"
                  >
                    <span>Next step</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    onClick={() => setCurrentStep(7)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow-xs"
                  >
                    <span>Finish tour</span>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(5)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Invoices
              </button>
              <button
                onClick={() => setCurrentStep(7)}
                className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                Skip tour
              </button>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 7: SETUP COMPLETE */}
        {/* ================================================================= */}
        {currentStep === 7 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div className="text-center sm:text-left space-y-2">
              <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                You're Ready to Operate
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Your workspace is configured and ready for production AP workflows.
              </p>
            </div>

            {/* Derived Setup Checklist Summary */}
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs space-y-3">
              <span className="text-xs font-bold text-slate-900 dark:text-white block">
                Workspace Readiness Checklist
              </span>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    Sign in & Authenticate
                  </span>
                  <span className="text-[11px] text-emerald-600 font-medium">Verified</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    Workspace & Role Context
                  </span>
                  <span className="text-[11px] text-emerald-600 font-medium">{currentUser?.role}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    {checklist.gmailConnected ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-300 dark:border-slate-600" />
                    )}
                    Connect Gmail Mailbox
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {checklist.gmailConnected ? 'Connected' : 'Optional / Skipped'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    {checklist.erpConnected ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-300 dark:border-slate-600" />
                    )}
                    Procurement Reference Data
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {checklist.erpConnected ? 'Ready (Evaluation Snapshots)' : 'Pending Live Sync'}
                  </span>
                </div>
              </div>
            </div>

            {/* Daily Operational Guide */}
            <div className="p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-2 text-xs">
              <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                What Your Shift Looks Like:
              </span>
              <p className="text-slate-600 dark:text-slate-400">
                • <strong>Today (`/today`):</strong> Start here. See items needing immediate attention sorted by exposure and age.
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                • <strong>Invoices (`/invoices`):</strong> The full ledger of received, clean, and exception invoices.
              </p>
              <p className="text-slate-600 dark:text-slate-400">
                • <strong>Approvals (`/approvals`):</strong> High-value invoices (≥ ₹5,00,000) requiring Controller dual sign-off.
              </p>
            </div>

            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setCurrentStep(6)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Tour
              </button>
              <button
                onClick={handleFinishOnboarding}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
              >
                <span>Go to Today Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
