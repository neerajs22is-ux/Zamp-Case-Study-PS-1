import { ScreenPath } from "../components/ScreenPath";
import React, { useEffect, useMemo, useState } from "react";
import { RefreshCw, User, ChevronRight, ShieldAlert } from "lucide-react";
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
  Modal,
  LoadingState,
  EmptyState,
  ErrorState,
} from "../components/ui";
import type { FilterTabItem } from "../components/ui";
import "./OperationsPages.css";
import type { ExceptionItem } from "../types";

interface ExceptionsPageProps {
  onSelectInvoice: (invoiceId: string) => void;
}

interface TeamMember {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

type ExceptionTab = "all" | "critical" | "high_exposure" | "unassigned";

export const ExceptionsPage: React.FC<ExceptionsPageProps> = ({
  onSelectInvoice,
}) => {
  const [items, setItems] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<ExceptionTab>("all");

  // Reassign Modal State
  const [reassignModalItem, setReassignModalItem] =
    useState<ExceptionItem | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [teamLoadError, setTeamLoadError] = useState(false);
  const [selectedOwnerId, setSelectedOwnerId] = useState<string>("");
  const [reassignReason, setReassignReason] = useState<string>("");
  const [reassignLoading, setReassignLoading] = useState<boolean>(false);
  const [reassignSuccessMsg, setReassignSuccessMsg] = useState<string | null>(
    null,
  );

  const loadExceptions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getExceptions();
      setItems(res.items || []);
    } catch (err: any) {
      setError(err.message || "Could not load exceptions.");
    } finally {
      setLoading(false);
    }
  };

  const loadTeamMembers = async () => {
    setTeamLoadError(false);
    try {
      const res = await api.getMembers();
      if (res && res.items) {
        setTeamMembers(res.items.filter((m: any) => m.is_active));
      }
    } catch (err) {
      console.debug("Failed to load team members:", err);
      setTeamLoadError(true);
    }
  };

  useEffect(() => {
    loadExceptions();
    loadTeamMembers();
  }, []);

  const formatINR = (val: number | null | undefined) => {
    if (val == null) return "Not available";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(val);
  };

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Tab filter
      if (activeTab === "critical" && item.blocking_gate_number < 4)
        return false;
      if (activeTab === "high_exposure" && (item.exposure_amount_inr == null || item.exposure_amount_inr < 500000))
        return false;
      if (activeTab === "unassigned" && item.assigned_user_id) return false;

      // Search filter
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        (item.invoice_number || "").toLowerCase().includes(q) ||
        (item.invoice_id || "").toLowerCase().includes(q) ||
        (item.vendor_name || "").toLowerCase().includes(q) ||
        (item.blocking_gate_name || "").toLowerCase().includes(q) ||
        (item.assigned_user_id || "").toLowerCase().includes(q)
      );
    });
  }, [items, activeTab, searchQuery]);

  const handleOpenReassign = (e: React.MouseEvent, item: ExceptionItem) => {
    e.stopPropagation();
    setReassignModalItem(item);
    setSelectedOwnerId(item.assigned_user_id || "");
    setReassignReason("");
    setReassignSuccessMsg(null);
  };

  const handleConfirmReassign = async () => {
    if (!reassignModalItem || !selectedOwnerId) return;
    setReassignLoading(true);
    try {
      await api.reassignException(
        reassignModalItem.exception_id,
        selectedOwnerId,
        reassignReason || "Task routed for operational investigation.",
      );
      setReassignSuccessMsg("Exception reassigned successfully.");
      setTimeout(() => {
        setReassignModalItem(null);
        loadExceptions();
      }, 700);
    } catch (err: any) {
      alert(`Reassign failed: ${err.message}`);
    } finally {
      setReassignLoading(false);
    }
  };

  const tabs: FilterTabItem<ExceptionTab>[] = [
    { id: "all", label: "All Exceptions", count: items.length },
    {
      id: "critical",
      label: "Core Discrepancies",
      count: items.filter((i) => i.blocking_gate_number >= 4).length,
      badgeTone: "error",
    },
    {
      id: "high_exposure",
      label: "High Exposure (≥ ₹5L)",
      count: items.filter((i) => i.exposure_amount_inr != null && i.exposure_amount_inr >= 500000).length,
      badgeTone: "warning",
    },
    {
      id: "unassigned",
      label: "Unassigned",
      count: items.filter((i) => !i.assigned_user_id).length,
      badgeTone: "neutral",
    },
  ];

  return (
    <div className="operations-page space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        className="operations-header"
        title="Exceptions"
        description="Each exception is an issue record, so counts here are not invoice counts. Exposure is the amount recorded for the issue. Open the invoice to investigate."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={loadExceptions}
            isLoading={loading}
            leftIcon={
              <RefreshCw
                className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
              />
            }
          >
            Refresh
          </Button>
        }
      />

      <ScreenPath
        title="Investigate the issue before deciding"
        links={[
          { to: "/invoices", label: "Invoice inbox" },
          { to: "/audit", label: "Recorded history" },
        ]}
      >
        Start with the named failed check, inspect the invoice evidence, then
        assign follow-up to the appropriate colleague. Reassigning an issue does
        not resolve it.
      </ScreenPath>

      {error && <ErrorState message={error} onRetry={loadExceptions} />}

      {/* 2. Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <FilterTabs
          className="operations-tabs"
          tabs={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          aria-label="Search exceptions"
          placeholder="Search by invoice, vendor, issue..."
          className="w-full sm:w-64"
        />
      </div>

      {/* 3. Exceptions Table */}
      <Card
        data-tour="exceptions-table"
        className="operations-table overflow-hidden"
      >
        {loading && items.length === 0 ? (
          <LoadingState label="Loading exception queue..." className="py-16" />
        ) : error && items.length === 0 ? null : filteredItems.length === 0 ? (
          <EmptyState
            title="No exceptions in this queue"
            description={
              searchQuery
                ? `No records matched "${searchQuery}".`
                : "No exceptions match the selected queue."
            }
            className="py-12 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead>Invoice & Supplier</TableHead>
                  <TableHead>Issue</TableHead>
                  <TableHead className="text-right">Exposure Amount</TableHead>
                  <TableHead>Statutory Deadline</TableHead>
                  <TableHead>Assigned Owner</TableHead>
                  <TableHead className="text-right">Next action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => (
                  <TableRow
                    key={item.exception_id}
                    onClick={() => onSelectInvoice(item.invoice_id)}
                    className="group"
                  >
                    <TableCell>
                      <div className="font-mono font-semibold text-slate-900 dark:text-white">
                        {item.invoice_number || item.invoice_id}
                      </div>
                      <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                        {item.vendor_name || "Supplier not reported"}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Badge tone="error" size="sm">
                          Gate {item.blocking_gate_number}
                        </Badge>
                        <span className="font-medium text-slate-800 dark:text-slate-200 text-xs">
                          {item.blocking_gate_name}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="text-right font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                      {item.exposure_amount_inr == null ? `INR equivalent unavailable (${item.currency})` : formatINR(item.exposure_amount_inr)}
                    </TableCell>

                    <TableCell>
                      {item.msme_statutory_deadline ? (
                        <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-mono">
                          <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                          <span>
                            {new Date(
                              item.msme_statutory_deadline,
                            ).toLocaleDateString()}
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs">
                          Not available
                        </span>
                      )}
                    </TableCell>

                    <TableCell>
                      <button
                        type="button"
                        onClick={(e) => handleOpenReassign(e, item)}
                        className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium cursor-pointer"
                        title="Click to reassign owner"
                      >
                        <User className="w-3.5 h-3.5" />
                        <span>
                          {item.assigned_user_id
                            ? `${item.assigned_user_id} · Reassign`
                            : "Assign owner"}
                        </span>
                      </button>
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectInvoice(item.invoice_id);
                        }}
                        rightIcon={
                          <ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                        }
                      >
                        Inspect invoice
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Reassign Modal */}
      {reassignModalItem && (
        <Modal
          className="operations-dialog"
          isOpen={Boolean(reassignModalItem)}
          onClose={() => setReassignModalItem(null)}
          title="Assign responsibility for this issue"
          description={`Choose who will follow up on the issue for invoice ${reassignModalItem.invoice_number || reassignModalItem.invoice_id}. This does not resolve the issue or approve the invoice.`}
          maxWidth="md"
          footer={
            <div className="flex items-center justify-end gap-2.5 w-full">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setReassignModalItem(null)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmReassign}
                isLoading={reassignLoading}
                disabled={!selectedOwnerId}
              >
                Confirm Assignment
              </Button>
            </div>
          }
        >
          <div className="space-y-3 text-xs">
            <p className="operations-dialog-note">
              Reassignment requires an AP Lead, Controller or System Admin role.
            </p>
            {teamLoadError && (
              <p role="alert" className="text-rose-700 dark:text-rose-300">
                Could not load assignees.{" "}
                <button
                  type="button"
                  onClick={loadTeamMembers}
                  className="underline"
                >
                  Retry
                </button>
              </p>
            )}
            {reassignSuccessMsg && (
              <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                {reassignSuccessMsg}
              </div>
            )}

            <div>
              <label
                htmlFor="exception-owner"
                className="font-semibold text-slate-800 dark:text-slate-200 block mb-1"
              >
                Select Team Member
              </label>
              <select
                id="exception-owner"
                value={selectedOwnerId}
                onChange={(e) => setSelectedOwnerId(e.target.value)}
                className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
              >
                <option value="">-- Choose assignee --</option>
                {teamMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} ({m.email}) — {m.role}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="exception-note"
                className="font-semibold text-slate-800 dark:text-slate-200 block mb-1"
              >
                Assignment Note
              </label>
              <textarea
                id="exception-note"
                rows={2}
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
                placeholder="Reason for routing this discrepancy..."
                className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
