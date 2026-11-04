import React, { useEffect, useState, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  RefreshCw, 
  Mail, 
  ChevronLeft, 
  ChevronRight, 
  UploadCloud,
  X
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { 
  PageHeader, 
  Card, 
  Button, 
  SearchInput, 
  FilterTabs, 
  Table, 
  TableHeader, 
  TableBody, 
  TableRow, 
  TableHead, 
  TableCell, 
  LoadingState, 
  EmptyState, 
  Modal 
} from '../components/ui';
import type { FilterTabItem } from '../components/ui';
import type { InboxResponse } from '../types';

interface InboxPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

type OperationalQueueTab = 'all' | 'needs_attention' | 'ready' | 'waiting' | 'approved';

export const InboxPage: React.FC<InboxPageProps> = ({ onSelectInvoice }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<InboxResponse | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Operational Queue Tab State
  const [activeQueueTab, setActiveQueueTab] = useState<OperationalQueueTab>(() => {
    const stage = searchParams.get('stage');
    const decision = searchParams.get('decision');
    if (stage === 'ACTION_REQUIRED') return 'needs_attention';
    if (decision === 'MATCH_CANDIDATE' || decision === 'AUTO_APPROVED') return 'ready';
    if (decision === 'HOLD_PENDING_EVIDENCE' || decision === 'QUARANTINED') return 'waiting';
    if (decision === 'MANUALLY_APPROVED' || decision === 'APPROVED') return 'approved';
    return 'all';
  });

  // Filters
  const [stageFilter, setStageFilter] = useState<string>(searchParams.get('stage') || '');
  const [decisionFilter, setDecisionFilter] = useState<string>(searchParams.get('decision') || '');
  const [fyFilter, setFyFilter] = useState<string>(() => searchParams.get('fy') || localStorage.getItem('ap.inbox.fy') || '');
  const [monthFilter, setMonthFilter] = useState<string>(() => searchParams.get('month') || localStorage.getItem('ap.inbox.month') || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);

  // Sync & Upload State
  const [syncingMailbox, setSyncingMailbox] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleQueueTabChange = (tabId: OperationalQueueTab) => {
    setActiveQueueTab(tabId);
    setPage(1);
    const next = new URLSearchParams();
    if (tabId === 'needs_attention') {
      next.set('stage', 'ACTION_REQUIRED');
      setStageFilter('ACTION_REQUIRED');
      setDecisionFilter('');
    } else if (tabId === 'ready') {
      next.set('decision', 'MATCH_CANDIDATE');
      setStageFilter('');
      setDecisionFilter('MATCH_CANDIDATE');
    } else if (tabId === 'waiting') {
      next.set('decision', 'HOLD_PENDING_EVIDENCE');
      setStageFilter('');
      setDecisionFilter('HOLD_PENDING_EVIDENCE');
    } else if (tabId === 'approved') {
      next.set('decision', 'MANUALLY_APPROVED');
      setStageFilter('');
      setDecisionFilter('MANUALLY_APPROVED');
    } else {
      setStageFilter('');
      setDecisionFilter('');
    }
    setSearchParams(next);
  };

  const handleUploadFile = async (file: File) => {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      setUploadError('File exceeds maximum upload size of 50 MB.');
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadFeedback(`Uploading ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.uploadDocument(formData);
      setUploadFeedback(`Uploaded ${file.name}. Invoice registered into processing queue.`);
      await loadInbox();
      setTimeout(() => {
        setUploadModalOpen(false);
        setUploadFeedback(null);
      }, 1200);
    } catch (err: any) {
      if (err.message && err.message.includes('409')) {
        setUploadError(`Duplicate detected: ${file.name} has already been registered.`);
      } else {
        setUploadError(err.message || 'Invoice upload failed.');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleSyncMailbox = async () => {
    setSyncingMailbox(true);
    setSyncFeedback(null);
    setSyncError(null);
    try {
      const res = await api.syncGmailMailbox(15);
      const mode = res.sync_mode === 'INCREMENTAL_HISTORY' ? 'History API' : 'Full Reconciliation';
      const msg = `${mode}: ${res.ingested_count} ingested, ${res.duplicates_skipped} duplicate(s) skipped.`;
      setSyncFeedback(msg);
      await loadInbox();
    } catch (err: any) {
      setSyncError(err.message || 'Mailbox sync failed.');
    } finally {
      setSyncingMailbox(false);
    }
  };

  const loadInbox = async () => {
    setLoading(true);
    try {
      const res = await api.getInbox({
        page,
        stage: stageFilter || undefined,
        decision: decisionFilter || undefined,
        fy: fyFilter || undefined,
        month: monthFilter ? parseInt(monthFilter, 10) : undefined,
      });
      setData(res);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleFyChange = (val: string) => {
    setPage(1);
    setFyFilter(val);
    if (val) {
      localStorage.setItem('ap.inbox.fy', val);
    } else {
      localStorage.removeItem('ap.inbox.fy');
    }
  };

  const handleMonthChange = (val: string) => {
    setPage(1);
    setMonthFilter(val);
    if (val) {
      localStorage.setItem('ap.inbox.month', val);
    } else {
      localStorage.removeItem('ap.inbox.month');
    }
  };

  useEffect(() => {
    loadInbox();
  }, [page, stageFilter, decisionFilter, fyFilter, monthFilter]);

  // Polling if any invoice is processing
  useEffect(() => {
    const hasActiveProcessing = data?.items?.some(
      (inv) => inv.stage === 'RECEIVED' || inv.job_status === 'PROCESSING' || inv.job_status === 'QUEUED'
    );
    if (!hasActiveProcessing) return;

    const timer = setInterval(() => {
      api.getInbox({
        page,
        stage: stageFilter || undefined,
        decision: decisionFilter || undefined,
        fy: fyFilter || undefined,
        month: monthFilter ? parseInt(monthFilter, 10) : undefined,
      }).then(setData).catch(() => {});
    }, 3000);

    return () => clearInterval(timer);
  }, [data?.items, page, stageFilter, decisionFilter, fyFilter, monthFilter]);

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!searchQuery.trim()) return data.items;
    const q = searchQuery.toLowerCase().trim();
    return data.items.filter((inv) =>
      (inv.vendor_name || '').toLowerCase().includes(q) ||
      (inv.invoice_number || '').toLowerCase().includes(q) ||
      (inv.po_reference || '').toLowerCase().includes(q) ||
      (inv.vendor_gstin || '').toLowerCase().includes(q) ||
      inv.id.toLowerCase().includes(q)
    );
  }, [data?.items, searchQuery]);

  const formatINR = (val?: number | null) => {
    if (val === undefined || val === null) return '—';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const queueTabs: FilterTabItem<OperationalQueueTab>[] = [
    { id: 'all', label: 'All Invoices' },
    { id: 'needs_attention', label: 'Needs Attention', badgeTone: 'warning' },
    { id: 'ready', label: 'Ready for Approval', badgeTone: 'success' },
    { id: 'waiting', label: 'Waiting on Evidence', badgeTone: 'info' },
    { id: 'approved', label: 'Approved & Cleared', badgeTone: 'neutral' },
  ];

  return (
    <div className="space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        title="Invoices Inbox"
        description="Ingested vendor bills, OCR extraction status, and 3-way/4-way matching queues."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSyncMailbox}
              isLoading={syncingMailbox}
              leftIcon={<Mail className="w-3.5 h-3.5" />}
              title="Sync Gmail inbox for incoming invoice attachments"
            >
              Sync Gmail
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setUploadModalOpen(true)}
              leftIcon={<UploadCloud className="w-3.5 h-3.5" />}
            >
              Upload Invoice
            </Button>
          </div>
        }
      />

      {/* Sync / Upload Toasts */}
      {syncFeedback && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <span>{syncFeedback}</span>
          <button onClick={() => setSyncFeedback(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
      {syncError && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <span>{syncError}</span>
          <button onClick={() => setSyncError(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Operational Filter Tabs (Flick AI Style) */}
      <div data-tour="inbox-queue-tabs" className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pt-1">
        <FilterTabs
          tabs={queueTabs}
          activeTab={activeQueueTab}
          onChange={handleQueueTabChange}
        />

        {/* Temporal Period Scoping & Search */}
        <div className="flex items-center gap-2 flex-wrap shrink-0">
          {/* Fiscal Year Filter */}
          <select
            value={fyFilter}
            onChange={(e) => handleFyChange(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-hidden cursor-pointer"
            aria-label="Fiscal Year Filter"
          >
            <option value="">All Financial Years</option>
            <option value="FY2024-25">FY 2024-25</option>
            <option value="FY2023-24">FY 2023-24</option>
          </select>

          {/* Month Filter */}
          <select
            value={monthFilter}
            onChange={(e) => handleMonthChange(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-hidden cursor-pointer"
            aria-label="Month Filter"
          >
            <option value="">All Months</option>
            <option value="1">January</option>
            <option value="2">February</option>
            <option value="3">March</option>
            <option value="4">April</option>
            <option value="5">May</option>
            <option value="6">June</option>
            <option value="7">July</option>
            <option value="8">August</option>
            <option value="9">September</option>
            <option value="10">October</option>
            <option value="11">November</option>
            <option value="12">December</option>
          </select>

          {/* Search Box */}
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search invoice, vendor, PO..."
            className="w-48 sm:w-56"
          />

          <Button
            variant="ghost"
            size="sm"
            onClick={loadInbox}
            disabled={loading}
            title="Refresh table"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* 3. Master Invoices Table */}
      <Card className="overflow-hidden">
        {loading && !data ? (
          <LoadingState label="Loading invoices..." className="py-16" />
        ) : filteredItems.length === 0 ? (
          <EmptyState
            title="No invoices found in this view"
            description={searchQuery ? `No invoices matched "${searchQuery}". Try clearing search.` : "No bills matching the selected queue and period."}
            action={
              searchQuery ? (
                <Button variant="secondary" size="sm" onClick={() => setSearchQuery('')}>
                  Clear Search
                </Button>
              ) : (
                <Button variant="primary" size="sm" onClick={() => setUploadModalOpen(true)}>
                  Upload an Invoice
                </Button>
              )
            }
            className="py-14 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Invoice & Date</TableHead>
                  <TableHead>Supplier / Vendor</TableHead>
                  <TableHead>Linked PO</TableHead>
                  <TableHead className="text-right">Billed Amount</TableHead>
                  <TableHead>Verification Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((inv, index) => (
                  <TableRow
                    key={inv.id}
                    onClick={() => onSelectInvoice(inv.id)}
                    className="group"
                  >
                    <TableCell className="text-slate-400 font-mono text-[11px]">
                      {(page - 1) * 10 + index + 1}
                    </TableCell>
                    <TableCell>
                      <div className="font-mono font-semibold text-slate-900 dark:text-white">
                        {inv.invoice_number || inv.id}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : 'Date Pending Extraction'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="font-semibold text-slate-800 dark:text-slate-200">
                        {inv.vendor_name || 'Unregistered Vendor'}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {inv.vendor_gstin || 'GSTIN Not Found'}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-slate-600 dark:text-slate-300">
                      {inv.po_reference || <span className="text-slate-400">None</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                      {formatINR(inv.total_amount)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        invoice={inv}
                        size="sm"
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectInvoice(inv.id);
                        }}
                        rightIcon={<ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />}
                      >
                        Review
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* 4. Table Pagination Footer */}
        {data && (data.total_pages || 1) > 1 && (
          <div className="p-3 sm:px-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between text-xs text-slate-500">
            <div>
              Showing page <span className="font-semibold text-slate-900 dark:text-white">{data.page}</span> of{' '}
              <span className="font-semibold text-slate-900 dark:text-white">{data.total_pages}</span> ({data.total_count} total invoices)
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="xs"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
                leftIcon={<ChevronLeft className="w-3 h-3" />}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="xs"
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages || loading}
                rightIcon={<ChevronRight className="w-3 h-3" />}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Upload Invoice Modal */}
      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Upload Vendor Invoice"
        description="Accepts PDF, TIFF, PNG, or JPEG scans up to 50 MB for autonomous extraction."
        maxWidth="md"
      >
        <div className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleUploadFile(e.dataTransfer.files[0]);
              }
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              isDragOver
                ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20'
                : 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600 bg-slate-50/50 dark:bg-slate-850/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tiff"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleUploadFile(e.target.files[0]);
                }
              }}
              className="hidden"
            />
            {uploading ? (
              <LoadingState label="Uploading & registering invoice..." className="py-6" />
            ) : (
              <>
                <UploadCloud className="w-10 h-10 text-indigo-600 dark:text-indigo-400 mx-auto mb-2.5" />
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 block">
                  Click to select or drag and drop invoice PDF
                </span>
                <span className="text-xs text-slate-400 mt-1 block">
                  Supports standard tax invoices, credit notes, and delivery challans
                </span>
              </>
            )}
          </div>

          {uploadFeedback && (
            <div className="p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-xs text-indigo-800 dark:text-indigo-300">
              {uploadFeedback}
            </div>
          )}

          {uploadError && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
              {uploadError}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
