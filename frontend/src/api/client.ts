import type { 
  HealthResponse, DashboardMetrics, InboxResponse, 
  ExceptionsResponse, SourceRecordsData, AuditResponse, AuthenticatedUser,
  UserInvitation, AccessRequest, DocumentMetadata
} from '../types';

const AUTH_STORAGE_KEY = 'ap_command_center_auth_token';

export function getAuthToken(): string | null {
  return localStorage.getItem(AUTH_STORAGE_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(AUTH_STORAGE_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const token = getAuthToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new Error('Authentication required. Missing or expired enterprise session token.');
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export const api = {
  getHealth: () => request<HealthResponse>('/api/v1/health'),
  getAuthStatus: () => request<any>('/api/v1/auth/status'),
  getCurrentUser: () => request<AuthenticatedUser>('/api/v1/auth/me'),
  getDevSession: (email: string, org_id?: string, unprovisioned?: boolean) => request<{ access_token: string; token_type: string; user: any }>('/api/v1/auth/dev-session', {
    method: 'POST',
    body: JSON.stringify({ email, org_id, unprovisioned }),
  }),
  logout: () => request<{ status: string; message: string }>('/api/v1/auth/logout', { method: 'POST' }),
  createInvitation: (email: string, role: string) => request<UserInvitation>('/api/v1/auth/invitations', {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  }),
  acceptInvitation: (token: string) => request<{ status: string; org_id: string; role: string; message: string }>('/api/v1/auth/invitations/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  }),
  submitAccessRequest: (org_id: string, reason?: string, requested_role?: string) => request<{ request_id: string; org_id: string; status: string; message: string }>('/api/v1/auth/access-requests', {
    method: 'POST',
    body: JSON.stringify({ org_id, reason, requested_role }),
  }),
  getMyAccessRequests: () => request<AccessRequest[]>('/api/v1/auth/access-requests/my'),
  getOrganisationAccessRequests: () => request<AccessRequest[]>('/api/v1/auth/access-requests'),
  reviewAccessRequest: (requestId: string, action: 'APPROVE' | 'REJECT', role?: string, reason?: string) => request<any>(`/api/v1/auth/access-requests/${requestId}/review`, {
    method: 'POST',
    body: JSON.stringify({ action, role, reason }),
  }),
  updateUserRole: (userId: string, role: string, reason: string) => request<any>(`/api/v1/auth/users/${userId}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role, reason }),
  }),
  deactivateUser: (userId: string, reason: string) => request<any>(`/api/v1/auth/users/${userId}/deactivate`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  }),
  getDashboardMetrics: () => request<DashboardMetrics>('/api/v1/dashboard/metrics'),
  getConnections: () => request<any>('/api/v1/connections'),
  uploadInvoice: (formData: FormData) => request<any>('/api/v1/connections/upload', {
    method: 'POST',
    body: formData,
  }),
  getInbox: (params: { page?: number; stage?: string; decision?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', params.page.toString());
    if (params.stage) q.set('stage', params.stage);
    if (params.decision) q.set('decision', params.decision);
    return request<InboxResponse>(`/api/v1/inbox?${q.toString()}`);
  },
  getInvoiceDetail: (id: string) => request<any>(`/api/v1/invoices/${id}`),
  executeAction: (id: string, action: string, reason: string, extra?: { undisputed_amount?: number; evidence_reference?: string }) => request<any>(`/api/v1/invoices/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action, reason, ...extra }),
  }),
  getExceptions: () => request<ExceptionsResponse>('/api/v1/exceptions'),
  getSourceRecords: () => request<SourceRecordsData>('/api/v1/source-records'),
  getAudit: (params: { invoice_id?: string; actor_id?: string; action?: string; correlation_id?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.invoice_id) q.set('invoice_id', params.invoice_id);
    if (params.actor_id) q.set('actor_id', params.actor_id);
    if (params.action) q.set('action', params.action);
    if (params.correlation_id) q.set('correlation_id', params.correlation_id);
    if (params.limit) q.set('limit', String(params.limit));
    return request<AuditResponse>(`/api/v1/audit?${q.toString()}`);
  },
  getDocuments: (includeDeleted: boolean = false) => request<DocumentMetadata[]>(`/api/v1/documents?include_deleted=${includeDeleted}`),
  uploadDocument: (formData: FormData) => request<any>('/api/v1/documents/upload', {
    method: 'POST',
    body: formData,
  }),
  getDocumentMetadata: (id: string) => request<DocumentMetadata>(`/api/v1/documents/${id}`),
  getDocumentSignedUrl: (id: string, expiresIn: number = 300) => request<{ document_id: string; storage_key: string; signed_url: string; expires_in: number }>(`/api/v1/documents/${id}/signed-url?expires_in=${expiresIn}`),
  softDeleteDocument: (id: string, reason?: string) => {
    const q = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return request<any>(`/api/v1/documents/${id}${q}`, { method: 'DELETE' });
  },
  purgeDocument: (id: string, reason?: string) => {
    const q = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    return request<any>(`/api/v1/documents/${id}/purge${q}`, { method: 'POST' });
  },
  getApprovals: (params: { status?: string; mine?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (params.status) q.set('status', params.status);
    if (params.mine !== undefined) q.set('mine', params.mine.toString());
    return request<{ total_count: number; threshold_inr: number; items: any[] }>(`/api/v1/approvals?${q.toString()}`);
  },
  getMembers: () => request<{ total_count: number; items: any[] }>('/api/v1/auth/members'),
  getGmailStatus: () => request<any>('/api/v1/integrations/gmail/status'),
  getGmailAuthorizeUrl: () => request<{ authorization_url: string; scope: string }>('/api/v1/integrations/gmail/authorize'),
  syncGmailMailbox: (maxMessages: number = 10, forceFull: boolean = false) => request<any>(`/api/v1/integrations/gmail/sync?max_messages=${maxMessages}&force_full=${forceFull}`, {
    method: 'POST',
  }),
  disconnectGmailMailbox: () => request<any>('/api/v1/integrations/gmail/disconnect', {
    method: 'POST',
  }),
};
