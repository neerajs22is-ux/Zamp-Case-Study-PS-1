import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  Key, 
  CheckCircle, 
  Clock, 
  AlertCircle, 
  Copy, 
  Check,
  RefreshCw,
  Mail,
  UserCheck
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser, AccessRequest, UserInvitation, UserRole } from '../types';

interface AccessManagementPageProps {
  currentUser: AuthenticatedUser;
}

const ROLE_DETAILS: Record<string, { label: string; description: string; color: string }> = {
  AP_ASSOCIATE: {
    label: 'AP Associate',
    description: 'Upload, triage line discrepancies, and resolve matching exceptions.',
    color: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800/40'
  },
  AP_LEAD: {
    label: 'AP Lead',
    description: 'Everything an Associate can, plus connect email, invite colleagues, and first approval under ₹5L.',
    color: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800/40'
  },
  CONTROLLER: {
    label: 'Financial Controller',
    description: 'Dual approval for high-value invoices (≥ ₹5L), access reviews, and audit exports.',
    color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40'
  },
  AUDITOR: {
    label: 'Auditor',
    description: 'Read-only access: inspect invoice workspaces, reference data, and full audit ledger.',
    color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800/40'
  },
  SYSTEM_ADMIN: {
    label: 'System Administrator',
    description: 'Full workspace management, security governance, and system-wide configurations.',
    color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40'
  }
};

export const AccessManagementPage: React.FC<AccessManagementPageProps> = ({ currentUser }) => {
  const [activeTab, setActiveTab] = useState<'members' | 'requests' | 'invite'>('members');
  
  // Members state
  const [members, setMembers] = useState<any[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(true);

  // Requests state
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  
  // General feedback
  const [error, setError] = useState<string | null>(null);

  // Invitation Form State
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('AP_ASSOCIATE');
  const [inviting, setInviting] = useState(false);
  const [generatedInvite, setGeneratedInvite] = useState<UserInvitation | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);

  // Review Dialog State
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewAction, setReviewAction] = useState<'APPROVE' | 'REJECT'>('APPROVE');
  const [reviewRole, setReviewRole] = useState<UserRole>('AP_ASSOCIATE');
  const [reviewReason, setReviewReason] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);

  const isSystemAdmin = currentUser.role === 'SYSTEM_ADMIN';
  const isController = currentUser.role === 'CONTROLLER';
  const isLead = currentUser.role === 'AP_LEAD';
  const canReviewRequests = isSystemAdmin || isController;
  const canInvite = isSystemAdmin || isController || isLead;

  const loadMembers = async () => {
    setLoadingMembers(true);
    try {
      const res = await api.getMembers();
      setMembers(res.items || []);
    } catch (err: any) {
      console.error('Failed to load members:', err);
    } finally {
      setLoadingMembers(false);
    }
  };

  const loadAccessRequests = async () => {
    setLoadingRequests(true);
    try {
      const data = await api.getOrganisationAccessRequests();
      setRequests(data);
    } catch (err: any) {
      console.error('Failed to load access requests:', err);
    } finally {
      setLoadingRequests(false);
    }
  };

  useEffect(() => {
    loadMembers();
    loadAccessRequests();
  }, []);

  const handleCreateInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    try {
      setInviting(true);
      setError(null);
      const inv = await api.createInvitation(inviteEmail.trim(), inviteRole);
      setGeneratedInvite(inv);
      setInviteEmail('');
    } catch (err: any) {
      setError(err.message || 'Failed to generate invitation.');
    } finally {
      setInviting(false);
    }
  };

  const handleCopyToken = () => {
    if (generatedInvite) {
      navigator.clipboard.writeText(generatedInvite.invitation_token);
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewingId) return;
    try {
      setSubmittingReview(true);
      setError(null);
      await api.reviewAccessRequest(
        reviewingId,
        reviewAction,
        reviewAction === 'APPROVE' ? reviewRole : undefined,
        reviewReason.trim() || undefined
      );
      setReviewingId(null);
      setReviewReason('');
      await loadAccessRequests();
      await loadMembers();
    } catch (err: any) {
      setError(err.message || 'Failed to review access request.');
    } finally {
      setSubmittingReview(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
            <Users className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Team & Access Control
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Manage organization team members, assign dual-approval permissions, and review workspace access requests.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              loadMembers();
              loadAccessRequests();
            }}
            disabled={loadingMembers || loadingRequests}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingMembers || loadingRequests ? 'animate-spin' : ''}`} />
            Refresh Roster
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-3.5 rounded-xl border bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-950/30 dark:border-rose-800/40 dark:text-rose-200 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800/80 text-xs overflow-x-auto whitespace-nowrap max-w-full">
        <button
          onClick={() => setActiveTab('members')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
            activeTab === 'members'
              ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <UserCheck className="w-3.5 h-3.5 text-indigo-500" />
          <span>Active Members</span>
          <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-700 font-mono">
            {members.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('requests')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
            activeTab === 'requests'
              ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Clock className="w-3.5 h-3.5 text-indigo-500" />
          <span>Pending Requests</span>
          {requests.filter(r => r.status === 'PENDING').length > 0 && (
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300 font-mono font-bold">
              {requests.filter(r => r.status === 'PENDING').length}
            </span>
          )}
        </button>

        {canInvite && (
          <button
            onClick={() => setActiveTab('invite')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-colors ${
              activeTab === 'invite'
                ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <UserPlus className="w-3.5 h-3.5 text-indigo-500" />
            <span>Invite Colleague</span>
          </button>
        )}
      </div>

      {/* Tab 1: Active Members Roster */}
      {activeTab === 'members' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden">
          {loadingMembers ? (
            <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
              <span>Loading organization member roster...</span>
            </div>
          ) : members.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
              No active members found for this organization.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[680px]">
                <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-4 font-medium">Member</th>
                    <th className="py-2.5 px-4 font-medium">Assigned Role & Responsibilities</th>
                    <th className="py-2.5 px-4 font-medium">Status</th>
                    <th className="py-2.5 px-4 font-medium text-right">Identifier</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {members.map((m) => {
                    const roleInfo = ROLE_DETAILS[m.role] || {
                      label: m.role || 'Member',
                      description: 'Standard organization member.',
                      color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
                    };
                    const initials = (m.full_name || m.email || 'U')
                      .split(' ')
                      .map((n: string) => n[0])
                      .join('')
                      .toUpperCase()
                      .substring(0, 2);

                    return (
                      <tr key={m.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800/40 flex items-center justify-center font-bold font-mono text-xs">
                              {initials}
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900 dark:text-white">
                                {m.full_name || m.email.split('@')[0]}
                                {m.id === currentUser.id && (
                                  <span className="ml-2 text-[10px] font-normal text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-1.5 py-0.5 rounded border border-indigo-200 dark:border-indigo-800/40">
                                    You
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                                {m.email}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4 max-w-md">
                          <div className="space-y-1">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border font-sans ${roleInfo.color}`}>
                              {roleInfo.label}
                            </span>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-normal">
                              {roleInfo.description}
                            </p>
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            {m.status || 'ACTIVE'}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right font-mono text-[11px] text-slate-400 dark:text-slate-500">
                          {m.id}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Pending Access Requests */}
      {activeTab === 'requests' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden">
          {loadingRequests ? (
            <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
              <span>Querying organization access requests...</span>
            </div>
          ) : requests.length === 0 ? (
            <div className="py-12 text-center text-xs space-y-2 px-4">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
              <div className="font-semibold text-slate-700 dark:text-slate-300">
                No pending access requests
              </div>
              <p className="text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
                All account creation and role promotion requests for this organization have been reviewed.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-950/60 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-4 font-medium">Applicant</th>
                    <th className="py-2.5 px-4 font-medium">Requested Role</th>
                    <th className="py-2.5 px-4 font-medium">Status</th>
                    <th className="py-2.5 px-4 font-medium">Submission Date</th>
                    <th className="py-2.5 px-4 font-medium text-right">Review Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {requests.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 dark:text-white">
                          {r.full_name || 'Applicant'}
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {r.email}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span className="font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                          {r.requested_role}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                          r.status === 'PENDING'
                            ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800/40'
                            : r.status === 'APPROVED'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40'
                            : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40'
                        }`}>
                          {r.status}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400">
                        {new Date(r.created_at).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric'
                        })}
                      </td>

                      <td className="py-3 px-4 text-right">
                        {r.status === 'PENDING' ? (
                          canReviewRequests ? (
                            <button
                              onClick={() => {
                                setReviewingId(r.id);
                                setReviewRole((r.requested_role as UserRole) || 'AP_ASSOCIATE');
                                setReviewAction('APPROVE');
                              }}
                              className="px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-sm transition-colors"
                            >
                              Review & Sign
                            </button>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">
                              Controller/Admin required
                            </span>
                          )
                        ) : (
                          <span className="text-slate-400 text-[11px]">
                            Resolved ({r.reviewed_at ? new Date(r.reviewed_at).toLocaleDateString('en-IN') : 'Completed'})
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Invite New Member */}
      {activeTab === 'invite' && canInvite && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm max-w-2xl">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-1">
            <UserPlus className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            Issue Organization Invitation
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
            Generates a signed cryptographically secure one-time invitation token. Invitations expire in 7 days.
          </p>

          <form onSubmit={handleCreateInvitation} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Colleague Corporate Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.internal"
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-sm font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Assigned Role & Authority
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as UserRole)}
                className="w-full px-3 py-2 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500 shadow-sm"
              >
                <option value="AP_ASSOCIATE">AP Associate — Upload, triage line items, resolve exceptions</option>
                <option value="AP_LEAD">AP Lead — Connect email, invite colleagues, approve invoices &lt; ₹5L</option>
                <option value="CONTROLLER">Financial Controller — Dual approval ≥ ₹5L, access review, audit export</option>
                <option value="AUDITOR">Auditor — Read-only access to workspaces and audit log</option>
                {isSystemAdmin && (
                  <option value="SYSTEM_ADMIN">System Administrator — Full workspace governance</option>
                )}
              </select>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-950/50 rounded-lg border border-slate-100 dark:border-slate-800/60 text-xs text-slate-600 dark:text-slate-400">
              <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-0.5">Note on Dispatch:</span>
              We generate the verified registration link. Because outbound SMTP is unconfigured in this tier, you will copy the invite link and share it securely with your colleague.
            </div>

            <button
              type="submit"
              disabled={inviting || !inviteEmail.trim()}
              className="w-full py-2 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs shadow-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              <Key className="w-3.5 h-3.5" />
              {inviting ? 'Generating Token...' : 'Generate Secure Invitation Link'}
            </button>
          </form>

          {/* Generated Invite Modal / Card */}
          {generatedInvite && (
            <div className="mt-5 p-4 rounded-xl border border-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/20 dark:border-emerald-800/40 space-y-3">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-semibold text-xs">
                <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Invitation Token Created Successfully</span>
              </div>
              
              <div className="space-y-1.5">
                <div className="text-[11px] text-slate-600 dark:text-slate-400">
                  Assigned Email: <strong className="font-mono text-slate-900 dark:text-white">{generatedInvite.email}</strong>
                </div>
                <div className="text-[11px] text-slate-600 dark:text-slate-400">
                  Role: <strong className="text-slate-900 dark:text-white">{generatedInvite.role}</strong>
                </div>
                <div className="text-[11px] text-slate-600 dark:text-slate-400">
                  Expires: <strong className="text-slate-900 dark:text-white">{new Date(generatedInvite.expires_at).toLocaleString('en-IN')}</strong> (in 7 days)
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="text"
                  readOnly
                  value={generatedInvite.invitation_token}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleCopyToken}
                  className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-750 inline-flex items-center gap-1.5 shadow-sm"
                >
                  {copiedToken ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 text-slate-500" />}
                  {copiedToken ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Review Dialog Modal */}
      {reviewingId && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Review Organization Access Request
            </h3>
            
            <form onSubmit={handleReviewSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Determination
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setReviewAction('APPROVE')}
                    className={`py-2 rounded-lg font-medium border text-center transition-colors ${
                      reviewAction === 'APPROVE'
                        ? 'bg-emerald-50 border-emerald-300 text-emerald-700 dark:bg-emerald-950/40 dark:border-emerald-800 dark:text-emerald-300'
                        : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    Approve Request
                  </button>
                  <button
                    type="button"
                    onClick={() => setReviewAction('REJECT')}
                    className={`py-2 rounded-lg font-medium border text-center transition-colors ${
                      reviewAction === 'REJECT'
                        ? 'bg-rose-50 border-rose-300 text-rose-700 dark:bg-rose-950/40 dark:border-rose-800 dark:text-rose-300'
                        : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    Reject Request
                  </button>
                </div>
              </div>

              {reviewAction === 'APPROVE' && (
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Grant Role
                  </label>
                  <select
                    value={reviewRole}
                    onChange={(e) => setReviewRole(e.target.value as UserRole)}
                    className="w-full px-3 py-1.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
                  >
                    <option value="AP_ASSOCIATE">AP Associate</option>
                    <option value="AP_LEAD">AP Lead</option>
                    <option value="CONTROLLER">Financial Controller</option>
                    <option value="AUDITOR">Auditor</option>
                    {isSystemAdmin && <option value="SYSTEM_ADMIN">System Administrator</option>}
                  </select>
                </div>
              )}

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Justification / Audit Note (Optional)
                </label>
                <textarea
                  rows={2}
                  value={reviewReason}
                  onChange={(e) => setReviewReason(e.target.value)}
                  placeholder="e.g. Approved per AP hiring plan..."
                  className="w-full px-3 py-1.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setReviewingId(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReview}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-sm transition-colors"
                >
                  {submittingReview ? 'Submitting...' : 'Confirm Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
