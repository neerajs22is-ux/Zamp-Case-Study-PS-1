import { ScreenPath } from "../components/ScreenPath";
import React, { useEffect, useState, useMemo } from "react";
import {
  Download,
  RefreshCw,
  Lock,
  ChevronRight,
  Copy,
  Check,
  User,
} from "lucide-react";
import { api } from "../api/client";
import {
  PageHeader,
  Card,
  Button,
  Badge,
  SearchInput,
  FilterTabs,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Drawer,
  LoadingState,
  EmptyState,
  ErrorState,
} from "../components/ui";
import type { FilterTabItem } from "../components/ui";
import "./OperationsPages.css";
import type { AuditEventItem, AuthenticatedUser } from "../types";

interface AuditPageProps {
  currentUser?: AuthenticatedUser | null;
}

type AuditCategory = "all" | "approval" | "invoice" | "security";

const ACTION_LABELS: Record<
  string,
  {
    label: string;
    tone: "success" | "warning" | "error" | "info" | "purple" | "neutral";
    category: AuditCategory;
  }
> = {
  APPROVE_AP_REVIEW: {
    label: "Approved (AP Review)",
    tone: "success",
    category: "approval",
  },
  APPROVE_UNDISPUTED: {
    label: "Approved (Undisputed)",
    tone: "success",
    category: "approval",
  },
  DUAL_APPROVAL_SIGNED: {
    label: "Dual-Approval Signed",
    tone: "purple",
    category: "approval",
  },
  REJECT_INVOICE: {
    label: "Rejected Invoice",
    tone: "error",
    category: "invoice",
  },
  QUARANTINE: { label: "Quarantined", tone: "purple", category: "invoice" },
  HOLD_PENDING_EVIDENCE: {
    label: "Held for Evidence",
    tone: "warning",
    category: "invoice",
  },
  REQUEST_SUPPLIER_CORRECTION: {
    label: "Correction Requested",
    tone: "info",
    category: "invoice",
  },
  RAISE_DEBIT_NOTE: {
    label: "Debit Note Raised",
    tone: "purple",
    category: "invoice",
  },
  EXCEPTION_REASSIGNED: {
    label: "Exception Reassigned",
    tone: "info",
    category: "invoice",
  },
  DOCUMENT_UPLOADED: {
    label: "Document Uploaded",
    tone: "neutral",
    category: "invoice",
  },
  USER_INVITED: { label: "User Invited", tone: "info", category: "security" },
  ROLE_UPDATED: { label: "Role Updated", tone: "purple", category: "security" },
  USER_DEACTIVATED: {
    label: "User Deactivated",
    tone: "error",
    category: "security",
  },
  ACCESS_REQUEST_APPROVED: {
    label: "Access Approved",
    tone: "success",
    category: "security",
  },
};

export const AuditPage: React.FC<AuditPageProps> = ({ currentUser }) => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<AuditCategory>("all");

  // Event Details Drawer State
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(
    null,
  );
  const [copiedSha, setCopiedSha] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const canExport =
    currentUser?.role &&
    ["AUDITOR", "CONTROLLER", "SYSTEM_ADMIN"].includes(currentUser.role);

  const loadAudit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAudit({ limit: 100 });
      setEvents(res.items || []);
    } catch (err: any) {
      setError(err.message || "Could not load audit events.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudit();
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (activeCategory !== "all") {
        const meta = ACTION_LABELS[e.action];
        if (!meta || meta.category !== activeCategory) return false;
      }
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        (e.reason || "").toLowerCase().includes(q) ||
        (e.action || "").toLowerCase().includes(q) ||
        (e.invoice_id || "").toLowerCase().includes(q) ||
        (e.actor_id || "").toLowerCase().includes(q) ||
        (e.actor_role || "").toLowerCase().includes(q) ||
        (e.correlation_id || "").toLowerCase().includes(q)
      );
    });
  }, [events, activeCategory, searchQuery]);

  const handleCopySha = (sha?: string) => {
    if (!sha) return;
    navigator.clipboard.writeText(sha);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2000);
  };

  const handleExportAudit = () => {
    const csvContent =
      "data:text/csv;charset=utf-8," +
      "ID,Timestamp,Actor,Role,Action,InvoiceID,Reason,CorrelationID\n" +
      filteredEvents
        .map(
          (e) =>
            `"${e.id}","${e.timestamp}","${e.actor_id}","${e.actor_role}","${e.action}","${e.invoice_id || ""}","${(e.reason || "").replace(/"/g, '""')}","${e.correlation_id || ""}"`,
        )
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `ap_audit_trail_${new Date().toISOString().slice(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setExportNotice("Audit trail exported successfully.");
    setTimeout(() => setExportNotice(null), 3000);
  };

  const tabs: FilterTabItem<AuditCategory>[] = [
    { id: "all", label: "All Activity", count: events.length },
    {
      id: "approval",
      label: "Approvals & Sign-Offs",
      count: events.filter(
        (e) => ACTION_LABELS[e.action]?.category === "approval",
      ).length,
      badgeTone: "success",
    },
    {
      id: "invoice",
      label: "Invoice Operations",
      count: events.filter(
        (e) => ACTION_LABELS[e.action]?.category === "invoice",
      ).length,
      badgeTone: "info",
    },
    {
      id: "security",
      label: "Governance & Access",
      count: events.filter(
        (e) => ACTION_LABELS[e.action]?.category === "security",
      ).length,
      badgeTone: "purple",
    },
  ];

  return (
    <div className="operations-page space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        className="operations-header"
        title="Audit trail"
        description="This view loads up to 100 recent events, not the complete ledger. An actor is the person or system that performed an action. Search and export apply to loaded events."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={loadAudit}
              isLoading={loading}
              leftIcon={
                <RefreshCw
                  className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
                />
              }
            >
              Refresh
            </Button>
            {canExport && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleExportAudit}
                leftIcon={<Download className="w-3.5 h-3.5" />}
              >
                Export CSV
              </Button>
            )}
          </div>
        }
      />

      {exportNotice && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
          {exportNotice}
        </div>
      )}

      <ScreenPath
        title="Reconstruct a recorded decision"
        links={[
          { to: "/invoices", label: "Find an invoice" },
          { to: "/today", label: "Workspace overview" },
        ]}
      >
        Find the event, open Details for its reason and references, then follow
        the invoice to its source and check results. Search and export cover the
        events loaded here.
      </ScreenPath>

      {error && <ErrorState message={error} onRetry={loadAudit} />}

      {/* 2. Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <FilterTabs
          className="operations-tabs"
          tabs={tabs}
          activeTab={activeCategory}
          onChange={setActiveCategory}
        />

        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          aria-label="Search audit events"
          placeholder="Filter by actor, action, invoice..."
          className="w-full sm:w-64"
        />
      </div>

      {/* 3. Audit Events Table */}
      <Card
        data-tour="audit-table"
        className="operations-table overflow-hidden"
      >
        {loading && events.length === 0 ? (
          <LoadingState label="Loading audit records..." className="py-16" />
        ) : error && events.length === 0 ? null : filteredEvents.length ===
          0 ? (
          <EmptyState
            title="No audit events found"
            description={
              searchQuery
                ? `No records matched "${searchQuery}".`
                : "No activity recorded in this category."
            }
            className="py-12 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Reason / event</TableHead>
                  <TableHead>Actor / Role</TableHead>
                  <TableHead>Related Invoice</TableHead>
                  <TableHead>Action Type</TableHead>
                  <TableHead className="text-right">Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEvents.map((e) => {
                  const meta = ACTION_LABELS[e.action] || {
                    label: e.action?.replace(/_/g, " "),
                    tone: "neutral",
                  };
                  return (
                    <TableRow
                      key={e.id}
                      onClick={() => setSelectedEvent(e)}
                      className="group"
                    >
                      <TableCell className="font-mono text-slate-500 text-[11px] whitespace-nowrap">
                        {new Date(e.timestamp).toLocaleDateString()}{" "}
                        <span className="text-slate-400">
                          {new Date(e.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </TableCell>

                      <TableCell>
                        <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                          {e.reason || meta.label}
                        </span>
                        {e.source_reference && (
                          <span className="text-[11px] text-slate-400 italic block mt-0.5 line-clamp-1 font-mono">
                            Ref: {e.source_reference}
                          </span>
                        )}
                      </TableCell>

                      <TableCell>
                        <div className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300">
                          <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="font-medium truncate">
                            {e.actor_id}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono">
                            {e.actor_role}
                          </span>
                        </div>
                      </TableCell>

                      <TableCell className="font-mono text-xs">
                        {e.invoice_id ? (
                          <span className="text-indigo-600 dark:text-indigo-400 font-semibold">
                            {e.invoice_id}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </TableCell>

                      <TableCell>
                        <Badge tone={meta.tone} size="sm">
                          {meta.label}
                        </Badge>
                      </TableCell>

                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={(evt) => {
                            evt.stopPropagation();
                            setSelectedEvent(e);
                          }}
                          rightIcon={<ChevronRight className="w-3 h-3" />}
                        >
                          Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Slide-Over Event Detail Drawer */}
      <Drawer
        className="operations-dialog"
        isOpen={Boolean(selectedEvent)}
        onClose={() => setSelectedEvent(null)}
        title={
          <div className="flex items-center gap-2">
            <Lock className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>Audit Event Verification</span>
          </div>
        }
        description="Inspect the recorded actor, reason, references and available before/after details for this event."
        width="md"
      >
        {selectedEvent && (
          <div className="space-y-4 text-xs">
            <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-2 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Event ID:</span>
                <span className="text-slate-800 dark:text-slate-200 truncate max-w-[200px]">
                  {selectedEvent.id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Timestamp:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {new Date(selectedEvent.timestamp).toISOString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Actor ID:</span>
                <span className="text-indigo-600 dark:text-indigo-400 font-sans font-semibold">
                  {selectedEvent.actor_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Actor Role:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {selectedEvent.actor_role}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Action:</span>
                <span className="text-slate-800 dark:text-slate-200">
                  {selectedEvent.action}
                </span>
              </div>
            </div>

            <div>
              <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-1">
                Event Description
              </span>
              <p className="text-slate-600 dark:text-slate-300 p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 leading-relaxed">
                {selectedEvent.reason ||
                  selectedEvent.action?.replace(/_/g, " ") ||
                  "Action recorded in audit log."}
              </p>
            </div>

            {selectedEvent.source_reference && (
              <div>
                <span className="font-semibold block mb-1">
                  Source reference
                </span>
                <p className="operations-source">
                  {selectedEvent.source_reference}
                </p>
              </div>
            )}

            {selectedEvent.correlation_id && (
              <div className="space-y-1.5 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  Correlation & Cryptographic Tracking ID
                </span>
                <div className="p-2.5 rounded-lg bg-slate-900 text-slate-100 font-mono text-[11px] break-all flex items-center justify-between gap-2">
                  <span>{selectedEvent.correlation_id}</span>
                  <button
                    type="button"
                    onClick={() =>
                      handleCopySha(selectedEvent.correlation_id || undefined)
                    }
                    className="p-1 hover:bg-slate-800 rounded shrink-0 text-slate-400 hover:text-white"
                    title="Copy correlation ID"
                  >
                    {copiedSha ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>
            )}

            {(selectedEvent.before_state || selectedEvent.after_state) && (
              <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  State Transition Diff
                </span>
                <div className="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-850 font-mono text-[10px] overflow-x-auto max-h-48 text-slate-700 dark:text-slate-300">
                  <pre>
                    {JSON.stringify(
                      {
                        before: selectedEvent.before_state,
                        after: selectedEvent.after_state,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};
