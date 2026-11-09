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
  ExternalLink,
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
                      <TableCell className="font-mono text-slate-500 dark:text-slate-400 text-[11px] whitespace-nowrap py-3.5">
                        <span className="font-semibold text-slate-700 dark:text-slate-200 block">
                          {new Date(e.timestamp).toLocaleDateString()}
                        </span>
                        <span className="text-[10.5px] text-slate-400">
                          {new Date(e.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </span>
                      </TableCell>

                      <TableCell className="py-3.5">
                        <span className="font-bold text-slate-900 dark:text-white text-xs sm:text-[13px] block leading-tight">
                          {e.reason || meta.label}
                        </span>
                        {e.source_reference && (
                          <span className="text-[11px] text-slate-400 italic block mt-1 line-clamp-1 font-mono">
                            Ref: {e.source_reference}
                          </span>
                        )}
                      </TableCell>

                      <TableCell className="py-3.5">
                        <div className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300">
                          <User className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                          <span className="font-medium truncate max-w-[120px] text-slate-800 dark:text-slate-200">
                            {e.actor_id}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {e.actor_role}
                          </span>
                        </div>
                      </TableCell>

                      <TableCell className="font-mono text-xs py-3.5">
                        {e.invoice_id ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded font-semibold text-xs bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/60">
                            {e.invoice_id}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </TableCell>

                      <TableCell className="py-3.5">
                        <Badge tone={meta.tone} size="sm" className="font-semibold">
                          {meta.label}
                        </Badge>
                      </TableCell>

                      <TableCell className="text-right py-3.5">
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={(evt) => {
                            evt.stopPropagation();
                            setSelectedEvent(e);
                          }}
                          rightIcon={<ChevronRight className="w-3 h-3 text-indigo-500" />}
                          className="font-medium hover:border-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors shadow-2xs"
                        >
                          Inspect
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
            {/* 1. Human-Readable Event Summary Header */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <Badge
                  tone={
                    ACTION_LABELS[selectedEvent.action]?.tone || "neutral"
                  }
                  size="md"
                  className="font-semibold"
                >
                  {ACTION_LABELS[selectedEvent.action]?.label ||
                    selectedEvent.action?.replace(/_/g, " ")}
                </Badge>
                <span className="text-[11px] font-mono text-slate-400">
                  {new Date(selectedEvent.timestamp).toLocaleDateString()} at{" "}
                  {new Date(selectedEvent.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
              </div>

              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                  Event Reason & Summary
                </span>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 leading-snug">
                  {selectedEvent.reason ||
                    ACTION_LABELS[selectedEvent.action]?.label ||
                    selectedEvent.action?.replace(/_/g, " ")}
                </p>
              </div>
            </div>

            {/* 2. Structured Actor & Governance Details */}
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                Actor & Governance Context
              </span>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[10px] text-slate-500 block">Operator / Actor</span>
                  <div className="flex items-center gap-1.5 font-medium text-slate-800 dark:text-slate-200 mt-0.5">
                    <User className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                    <span className="truncate">{selectedEvent.actor_id}</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-slate-500 block">Governance Role</span>
                  <span className="inline-block px-2 py-0.5 mt-0.5 rounded text-[10.5px] font-mono font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {selectedEvent.actor_role}
                  </span>
                </div>

                {selectedEvent.invoice_id && (
                  <div className="col-span-2 pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-slate-500 block">Related Invoice</span>
                      <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 text-xs">
                        {selectedEvent.invoice_id}
                      </span>
                    </div>
                    <a
                      href={`/invoices`}
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 font-medium"
                    >
                      <span>View in Invoices</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                )}

                {selectedEvent.source_reference && (
                  <div className="col-span-2 pt-1 border-t border-slate-100 dark:border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Source Reference</span>
                    <p className="font-mono text-[10.5px] text-slate-600 dark:text-slate-400 truncate mt-0.5" title={selectedEvent.source_reference}>
                      {selectedEvent.source_reference}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* 3. Human-Readable State Transition Summary */}
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                State Transition Summary
              </span>

              {selectedEvent.before_state || selectedEvent.after_state ? (
                <div className="space-y-2">
                  {/* Extract recognizable fields: stage, decision, status, amounts */}
                  {(() => {
                    const before = selectedEvent.before_state || {};
                    const after = selectedEvent.after_state || {};
                    const allKeys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)]));
                    const changedKeys = allKeys.filter(
                      (k) => JSON.stringify(before[k]) !== JSON.stringify(after[k])
                    );

                    if (changedKeys.length === 0) {
                      return (
                        <p className="text-slate-500 text-xs italic">
                          Initial immutable event snapshot recorded. No previous state modified.
                        </p>
                      );
                    }

                    return changedKeys.map((key) => {
                      const beforeVal = before[key];
                      const afterVal = after[key];
                      const keyLabel = key.replace(/_/g, " ").toUpperCase();

                      return (
                        <div
                          key={key}
                          className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs"
                        >
                          <span className="font-medium text-slate-600 dark:text-slate-400">
                            {keyLabel}:
                          </span>
                          <div className="flex items-center gap-1.5 font-mono text-[11px]">
                            <span className="text-slate-400 line-through">
                              {beforeVal !== undefined && beforeVal !== null
                                ? String(beforeVal)
                                : "None"}
                            </span>
                            <span className="text-slate-400">&rarr;</span>
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                              {afterVal !== undefined && afterVal !== null
                                ? String(afterVal)
                                : "None"}
                            </span>
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>
              ) : (
                <p className="text-slate-500 text-xs italic">
                  Event recorded with no preceding state modification.
                </p>
              )}
            </div>

            {/* 4. Collapsible Advanced Technical Details (Forensic & Cryptographic) */}
            <details className="group border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50/50 dark:bg-slate-900/40">
              <summary className="p-3 cursor-pointer text-[11px] font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center justify-between select-none">
                <span>Advanced Technical Details (Forensics & Hashes)</span>
                <span className="text-[10px] text-indigo-600 dark:text-indigo-400 group-open:rotate-180 transition-transform">
                  ▼
                </span>
              </summary>

              <div className="p-3 pt-0 border-t border-slate-200/60 dark:border-slate-800/60 space-y-3 font-mono text-[10.5px]">
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500 font-sans">Event ID:</span>
                  <div className="flex items-center gap-1">
                    <span className="text-slate-700 dark:text-slate-300">{selectedEvent.id}</span>
                    <button
                      type="button"
                      onClick={() => handleCopySha(selectedEvent.id)}
                      className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded text-slate-400"
                      title="Copy Event ID"
                    >
                      {copiedSha ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {selectedEvent.correlation_id && (
                  <div className="flex justify-between items-center py-1 border-t border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-sans">Correlation ID:</span>
                    <span className="text-slate-700 dark:text-slate-300 truncate max-w-[180px]">
                      {selectedEvent.correlation_id}
                    </span>
                  </div>
                )}

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                  <span className="font-sans font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                    Raw JSON Snapshot:
                  </span>
                  <pre className="p-2.5 rounded bg-slate-900 text-slate-200 text-[10px] overflow-x-auto max-h-40">
                    {JSON.stringify(
                      {
                        action: selectedEvent.action,
                        actor: selectedEvent.actor_id,
                        role: selectedEvent.actor_role,
                        before: selectedEvent.before_state,
                        after: selectedEvent.after_state,
                      },
                      null,
                      2
                    )}
                  </pre>
                </div>
              </div>
            </details>
          </div>
        )}
      </Drawer>
    </div>
  );
};
