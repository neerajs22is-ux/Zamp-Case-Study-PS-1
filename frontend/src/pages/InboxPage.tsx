import { ScreenPath } from "../components/ScreenPath";
import React, {
  useEffect,
  useState,
  useMemo,
  useRef,
  useCallback,
} from "react";
import { useSearchParams } from "react-router-dom";
import {
  RefreshCw,
  Mail,
  ChevronLeft,
  ChevronRight,
  UploadCloud,
  X,
} from "lucide-react";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import {
  PageHeader,
  Card,
  Button,
  SearchInput,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  LoadingState,
  ErrorState,
  EmptyState,
  Modal,
} from "../components/ui";
import type { FilterTabItem } from "../components/ui";
import type { InboxResponse } from "../types";
import { formatCurrency } from "../utils/currency";
import "./InboxPage.css";

interface InboxPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

type OperationalQueueTab =
  | "all"
  | "needs_attention"
  | "ready"
  | "waiting"
  | "approved";

export const InboxPage: React.FC<InboxPageProps> = ({ onSelectInvoice }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<InboxResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [inboxError, setInboxError] = useState(false);

  // Operational Queue Tab State
  const [activeQueueTab, setActiveQueueTab] = useState<OperationalQueueTab>(
    () => {
      const stage = searchParams.get("stage");
      const decision = searchParams.get("decision");
      if (stage === "ACTION_REQUIRED") return "needs_attention";
      if (decision === "MATCH_CANDIDATE" || decision === "AUTO_APPROVED")
        return "ready";
      if (decision === "HOLD_PENDING_EVIDENCE" || decision === "QUARANTINED")
        return "waiting";
      if (decision === "MANUALLY_APPROVED" || decision === "APPROVED")
        return "approved";
      return "all";
    },
  );

  // Filters
  const [stageFilter, setStageFilter] = useState<string>(
    searchParams.get("stage") || "",
  );
  const [decisionFilter, setDecisionFilter] = useState<string>(
    searchParams.get("decision") || "",
  );
  const [fyFilter, setFyFilter] = useState<string>(
    () => searchParams.get("fy") || localStorage.getItem("ap.inbox.fy") || "",
  );
  const [monthFilter, setMonthFilter] = useState<string>(
    () =>
      searchParams.get("month") || localStorage.getItem("ap.inbox.month") || "",
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const requestSequence = useRef(0);
  const polling = useRef(false);
  const [loadedQuery, setLoadedQuery] = useState<string | null>(null);
  const queryKey = JSON.stringify([
    page,
    stageFilter,
    decisionFilter,
    fyFilter,
    monthFilter,
  ]);
  const activeQuery = useRef(queryKey);

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
  const uploadButtonRef = useRef<HTMLButtonElement | null>(null);
  const uploadPickerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!uploadModalOpen) return;
    const uploadButton = uploadButtonRef.current;
    uploadPickerRef.current?.focus();
    const keepFocusInUpload = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const dialog = uploadPickerRef.current?.closest('[role="dialog"]');
      const controls = dialog?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [role="button"][tabindex="0"]',
      );
      if (!controls?.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", keepFocusInUpload);
    return () => {
      document.removeEventListener("keydown", keepFocusInUpload);
      uploadButton?.focus();
    };
  }, [uploadModalOpen]);

  const handleQueueTabChange = (tabId: OperationalQueueTab) => {
    setActiveQueueTab(tabId);
    setPage(1);
    const next = new URLSearchParams();
    if (tabId === "needs_attention") {
      next.set("stage", "ACTION_REQUIRED");
      setStageFilter("ACTION_REQUIRED");
      setDecisionFilter("");
    } else if (tabId === "ready") {
      next.set("decision", "MATCH_CANDIDATE");
      setStageFilter("");
      setDecisionFilter("MATCH_CANDIDATE");
    } else if (tabId === "waiting") {
      next.set("decision", "HOLD_PENDING_EVIDENCE");
      setStageFilter("");
      setDecisionFilter("HOLD_PENDING_EVIDENCE");
    } else if (tabId === "approved") {
      next.set("decision", "MANUALLY_APPROVED");
      setStageFilter("");
      setDecisionFilter("MANUALLY_APPROVED");
    } else {
      setStageFilter("");
      setDecisionFilter("");
    }
    setSearchParams(next);
  };

  const handleUploadFile = async (file: File) => {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      setUploadError("File exceeds maximum upload size of 50 MB.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadFeedback(`Uploading ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.uploadDocument(formData);
      setUploadFeedback(
        `Uploaded ${file.name}. Invoice registered into processing queue.`,
      );
      await loadInbox();
      setTimeout(() => {
        setUploadModalOpen(false);
        setUploadFeedback(null);
      }, 1200);
    } catch (err: any) {
      if (err.message && err.message.includes("409")) {
        setUploadError(
          `Duplicate detected: ${file.name} has already been registered.`,
        );
      } else {
        setUploadError(err.message || "Invoice upload failed.");
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
      const mode =
        res.sync_mode === "INCREMENTAL_HISTORY"
          ? "History API"
          : "Full Reconciliation";
      const msg = `${mode}: ${res.ingested_count} ingested, ${res.duplicates_skipped} duplicate(s) skipped.`;
      setSyncFeedback(msg);
      await loadInbox();
    } catch (err: any) {
      setSyncError(err.message || "Mailbox sync failed.");
    } finally {
      setSyncingMailbox(false);
    }
  };

  const loadInbox = useCallback(
    async (background = false) => {
      if (activeQuery.current !== queryKey) return;
      const request = ++requestSequence.current;
      if (!background) setLoading(true);
      try {
        const res = await api.getInbox({
          page,
          stage: stageFilter || undefined,
          decision: decisionFilter || undefined,
          fy: fyFilter || undefined,
          month: monthFilter ? parseInt(monthFilter, 10) : undefined,
        });
        if (
          request !== requestSequence.current ||
          activeQuery.current !== queryKey
        )
          return;
        setData(res);
        setLoadedQuery(queryKey);
        setInboxError(false);
      } catch (err: any) {
        if (
          request !== requestSequence.current ||
          activeQuery.current !== queryKey
        )
          return;
        console.error(err);
        setInboxError(true);
      } finally {
        if (
          request === requestSequence.current &&
          activeQuery.current === queryKey
        )
          setLoading(false);
      }
    },
    [page, stageFilter, decisionFilter, fyFilter, monthFilter, queryKey],
  );

  const handleFyChange = (val: string) => {
    setPage(1);
    setFyFilter(val);
    if (val) {
      localStorage.setItem("ap.inbox.fy", val);
    } else {
      localStorage.removeItem("ap.inbox.fy");
    }
  };

  const handleMonthChange = (val: string) => {
    setPage(1);
    setMonthFilter(val);
    if (val) {
      localStorage.setItem("ap.inbox.month", val);
    } else {
      localStorage.removeItem("ap.inbox.month");
    }
  };

  useEffect(() => {
    activeQuery.current = queryKey;
    const sequence = requestSequence;
    void loadInbox();
    return () => {
      sequence.current++;
    };
  }, [queryKey, loadInbox]);

  useEffect(() => {
    const hasActiveProcessing = data?.items?.some(
      (inv) =>
        inv.stage === "RECEIVED" ||
        inv.job_status === "PROCESSING" ||
        inv.job_status === "QUEUED",
    );
    if (!hasActiveProcessing) return;
    const timer = setInterval(() => {
      if (loading || polling.current) return;
      polling.current = true;
      void loadInbox(true).finally(() => {
        polling.current = false;
      });
    }, 3000);
    return () => clearInterval(timer);
  }, [data?.items, loadInbox, loading]);

  const filteredItems = useMemo(() => {
    if (!data?.items) return [];
    if (!searchQuery.trim()) return data.items;
    const q = searchQuery.toLowerCase().trim();
    return data.items.filter(
      (inv) =>
        (inv.vendor_name || "").toLowerCase().includes(q) ||
        (inv.invoice_number || "").toLowerCase().includes(q) ||
        (inv.po_reference || "").toLowerCase().includes(q) ||
        (inv.vendor_gstin || "").toLowerCase().includes(q) ||
        inv.id.toLowerCase().includes(q),
    );
  }, [data?.items, searchQuery]);

  const queueTabs: FilterTabItem<OperationalQueueTab>[] = [
    { id: "all", label: "All Invoices" },
    { id: "needs_attention", label: "Needs Attention", badgeTone: "warning" },
    { id: "ready", label: "Ready for Approval", badgeTone: "success" },
    { id: "waiting", label: "Waiting on Evidence", badgeTone: "info" },
    { id: "approved", label: "Approved & Cleared", badgeTone: "neutral" },
  ];

  return (
    <div className="inbox-pilot space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        className="inbox-header"
        title="Invoice inbox"
        description="Submit a supplier’s bill, follow its recorded status and open the evidence behind the decision."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="inbox-header-action"
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
              className="inbox-header-action inbox-primary-action"
              ref={uploadButtonRef}
              onClick={() => setUploadModalOpen(true)}
              leftIcon={<UploadCloud className="w-3.5 h-3.5" />}
            >
              Upload Invoice
            </Button>
          </div>
        }
      />

      <ScreenPath
        title="From document to decision"
        links={[
          { to: "/today", label: "Workspace overview" },
          { to: "/settings/connections", label: "Email connection" },
        ]}
      >
        Upload a bill, then open its record to compare the original document
        with extracted fields and check results. Statuses are recorded
        snapshots, not a live execution stream.
      </ScreenPath>

      {/* Sync / Upload Toasts */}
      {syncFeedback && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <span>{syncFeedback}</span>
          <button
            aria-label="Dismiss import result"
            onClick={() => setSyncFeedback(null)}
            className="text-emerald-600 hover:text-emerald-800"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
      {syncError && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center justify-between">
          <span>{syncError}</span>
          <button
            aria-label="Dismiss import error"
            onClick={() => setSyncError(null)}
            className="text-rose-600 hover:text-rose-800"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Operational Filter Tabs (Flick AI Style) */}
      <div data-tour="inbox-queue-tabs" className="inbox-controls">
        <div className="inbox-tabs" aria-label="Invoice queues">
          {queueTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              aria-pressed={activeQueueTab === tab.id}
              onClick={() => handleQueueTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <p
          className="text-xs text-slate-600 dark:text-slate-300"
          aria-live="polite"
        >
          {
            (
              {
                all: "Browse invoices in this view.",
                needs_attention:
                  "Invoices in the action-required stage. Open an invoice to see its checks.",
                ready:
                  "Invoices marked as match candidates. Review their checks before deciding.",
                waiting:
                  "Invoices held while evidence is pending. Open an invoice to see what is needed.",
                approved:
                  "Invoices with a recorded manual approval. Approval does not send a payment.",
              } as Record<OperationalQueueTab, string>
            )[activeQueueTab]
          }
        </p>

        {/* Temporal Period Scoping & Search */}
        <div className="inbox-filters">
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
            aria-label="Search invoices"
            className="inbox-search"
          />

          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadInbox()}
            disabled={loading}
            title="Refresh table"
            aria-label="Refresh table"
            className="inbox-refresh"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </div>

      <p className="text-xs text-slate-600 dark:text-slate-300">
        Search checks only the current page. PO means purchase order; GSTIN is a
        supplier’s tax registration number.
      </p>

      {/* 3. Master Invoices Table */}
      <Card className="inbox-table-card overflow-hidden">
        {(loading && (!data || inboxError)) ||
        (!inboxError && loadedQuery !== queryKey) ? (
          <LoadingState label="Loading invoices..." className="py-16" />
        ) : inboxError ? (
          <ErrorState
            title="Couldn't load invoices"
            message="Your invoices could not be refreshed. Check your connection and try again."
            onRetry={() => loadInbox()}
            className="inbox-error"
          />
        ) : filteredItems.length === 0 ? (
          <EmptyState
            title="No invoices found in this view"
            description={
              searchQuery
                ? `No invoices matched "${searchQuery}". Try clearing search.`
                : "No bills matching the selected queue and period."
            }
            action={
              searchQuery ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setSearchQuery("")}
                >
                  Clear Search
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setUploadModalOpen(true)}
                >
                  Upload an Invoice
                </Button>
              )
            }
            className="inbox-empty py-14 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Invoice & Date</TableHead>
                  <TableHead>Supplier / Vendor</TableHead>
                  <TableHead>Purchase order reference</TableHead>
                  <TableHead className="text-right">Billed Amount</TableHead>
                  <TableHead>Recorded status</TableHead>
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
                    <TableCell className="inbox-row-number">
                      {((data?.page ?? page) - 1) * (data?.page_size ?? 10) +
                        index +
                        1}
                    </TableCell>
                    <TableCell>
                      <div className="inbox-primary-text">
                        {inv.invoice_number || inv.id}
                      </div>
                      <div className="inbox-secondary-text">
                        {inv.created_at
                          ? new Date(inv.created_at).toLocaleDateString()
                          : "Date Pending Extraction"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="inbox-primary-text">
                        {inv.vendor_name || "Supplier not reported"}
                      </div>
                      <div className="inbox-secondary-text">
                        {inv.vendor_gstin || "Tax registration not reported"}
                      </div>
                    </TableCell>
                    <TableCell className="inbox-po">
                      {inv.po_reference || (
                        <span className="text-slate-400">None</span>
                      )}
                    </TableCell>
                    <TableCell className="inbox-amount text-right tabular-nums">
                      {formatCurrency(inv.total_amount, inv.currency)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge invoice={inv} size="sm" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="xs"
                        className="inbox-review-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectInvoice(inv.id);
                        }}
                        rightIcon={
                          <ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                        }
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
        {!inboxError &&
          loadedQuery === queryKey &&
          data &&
          (data.total_pages || 1) > 1 && (
            <div className="inbox-pagination p-3 sm:px-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between text-xs text-slate-500">
              <div>
                Showing page{" "}
                <span className="font-semibold text-slate-900 dark:text-white">
                  {data.page}
                </span>{" "}
                of{" "}
                <span className="font-semibold text-slate-900 dark:text-white">
                  {data.total_pages}
                </span>{" "}
                ({data.total_count} total invoices)
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
                  onClick={() =>
                    setPage((p) => Math.min(data.total_pages, p + 1))
                  }
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
        title="Submit an invoice"
        description="Choose a PDF up to 50 MB and 100 pages. Uploading adds a document to this workspace for processing; it does not approve it."
        maxWidth="md"
      >
        <div className="space-y-4">
          <div
            ref={uploadPickerRef}
            role="button"
            tabIndex={0}
            aria-label="Select an invoice file"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
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
                ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20"
                : "border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-600 bg-slate-50/50 dark:bg-slate-850/40"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleUploadFile(e.target.files[0]);
                }
              }}
              className="hidden"
            />
            {uploading ? (
              <LoadingState
                label="Uploading & registering invoice..."
                className="py-6"
              />
            ) : (
              <>
                <UploadCloud className="w-10 h-10 text-indigo-600 dark:text-indigo-400 mx-auto mb-2.5" />
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 block">
                  Click to select or drag and drop invoice PDF
                </span>
                <span className="text-xs text-slate-400 mt-1 block">
                  Supports standard tax invoices, credit notes, and delivery
                  challans
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
