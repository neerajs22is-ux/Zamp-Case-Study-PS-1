import React, { useState, useEffect, useMemo } from 'react';
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
  UserCheck,
  Shield,
  ShieldCheck,
  Search,
  X,
  FileCheck2,
  Lock
} from 'lucide-react';
import { api } from '../api/client';
import type { AuthenticatedUser, AccessRequest, UserInvitation, UserRole } from '../types';

interface AccessManagementPageProps {
  currentUser: AuthenticatedUser;
}

const ROLE_DETAILS: Record<string, { label: string; description: string; color: string; tier: string }> = {
  AP_ASSOCIATE: {
    label: 'AP Associate',
    description: 'Upload documents, triage line-item discrepancies, and initiate invoice matching review.',
    color: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800/40',
    tier: 'Operational'
  },
  AP_LEAD: {
    label: 'AP Lead',
    description: 'Triage exceptions, connect email, issue colleague invitations, and approve invoices under ₹5,00,000.',
    color: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800/40',
    tier: 'Supervisory'
  },
  CONTROLLER: {
    label: 'Financial Controller',
    description: 'Dual-control sign-off on invoices ≥ ₹5,00,000, review tenant access requests, and export audited ledgers.',
    color: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40',
    tier: 'Executive / Dual-Control'
  },
  AUDITOR: {
    label: 'Auditor (Read-Only)',
    description: 'Strict read-only inspection of invoices, policy verifications, master records, and immutable audit logs.',
    color: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800/40',
    tier: 'Compliance'
  },
  SYSTEM_ADMIN: {
    label: 'System Administrator',
    description: 'Full tenant administration, integration credentials, role assignments, and security policy governance.',
    color: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800/40',
    tier: 'Infrastructure'
  }
};

export const AccessManagementPage: React.FC<AccessManagementPageProps> = ({ currentUser }) => {
  const [activeTab, setActiveTab] = useState<'members' | 'requests' | 'invite'>('members');
  const [showRbacMatrix, setShowRbacMatrix] = useState(false);
  const [memberSearch, setMemberSearch] = useState('');
  
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

  const filteredMembers = useMemo(() => {
    if (!memberSearch.trim()) return members;
    const q = memberSearch.toLowerCase().trim();
    return members.filter(m => 
      (m.full_name || '').toLowerCase().includes(q) ||
      (m.email || '').toLowerCase().includes(q) ||
      (m.role || '').toLowerCase().includes(q)
    );
  }, [members, memberSearch]);

  // Executive Metric Counts
  const controllerCount = useMemo(() => {
    return members.filter(m => m.role === 'CONTROLLER').length;
  }, [members]);

  const leadCount = useMemo(() => {
    return members.filter(m => m.role === 'AP_LEAD').length;
  }, [members]);

  const pendingRequestsCount = useMemo(() => {
    return requests.filter(r => r.status === 'PENDING').length;
  }, [requests]);

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
      setError(err?.message || 'Failed to generate invitation.');
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
      setError(err?.message || 'Failed to review access request.');
    } finally {
      setSubmittingReview(false);
    }
  };

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <Users className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Team Access & Role Governance
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Manage organization team members, assign dual-approval permissions, and review workspace access requests.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRbacMatrix(!showRbacMatrix)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800/40 text-xs font-semibold text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 transition-colors shadow-2xs"
          >
            <Shield className="w-3.5 h-3.5" />
            {showRbacMatrix ? 'Hide Role Matrix' : 'View RBAC Matrix'}
          </button>

          <button
            onClick={() => {
              loadMembers();
              loadAccessRequests();
            }}
            disabled={loadingMembers || loadingRequests}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingMembers || loadingRequests ? 'animate-spin' : ''}`} />
            Refresh Roster
          </button>
        </div>
      </div>

      {/* Role Governance & Security Metrics Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Total Active Members</span>
            <Users className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-slate-900 dark:text-white font-mono tabular-nums">
            {members.length}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Provisioned team roster</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Dual-Approval Authority</span>
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono tabular-nums">
            {controllerCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Controllers (≥ ₹5,00,000)</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Supervisory AP Leads</span>
            <FileCheck2 className="w-4 h-4 text-sky-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-sky-600 dark:text-sky-400 font-mono tabular-nums">
            {leadCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">1st approval & invitations</div>
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>Pending Access Requests</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-1 text-lg font-bold text-amber-600 dark:text-amber-400 font-mono tabular-nums">
            {pendingRequestsCount}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Awaiting Controller sign-off</div>
        </div>
      </div>

      {/* Expandable RBAC Permissions Matrix */}
      {showRbacMatrix && (
        <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3 animate-in fade-in duration-150">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-500" />
              <h3 className="font-bold text-xs text-slate-900 dark:text-white uppercase tracking-wider">
                Role-Based Access Control (RBAC) Entitlements Matrix
              </h3>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Strict Separation of Duties</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[620px]">
              <thead className="text-[10px] uppercase font-bold text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2 px-3">Capability / Operation</th>
                  <th className="py-2 px-3 text-center">AP Associate</th>
                  <th className="py-2 px-3 text-center">AP Lead</th>
                  <th className="py-2 px-3 text-center">Financial Controller</th>
                  <th className="py-2 px-3 text-center">Auditor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/60 dark:divide-slate-800 text-[11px]">
                <tr>
                  <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">Upload & Ingest Invoices</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-slate-400">Read-Only</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">Initial Approval (&lt; ₹5,00,000)</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-slate-400">Read-Only</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">Dual Approval (≥ ₹5,00,000)</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓ (Exclusive)</td>
                  <td className="py-2 px-3 text-center text-slate-400">Read-Only</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">Issue Team Invitations</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-slate-400">Read-Only</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-medium text-slate-800 dark:text-slate-200">Export Audited Ledger CSV</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-rose-500 font-bold">✗</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                  <td className="py-2 px-3 text-center text-emerald-600 font-bold">✓</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="p-3.5 rounded-xl border bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-950/30 dark:border-rose-800/40 dark:text-rose-200 text-xs flex items-start gap-2.5 shadow-2xs">
          <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">{error}</div>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      )}

      {/* Tabs and Member Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800/60 rounded-xl border border-slate-200/70 dark:border-slate-700/50 text-xs overflow-x-auto whitespace-nowrap max-w-full">
          <button
            onClick={() => setActiveTab('members')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'members'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5 text-indigo-500" />
            <span>Active Members</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-200/80 dark:bg-slate-800 font-mono">
              {members.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('requests')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'requests'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-indigo-500" />
            <span>Pending Requests</span>
            {pendingRequestsCount > 0 && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300 font-mono font-bold">
                {pendingRequestsCount}
              </span>
            )}
          </button>

          {canInvite && (
            <button
              onClick={() => setActiveTab('invite')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-medium transition-all ${
                activeTab === 'invite'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs border border-slate-200/60 dark:border-slate-700'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5 text-indigo-500" />
              <span>Issue Invitation</span>
            </button>
          )}
        </div>

        {activeTab === 'members' && (
          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={memberSearch}
              onChange={(e) => setMemberSearch(e.target.value)}
              placeholder="Search member name or email..."
              className="w-full pl-8 pr-7 py-1.5 text-xs rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 shadow-2xs transition-all"
            />
            {memberSearch && (
              <button
                onClick={() => setMemberSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Tab 1: Active Members Roster */}
      {activeTab === 'members' && (
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs overflow-hidden">
          {loadingMembers ? (
            <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
              <span>Loading organization member roster...</span>
            </div>
          ) : filteredMembers.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
              No active members match your search criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[720px]">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider sticky top-0 backdrop-blur-xs">
                  <tr>
                    <th className="py-2.5 px-4">Member</th>
                    <th className="py-2.5 px-4">Assigned Role & Responsibilities</th>
                    <th className="py-2.5 px-4">Governance Tier</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4 text-right">User ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {filteredMembers.map((m) => {
                    const roleInfo = ROLE_DETAILS[m.role] || {
                      label: m.role || 'Member',
                      description: 'Standard organization member.',
                      color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
                      tier: 'Standard'
                    };
                    const initials = (m.full_name || m.email || 'U')
                      .split(' ')
                      .map((n: string) => n[0])
                      .join('')
                      .toUpperCase()
                      .substring(0, 2);

                    return (
                      <tr key={m.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800/40 flex items-center justify-center font-bold font-mono text-xs">
                              {initials}
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                <span>{m.full_name || m.email.split('@')[0]}</span>
                                {m.id === currentUser.id && (
                                  <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-1.5 py-0.2 rounded border border-indigo-200 dark:border-indigo-800/40">
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

                        <td className="py-3 px-4 max-w-sm">
                          <div className="space-y-0.5">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${roleInfo.color}`}>
                              {roleInfo.label}
                            </span>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-normal">
                              {roleInfo.description}
                            </p>
                          </div>
                        </td>

                        <td className="py-3 px-4 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                          {roleInfo.tier}
                        </td>

                        <td className="py-3 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/40">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            {m.is_active ? 'ACTIVE' : 'DEACTIVATED'}
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
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs overflow-hidden">
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
              <table className="w-full text-left text-xs min-w-[700px]">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-2.5 px-4">Applicant</th>
                    <th className="py-2.5 px-4">Requested Role</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Submission Date</th>
                    <th className="py-2.5 px-4 text-right">Review Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {requests.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 dark:text-white">
                          {r.full_name || 'Applicant'}
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {r.email}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                          {r.requested_role}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${
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
                              className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-2xs transition-colors"
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
        <div className="bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-2xs max-w-2xl space-y-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-1">
              <UserPlus className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              Issue Organization Invitation
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Generates a signed, cryptographically secure 7-day invitation token. Storage uses SHA-256 token hashing to prevent credential exposure.
            </p>
          </div>

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
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 shadow-2xs font-mono"
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
                className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500 shadow-2xs"
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

            <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800/60 text-xs text-slate-600 dark:text-slate-400 space-y-1">
              <span className="font-semibold text-slate-800 dark:text-slate-200 block">Invitation Security Invariants:</span>
              <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                <li>Cryptographically secure 256-bit token generated via secrets engine.</li>
                <li>Hashed with SHA-256 before database insertion (raw token never stored).</li>
                <li>Strict 7-day expiration with single-use revocation on acceptance.</li>
              </ul>
            </div>

            <button
              type="submit"
              disabled={inviting || !inviteEmail.trim()}
              className="w-full py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-2xs transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              <Key className="w-3.5 h-3.5" />
              {inviting ? 'Generating Cryptographic Token...' : 'Generate Secure Invitation Link'}
            </button>
          </form>

          {/* Generated Invite Modal / Card */}
          {generatedInvite && (
            <div className="mt-4 p-4 rounded-xl border border-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/20 dark:border-emerald-800/40 space-y-3">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-semibold text-xs">
                <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Invitation Token Created Successfully</span>
              </div>
              
              <div className="space-y-1 text-xs">
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
                  className="flex-1 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-hidden"
                />
                <button
                  type="button"
                  onClick={handleCopyToken}
                  className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 inline-flex items-center gap-1.5 shadow-2xs"
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
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Review Organization Access Request
            </h3>
            
            <form onSubmit={handleReviewSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Determination
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setReviewAction('APPROVE')}
                    className={`py-2 rounded-xl font-semibold border text-center transition-colors ${
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
                    className={`py-2 rounded-xl font-semibold border text-center transition-colors ${
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
                    className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
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
                  className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setReviewingId(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReview}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-2xs transition-colors"
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
