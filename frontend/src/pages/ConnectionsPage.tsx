import React, { useEffect, useState } from 'react';
import { 
  Link2, 
  Upload, 
  ShieldCheck, 
  Mail, 
  Database, 
  HardDrive, 
  AlertOctagon, 
  CheckCircle2, 
  XCircle, 
  RefreshCw, 
  FileText,
  ExternalLink,
  Download,
  Trash2,
  AlertTriangle,
  FileCheck
} from 'lucide-react';
import { api, getAuthToken } from '../api/client';
import type { DocumentMetadata, UploadLifecycleStatus } from '../types';

export const ConnectionsPage: React.FC = () => {
  const [connections, setConnections] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploadLifecycle, setUploadLifecycle] = useState<UploadLifecycleStatus>('Idle');
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [syncingGmail, setSyncingGmail] = useState(false);
  const [gmailSyncResult, setGmailSyncResult] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const connData = await api.getConnections();
      setConnections(connData);
    } catch (err: any) {
      setError(err.message || 'Failed to query connection states.');
    } finally {
      setLoading(false);
    }

    await loadDocuments();
  };

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch {
      // If unauthenticated or no docs
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset state
    setUploadResult(null);
    setUploadError(null);

    // 1. Client-Side Validation
    setUploadLifecycle('Validating');
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadLifecycle('Failed');
      setUploadError('Unsupported format: Only authentic PDF documents are accepted.');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadLifecycle('Failed');
      setUploadError(`File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 50 MB Supabase Free limit.`);
      return;
    }

    // 2. Uploading
    setUploadLifecycle('Uploading');
    try {
      const formData = new FormData();
      formData.append('file', file);

      // 3. Processing
      setUploadLifecycle('Processing');
      const token = getAuthToken();
      const response = await fetch('/api/v1/documents/upload', {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (response.status === 409 || data.status === 'DUPLICATE_DETECTED') {
        setUploadLifecycle('Duplicate detected');
        setUploadError(data.detail || 'A document with identical SHA-256 hash already exists in this organisation.');
        setUploadResult(data);
        return;
      }

      if (response.status === 403) {
        setUploadLifecycle('Access denied');
        setUploadError(data.detail || 'Access denied: Active tenant membership required.');
        return;
      }

      if (!response.ok) {
        setUploadLifecycle('Failed');
        setUploadError(data.detail || `Upload failed with HTTP ${response.status}`);
        return;
      }

      // 4. Ready
      setUploadLifecycle('Ready');
      setUploadResult(data);
      await loadData();
    } catch (err: any) {
      setUploadLifecycle('Failed');
      setUploadError(err.message || 'Network failure during document upload.');
    } finally {
      // Clear input so same file can be selected again if needed
      e.target.value = '';
    }
  };

  const handleOpenSignedUrl = async (docId: string) => {
    try {
      const res = await api.getDocumentSignedUrl(docId, 300);
      window.open(res.signed_url, '_blank', 'noopener,noreferrer');
    } catch (err: any) {
      alert(`Presigned URL generation failed: ${err.message}`);
    }
  };

  const handleDownload = (docId: string) => {
    const token = getAuthToken();
    const downloadUrl = `/api/v1/documents/${docId}/download`;
    // Trigger download with auth header
    fetch(downloadUrl, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    })
      .then(res => {
        if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);
        const header = res.headers.get('Content-Disposition');
        const filenameMatch = header && header.match(/filename="?([^"]+)"?/);
        const filename = filenameMatch ? filenameMatch[1] : `document_${docId}.pdf`;
        return res.blob().then(blob => ({ blob, filename }));
      })
      .then(({ blob, filename }) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(err => alert(err.message));
  };

  const handleSoftDelete = async (docId: string, filename: string) => {
    if (!window.confirm(`Are you sure you want to soft delete '${filename}'? The physical file will be preserved in storage according to retention policy.`)) {
      return;
    }

    setDeletingId(docId);
    try {
      await api.softDeleteDocument(docId, 'Operator soft deletion from Ingestion Hub');
      await loadDocuments();
    } catch (err: any) {
      alert(`Soft delete failed: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleConnectGmail = async () => {
    try {
      const res = await api.getGmailAuthorizeUrl();
      if (res.authorization_url) {
        window.location.href = res.authorization_url;
      }
    } catch (err: any) {
      alert(`Gmail OAuth initiation failed: ${err.message}`);
    }
  };

  const handleSyncGmail = async () => {
    setSyncingGmail(true);
    setGmailSyncResult(null);
    try {
      const res = await api.syncGmailMailbox(15);
      setGmailSyncResult(`Sync complete: ${res.ingested_count} invoice(s) ingested, ${res.duplicates_skipped} duplicate(s) skipped, ${res.quarantined_count} quarantined.`);
      await loadData();
    } catch (err: any) {
      alert(`Gmail sync failed: ${err.message}`);
    } finally {
      setSyncingGmail(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!window.confirm("Disconnect authorized Gmail ingestion mailbox?")) return;
    try {
      await api.disconnectGmailMailbox();
      await loadData();
    } catch (err: any) {
      alert(`Disconnect failed: ${err.message}`);
    }
  };

  const getPillarBadge = (status: string) => {
    switch (status) {
      case 'CONNECTED':
        return <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20"><CheckCircle2 className="w-3 h-3" /> CONNECTED</span>;
      case 'NOT_CONFIGURED':
        return <span className="flex items-center gap-1 text-[11px] font-mono text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20"><AlertOctagon className="w-3 h-3" /> NOT CONFIGURED</span>;
      case 'BLOCKED':
        return <span className="flex items-center gap-1 text-[11px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20"><XCircle className="w-3 h-3" /> BLOCKED</span>;
      default:
        return <span className="text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">{status}</span>;
    }
  };

  const pillars = connections?.pillars || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Link2 className="w-5 h-5 text-indigo-400" />
            Integrations & Ingestion Hub
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Verified status of Identity, Gmail, SAP S/4HANA ERP, Supabase Storage & Tenant Documents.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading || loadingDocs}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading || loadingDocs ? 'animate-spin' : ''}`} />
          Run Health Checks
        </button>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-lg p-3 text-xs text-rose-300">
          Connection inspection error: {error}
        </div>
      )}

      {/* Manual Upload Card with Honest Lifecycle States */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
            <Upload className="w-4 h-4 text-indigo-400" />
            Tenant Invoice Ingestion (Direct Supabase Storage Intake)
          </h2>
          <span className="text-[11px] font-mono text-slate-400">
            Path: org_{'{org_id}'}/invoices/{'{doc_id}'}/{'{filename}'}
          </span>
        </div>
        <p className="text-xs text-slate-400 mb-4">
          Upload authentic vendor invoice PDFs. Ingested files are strictly validated (%PDF- header, &le; 50 MB limit), hashed with SHA-256, persisted to private Supabase Storage, and registered in the append-only audit log.
        </p>

        {/* Upload Status Banner */}
        {uploadLifecycle === 'Validating' && (
          <div className="mb-4 bg-sky-950/40 border border-sky-800/60 rounded-lg p-3 text-xs text-sky-300 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
            <span>Validating: Checking PDF signature header (%PDF-) and file size (&le; 50 MB)...</span>
          </div>
        )}

        {uploadLifecycle === 'Uploading' && (
          <div className="mb-4 bg-indigo-950/40 border border-indigo-800/60 rounded-lg p-3 text-xs text-indigo-300 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
            <span>Uploading: Streaming encrypted bytes to Supabase Storage...</span>
          </div>
        )}

        {uploadLifecycle === 'Processing' && (
          <div className="mb-4 bg-amber-950/40 border border-amber-800/60 rounded-lg p-3 text-xs text-amber-300 flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-amber-400" />
            <span>Processing: Writing tenant-scoped document metadata and queuing ingestion job...</span>
          </div>
        )}

        {uploadLifecycle === 'Ready' && uploadResult && (
          <div className="mb-4 bg-emerald-950/40 border border-emerald-800/60 rounded-lg p-3.5 text-xs text-emerald-300">
            <div className="flex items-center gap-2 font-medium mb-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Document Upload Succeeded & Verified</span>
            </div>
            <div className="font-mono text-[11px] text-emerald-400/90 space-y-0.5">
              <div><span className="text-slate-400">Filename:</span> {uploadResult.filename}</div>
              <div><span className="text-slate-400">Document ID:</span> {uploadResult.document_id}</div>
              <div><span className="text-slate-400">Invoice ID:</span> {uploadResult.invoice_id}</div>
              <div><span className="text-slate-400">SHA-256:</span> {uploadResult.sha256}</div>
              <div><span className="text-slate-400">Storage Key:</span> {uploadResult.storage_key}</div>
            </div>
          </div>
        )}

        {uploadLifecycle === 'Duplicate detected' && (
          <div className="mb-4 bg-amber-950/40 border border-amber-800/60 rounded-lg p-3.5 text-xs text-amber-300">
            <div className="flex items-center gap-2 font-medium mb-1">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Duplicate Detected</span>
            </div>
            <p className="text-amber-200/80 mb-1">{uploadError}</p>
            {uploadResult?.document_id && (
              <div className="font-mono text-[11px] text-amber-400/80">
                Existing Document ID: {uploadResult.document_id} | Invoice ID: {uploadResult.invoice_id}
              </div>
            )}
          </div>
        )}

        {uploadLifecycle === 'Access denied' && (
          <div className="mb-4 bg-rose-950/40 border border-rose-800/60 rounded-lg p-3 text-xs text-rose-300 flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <div>
              <span className="font-medium">Access Denied:</span> {uploadError}
            </div>
          </div>
        )}

        {uploadLifecycle === 'Failed' && (
          <div className="mb-4 bg-rose-950/40 border border-rose-800/60 rounded-lg p-3 text-xs text-rose-300 flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <div>
              <span className="font-medium">Upload Failed:</span> {uploadError}
            </div>
          </div>
        )}

        <div className="border border-dashed border-slate-700/80 rounded-lg p-6 text-center hover:border-indigo-500 transition-colors bg-slate-950/40">
          <FileText className="w-8 h-8 text-slate-500 mx-auto mb-2" />
          <div className="text-xs text-slate-300 mb-2">
            Select genuine vendor invoice PDF (Max 50 MB, Supabase Free plan compliant)
          </div>
          <label className="inline-flex items-center gap-2 px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white cursor-pointer shadow-sm transition-colors">
            <span>{['Validating', 'Uploading', 'Processing'].includes(uploadLifecycle) ? `${uploadLifecycle}...` : 'Browse & Ingest Invoice PDF'}</span>
            <input 
              type="file" 
              accept=".pdf" 
              className="hidden" 
              onChange={handleFileUpload} 
              disabled={['Validating', 'Uploading', 'Processing'].includes(uploadLifecycle)} 
            />
          </label>
        </div>
      </div>

      {/* Tenant Ingested Documents Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
          <h2 className="text-xs font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-emerald-400" />
            Tenant Ingested Documents ({documents.length})
          </h2>
          <span className="text-[11px] font-mono text-slate-500">Private Bucket: invoices | TTL &le; 300s</span>
        </div>

        {loadingDocs ? (
          <div className="py-8 text-center text-xs text-slate-500">
            <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-indigo-400" />
            Loading tenant document catalog...
          </div>
        ) : documents.length === 0 ? (
          <div className="text-xs text-slate-500 py-6 text-center">
            No documents ingested for this organisation yet. Upload a vendor invoice above to begin.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">Filename</th>
                  <th className="py-2.5 px-3">Size</th>
                  <th className="py-2.5 px-3">SHA-256</th>
                  <th className="py-2.5 px-3">Storage Path</th>
                  <th className="py-2.5 px-3">Uploaded</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 text-slate-200 font-sans font-medium flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      <span className="truncate max-w-[200px]" title={doc.filename}>{doc.filename}</span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {(doc.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-2.5 px-3 text-slate-400" title={doc.sha256_hash}>
                      {doc.sha256_hash.substring(0, 12)}...
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 truncate max-w-[240px]" title={doc.storage_key}>
                      {doc.storage_key}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      {doc.uploaded_at.replace('T', ' ').substring(0, 19)}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2 font-sans">
                        <button
                          onClick={() => handleOpenSignedUrl(doc.id)}
                          title="Generate Presigned URL (TTL 300s) & Open"
                          className="p-1 rounded text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950/60 transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDownload(doc.id)}
                          title="Download Document (Verified SHA-256)"
                          className="p-1 rounded text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/60 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleSoftDelete(doc.id, doc.filename)}
                          disabled={deletingId === doc.id}
                          title="Soft Delete Document (Storage Preserved)"
                          className="p-1 rounded text-rose-400 hover:text-rose-300 hover:bg-rose-950/60 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4 Integration Pillars Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Identity Provider */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
                Enterprise SSO / OIDC Identity
              </div>
              {getPillarBadge(pillars.identity?.status || 'NOT_CONFIGURED')}
            </div>
            <p className="text-xs text-slate-400 mb-3">
              {pillars.identity?.message || 'Supabase Auth OIDC Provider (Google Workspace / Enterprise SAML)'}
            </p>
            <div className="space-y-1.5 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-3 rounded border border-slate-800/80">
              <div><span className="text-slate-500">Provider:</span> {pillars.identity?.provider || 'supabase_auth'}</div>
              <div><span className="text-slate-500">Issuer:</span> {pillars.identity?.issuer || 'https://<project>.supabase.co/auth/v1'}</div>
              <div><span className="text-slate-500">Redirect URI:</span> {pillars.identity?.redirect_uri}</div>
            </div>
          </div>
        </div>

        {/* 2. Gmail Ingestion */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Mail className="w-4 h-4 text-indigo-400" />
                Gmail Ingestion (Direct OAuth 2.0 & History API Sync)
              </div>
              {getPillarBadge(pillars.gmail_ingestion?.status || 'NOT_CONFIGURED')}
            </div>
            <p className="text-xs text-slate-400 mb-3">
              {pillars.gmail_ingestion?.message || 'Server-side OAuth 2.0 with minimum gmail.readonly scope & incremental History API sync.'}
            </p>
            <div className="space-y-1.5 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-3 rounded border border-slate-800/80 mb-3">
              <div><span className="text-slate-500">Mailbox:</span> {pillars.gmail_ingestion?.mailbox || 'Not configured'}</div>
              <div><span className="text-slate-500">Scope:</span> https://www.googleapis.com/auth/gmail.readonly</div>
              <div><span className="text-slate-500">Tokens:</span> Fernet Encrypted (AES-128-CBC + HMAC-SHA256)</div>
              <div><span className="text-slate-500">Sync Engine:</span> On-Demand / Incremental History API (users.history.list)</div>
              <div><span className="text-slate-500">Last Synced:</span> {pillars.gmail_ingestion?.last_synced_at ? pillars.gmail_ingestion.last_synced_at.replace('T', ' ').substring(0, 19) : 'Pending initial sync'}</div>
              <div><span className="text-slate-500">History Watermark:</span> {pillars.gmail_ingestion?.last_history_id || 'None (initial reconciliation pending)'}</div>
            </div>

            {pillars.gmail_ingestion?.initial_sync_pending && (
              <div className="mb-3 bg-amber-950/40 border border-amber-800/60 rounded p-2 text-[11px] text-amber-300">
                Initial full synchronization pending. Click 'Sync Mailbox Now' to import pre-existing vendor invoice emails.
              </div>
            )}

            {gmailSyncResult && (
              <div className="mb-3 bg-emerald-950/40 border border-emerald-800/60 rounded p-2 text-[11px] text-emerald-300">
                {gmailSyncResult}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
            {pillars.gmail_ingestion?.status === 'CONNECTED' ? (
              <>
                <button
                  onClick={handleSyncGmail}
                  disabled={syncingGmail}
                  className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white transition-colors flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3 h-3 ${syncingGmail ? 'animate-spin' : ''}`} />
                  <span>{syncingGmail ? 'Syncing...' : 'Sync Mailbox Now'}</span>
                </button>
                <button
                  onClick={handleDisconnectGmail}
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-rose-300 transition-colors"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={handleConnectGmail}
                className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white transition-colors flex items-center gap-1.5"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>Connect Dedicated Mailbox</span>
              </button>
            )}
          </div>
        </div>

        {/* 3. SAP ERP Read-Only */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Database className="w-4 h-4 text-indigo-400" />
                SAP S/4HANA ERP (Read-Only)
              </div>
              {getPillarBadge(pillars.sap_erp?.status || 'NOT_CONFIGURED')}
            </div>
            <p className="text-xs text-slate-400 mb-3">
              {pillars.sap_erp?.message || 'Read-only adapter for POs, GRNs, Rate Contracts and QC records.'}
            </p>
            <div className="space-y-1.5 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-3 rounded border border-slate-800/80">
              <div><span className="text-slate-500">System:</span> {pillars.sap_erp?.system || 'SAP S/4HANA'}</div>
              <div><span className="text-slate-500">Company Code:</span> {pillars.sap_erp?.company_code || 'Not provisioned'}</div>
              <div><span className="text-slate-500">Required:</span> SAP_API_BASE_URL, SAP_CLIENT_ID, SAP_COMPANY_CODE</div>
            </div>
          </div>
        </div>

        {/* 4. Encrypted Object Storage */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <HardDrive className="w-4 h-4 text-indigo-400" />
                Supabase Storage (Private Bucket)
              </div>
              {getPillarBadge(pillars.object_storage?.status || 'NOT_CONFIGURED')}
            </div>
            <p className="text-xs text-slate-400 mb-3">
              {pillars.object_storage?.message || 'Private encrypted Supabase Storage bucket for authentic invoice originals.'}
            </p>
            <div className="space-y-1.5 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-3 rounded border border-slate-800/80">
              <div><span className="text-slate-500">Provider:</span> {pillars.object_storage?.provider || 'supabase'}</div>
              <div><span className="text-slate-500">Bucket:</span> {pillars.object_storage?.bucket || 'invoices'}</div>
              <div><span className="text-slate-500">Max File Size:</span> 50 MB</div>
            </div>
          </div>
        </div>
      </div>

      {/* Quarantined Documents Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
          <h2 className="text-xs font-semibold text-slate-200 tracking-wide uppercase flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-purple-400" />
            Quarantined Documents ({connections?.quarantined_count || 0})
          </h2>
          <span className="text-[11px] text-slate-500">Unreadable, Corrupt or Security-Failed Files</span>
        </div>

        {(!connections?.quarantined_documents || connections.quarantined_documents.length === 0) ? (
          <div className="text-xs text-slate-500 py-6 text-center">
            Zero quarantined documents. No ingestion or parsing failures recorded.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-2 px-3">Filename</th>
                  <th className="py-2 px-3">SHA-256</th>
                  <th className="py-2 px-3">Quarantine Reason</th>
                  <th className="py-2 px-3">Quarantined At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {connections.quarantined_documents.map((q: any) => (
                  <tr key={q.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 text-slate-200">{q.filename}</td>
                    <td className="py-2.5 px-3 text-slate-400">{q.sha256?.substring(0, 16)}...</td>
                    <td className="py-2.5 px-3 text-purple-400">{q.quarantine_reason}</td>
                    <td className="py-2.5 px-3 text-slate-500">{q.quarantined_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
