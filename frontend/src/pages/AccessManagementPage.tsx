import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  Key, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertCircle, 
  Copy, 
  Check,
  Loader2
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser, AccessRequest, UserInvitation, UserRole } from '../types';

interface AccessManagementPageProps {
  currentUser: AuthenticatedUser;
}

export const AccessManagementPage: React.FC<AccessManagementPageProps> = ({ currentUser }) => {
  const [activeTab, setActiveTab] = useState<'requests' | 'invite'>('requests');
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [loading, setLoading] = useState(true);
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

  useEffect(() => {
    loadAccessRequests();
  }, []);

  const loadAccessRequests = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getOrganisationAccessRequests();
      setRequests(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load access requests.');
    } finally {
      setLoading(false);
    }
  };

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
    } catch (err: any) {
      setError(err.message || 'Failed to submit review.');
    } finally {
      setSubmittingReview(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-800 pb-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Users className="w-5 h-5 text-indigo-400" />
            Organisation Team & Access Management
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage employee invitations, review uninvited access requests, and enforce strict role boundaries.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('requests')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === 'requests'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            Access Requests ({requests.filter((r) => r.status === 'PENDING').length})
          </button>
          <button
            onClick={() => setActiveTab('invite')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'invite'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            Issue Invitation
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tab 1: Access Requests */}
      {activeTab === 'requests' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Pending Employee Access Requests</h3>
                <p className="text-xs text-slate-400">
                  Requests submitted by authenticated employees requiring explicit Controller or Admin approval.
                </p>
              </div>
              <button
                onClick={loadAccessRequests}
                disabled={loading}
                className="text-xs text-slate-400 hover:text-white bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg transition-colors"
              >
                Refresh
              </button>
            </div>

            {loading ? (
              <div className="p-12 text-center text-slate-500 text-xs flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                Loading access requests...
              </div>
            ) : requests.length === 0 ? (
              <div className="p-12 text-center text-slate-500 text-xs">
                No access requests on record for organisation '{currentUser.org_id}'.
              </div>
            ) : (
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono text-[11px]">
                  <tr>
                    <th className="py-2.5 px-4">Applicant</th>
                    <th className="py-2.5 px-4">Requested Role</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Justification</th>
                    <th className="py-2.5 px-4">Requested Date</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-sans">
                  {requests.map((req) => (
                    <tr key={req.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{req.full_name || req.email}</div>
                        <div className="text-[11px] text-slate-400 font-mono">{req.email}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                          {req.requested_role}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center gap-1 font-mono text-[11px] px-2 py-0.5 rounded ${
                          req.status === 'PENDING'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : req.status === 'APPROVED'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}>
                          {req.status === 'PENDING' && <Clock className="w-3 h-3" />}
                          {req.status === 'APPROVED' && <CheckCircle className="w-3 h-3" />}
                          {req.status === 'REJECTED' && <XCircle className="w-3 h-3" />}
                          {req.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {req.review_reason || 'No justification provided.'}
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                        {new Date(req.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {req.status === 'PENDING' && (isSystemAdmin || isController) ? (
                          <div className="flex justify-end gap-1.5">
                            <button
                              onClick={() => {
                                setReviewingId(req.id);
                                setReviewAction('APPROVE');
                                setReviewRole((req.requested_role as UserRole) || 'AP_ASSOCIATE');
                              }}
                              className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-600/30 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => {
                                setReviewingId(req.id);
                                setReviewAction('REJECT');
                              }}
                              className="bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-600/30 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-slate-600 text-[11px]">Reviewed</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Issue Invitation */}
      {activeTab === 'invite' && (
        <div className="max-w-xl bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-white">Issue Single-Use Tenant Invitation</h3>
            <p className="text-xs text-slate-400 mt-1">
              Generates a secure, 32-byte cryptographic token valid for 7 days. The invitee must sign in using this exact email address to claim membership.
            </p>
          </div>

          <form onSubmit={handleCreateInvitation} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Corporate Email Address</label>
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.internal"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Assigned Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as UserRole)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="AP_ASSOCIATE">AP Associate (Verification, Matching, Ingestion)</option>
                <option value="AP_LEAD">AP Lead (Routing, Threshold Approvals)</option>
                <option value="CONTROLLER">Controller (Financial Approvals, Dual Control)</option>
                <option value="CATEGORY_MANAGER">Category Manager (Commercial Reviews)</option>
                <option value="AUDITOR">Auditor (Strictly Read-Only Inspection)</option>
                {isSystemAdmin && (
                  <option value="SYSTEM_ADMIN">System Administrator (Full Org Access)</option>
                )}
              </select>
              {!isSystemAdmin && (
                <p className="text-[11px] text-slate-500 mt-1">
                  * Privilege escalation barred: Only System Administrators can issue invitations for the SYSTEM_ADMIN role.
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={inviting || !inviteEmail.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {inviting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
              Generate Single-Use Invitation Token
            </button>
          </form>

          {/* Generated Token Display */}
          {generatedInvite && (
            <div className="mt-6 p-4 bg-slate-950 border border-emerald-500/30 rounded-lg space-y-3">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                <CheckCircle className="w-4 h-4" />
                <span>Invitation Successfully Created</span>
              </div>
              <p className="text-xs text-slate-400">
                Share this token with <span className="font-mono text-slate-200">{generatedInvite.email}</span>. It can only be redeemed once and expires on {new Date(generatedInvite.expires_at).toLocaleDateString()}.
              </p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={generatedInvite.invitation_token}
                  className="flex-1 bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-xs text-emerald-300 font-mono select-all focus:outline-none"
                />
                <button
                  onClick={handleCopyToken}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3 py-1.5 rounded flex items-center gap-1.5 border border-slate-700 transition-colors"
                >
                  {copiedToken ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedToken ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Review Dialog Modal */}
      {reviewingId && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-semibold text-white">
              {reviewAction === 'APPROVE' ? 'Approve Access Request' : 'Reject Access Request'}
            </h3>
            <p className="text-xs text-slate-400">
              {reviewAction === 'APPROVE'
                ? 'Approving this request will immediately provision the employee with active organisation membership.'
                : 'Rejecting this request will mark the application as denied. Please provide a clear audit reason.'}
            </p>

            <form onSubmit={handleReviewSubmit} className="space-y-4">
              {reviewAction === 'APPROVE' && (
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Granted Role</label>
                  <select
                    value={reviewRole}
                    onChange={(e) => setReviewRole(e.target.value as UserRole)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="AP_ASSOCIATE">AP Associate</option>
                    <option value="AP_LEAD">AP Lead</option>
                    <option value="CONTROLLER">Controller</option>
                    <option value="CATEGORY_MANAGER">Category Manager</option>
                    <option value="AUDITOR">Auditor</option>
                    {isSystemAdmin && <option value="SYSTEM_ADMIN">System Administrator</option>}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Review Notes / Reason</label>
                <textarea
                  value={reviewReason}
                  onChange={(e) => setReviewReason(e.target.value)}
                  placeholder="Record an audit reason for this access decision..."
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setReviewingId(null)}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReview}
                  className={`px-4 py-2 rounded-lg text-xs font-semibold text-white transition-colors flex items-center gap-1.5 ${
                    reviewAction === 'APPROVE'
                      ? 'bg-emerald-600 hover:bg-emerald-500'
                      : 'bg-rose-600 hover:bg-rose-500'
                  }`}
                >
                  {submittingReview && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Confirm {reviewAction === 'APPROVE' ? 'Approval' : 'Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};