import { ScreenPath } from "../components/ScreenPath";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  RefreshCw,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { api } from "../api/client";
import {
  PageHeader,
  Card,
  Button,
  Badge,
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
import type { AuthenticatedUser } from "../types";
import { formatCurrency } from "../utils/currency";

interface ApprovalsPageProps {
  currentUser?: AuthenticatedUser | null;
}

type ApprovalTab = "pending" | "approved" | "all";

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({
  currentUser,
}) => {
  const navigate = useNavigate();
  const [approvals, setApprovals] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<ApprovalTab>("pending");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Controller Dual Sign-off Modal State
  const [selectedApproval, setSelectedApproval] = useState<any | null>(null);
  const [controllerNote, setControllerNote] = useState<string>(
    "Dual-approval authorized by Financial Controller.",
  );
  const [isSubmittingApproval, setIsSubmittingApproval] =
    useState<boolean>(false);
  const [approvalSuccess, setApprovalSuccess] = useState<string | null>(null);

  const isAuditor = currentUser?.role === "AUDITOR";
  const isController =
    currentUser?.role === "CONTROLLER" || currentUser?.role === "SYSTEM_ADMIN";

  const fetchApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getApprovals();
      setApprovals(res.items || []);
    } catch (err: any) {
      setError(err.message || "Failed to load approvals queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const formatINR = (amount?: number) => {
    if (amount === undefined || amount === null) return "—";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const filteredApprovals = approvals.filter((item) => {
    if (activeTab === "pending")
      return item.status === "PENDING_SECOND_APPROVAL";
    if (activeTab === "approved") return item.status === "APPROVED";
    return true;
  });

  const pendingCount = approvals.filter(
    (a) => a.status === "PENDING_SECOND_APPROVAL",
  ).length;
  const approvedCount = approvals.filter((a) => a.status === "APPROVED").length;

  const handleConfirmDualApproval = async () => {
    if (!selectedApproval) return;
    setIsSubmittingApproval(true);
    try {
      await api.executeAction(
        selectedApproval.invoice_id || selectedApproval.id,
        "APPROVE_AP_REVIEW",
        controllerNote.trim() || "Controller dual approval recorded.",
      );
      setApprovalSuccess(
        `Invoice ${selectedApproval.invoice_number || selectedApproval.id} authorized.`,
      );
      setSelectedApproval(null);
      await fetchApprovals();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  const tabs: FilterTabItem<ApprovalTab>[] = [
    {
      id: "pending",
      label: "Awaiting Controller Review",
      count: pendingCount,
      badgeTone: "warning",
    },
    {
      id: "approved",
      label: "Signed Off",
      count: approvedCount,
      badgeTone: "success",
    },
    { id: "all", label: "All Approval Records", count: approvals.length },
  ];

  return (
    <div className="operations-page space-y-5">
      {/* 1. Page Header */}
      <PageHeader
        className="operations-header"
        title="Approvals"
        description="Review invoices requiring an independent second sign-off. Internal sign-off records a decision; it does not send a payment."
        badge={
          isAuditor ? (
            <Badge tone="info" size="sm">
              Auditor Mode (Read-Only)
            </Badge>
          ) : undefined
        }
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchApprovals}
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
        title="An independent internal sign-off"
        links={[
          { to: "/invoices", label: "Invoice evidence" },
          { to: "/audit", label: "Sign-off history" },
        ]}
      >
        Inspect the first reviewer, outstanding checks and your eligibility on
        each record. A second sign-off must come from a different authorized
        person; the server validates the action.
      </ScreenPath>

      {error && <ErrorState message={error} onRetry={fetchApprovals} />}

      {/* Success Notification */}
      {approvalSuccess && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <span>{approvalSuccess}</span>
          <button
            onClick={() => setApprovalSuccess(null)}
            className="text-emerald-600 hover:text-emerald-800"
          >
            &times;
          </button>
        </div>
      )}

      {/* 2. Governance Policy Notice */}
      <div className="operations-notice p-4 rounded-xl flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
        <div className="text-xs text-purple-950 dark:text-purple-200 space-y-1">
          <p className="font-semibold text-sm">Independent second sign-off</p>
          <p className="text-purple-800 dark:text-purple-300/90 leading-relaxed">
            The second sign-off must be made by a different person with the
            Controller or System Admin role. Eligibility and any failed checks
            are shown on each record.
          </p>
        </div>
      </div>

      {/* 3. Filter Tabs */}
      <div className="flex items-center justify-between">
        <FilterTabs
          className="operations-tabs"
          tabs={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />
      </div>

      {/* 4. Table */}
      <Card
        data-tour="approvals-table"
        className="operations-table overflow-hidden"
      >
        {loading && approvals.length === 0 ? (
          <LoadingState
            label="Loading second-sign-off records…"
            className="py-16"
          />
        ) : error &&
          approvals.length === 0 ? null : filteredApprovals.length === 0 ? (
          <EmptyState
            title="No approval records in this view"
            description="No records match the selected queue."
            className="py-12 border-none bg-transparent"
          />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow isInteractive={false}>
                  <TableHead>Invoice & Supplier</TableHead>
                  <TableHead className="text-right">Billed Amount</TableHead>
                  <TableHead>Primary Review Sign-Off</TableHead>
                  <TableHead>Dual-Approval Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredApprovals.map((item) => (
                  <TableRow
                    key={item.id}
                    onClick={() =>
                      navigate(`/invoices/${item.invoice_id || item.id}`)
                    }
                    className="group"
                  >
                    <TableCell>
                      <div className="font-mono font-semibold text-slate-900 dark:text-white">
                        {item.invoice_number || item.id}
                      </div>
                      <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                        {item.vendor_name || "Supplier unavailable"}
                      </div>
                    </TableCell>

                    <TableCell className="text-right font-mono font-semibold text-slate-900 dark:text-white tabular-nums">
                      <div className="text-sm">
                        {formatCurrency(item.total_amount, item.currency)}
                      </div>
                      {item.threshold_inr != null && (
                        <div className="operations-meta">
                          Threshold: {formatINR(item.threshold_inr)}
                        </div>
                      )}
                    </TableCell>

                    <TableCell>
                      <div className="text-xs font-medium text-slate-800 dark:text-slate-200">
                        {item.first_approver_name ||
                          item.first_approver_id ||
                          "Not available"}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {item.first_approved_at
                          ? new Date(
                              item.first_approved_at,
                            ).toLocaleDateString()
                          : "Date unavailable"}
                      </div>
                    </TableCell>

                    <TableCell>
                      {item.status === "APPROVED" ? (
                        <Badge
                          tone="success"
                          size="sm"
                          icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                        >
                          Internal sign-off complete
                        </Badge>
                      ) : item.status === "PENDING_SECOND_APPROVAL" ? (
                        <Badge tone="warning" size="sm" dot>
                          Awaiting second sign-off
                        </Badge>
                      ) : (
                        <Badge tone="neutral" size="sm">
                          {item.status || "Status unavailable"}
                        </Badge>
                      )}
                      {item.status === "PENDING_SECOND_APPROVAL" &&
                        item.can_approve === false && (
                          <p className="operations-eligibility">
                            {item.cannot_approve_reason ||
                              "Not eligible for second sign-off."}
                          </p>
                        )}
                      {item.status === "PENDING_SECOND_APPROVAL" &&
                        isController &&
                        item.can_approve == null && (
                          <p className="operations-eligibility">
                            Eligibility is not confirmed. The server will check
                            when you submit.
                          </p>
                        )}
                    </TableCell>

                    <TableCell className="text-right">
                      {item.status === "PENDING_SECOND_APPROVAL" &&
                      isController &&
                      item.can_approve !== false ? (
                        <Button
                          variant="primary"
                          size="xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedApproval(item);
                            setControllerNote(
                              "Controller dual approval authorized.",
                            );
                          }}
                          leftIcon={<ShieldCheck className="w-3 h-3" />}
                        >
                          {item.can_approve == null
                            ? "Review sign-off"
                            : "Sign Off"}
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/invoices/${item.invoice_id || item.id}`);
                          }}
                          rightIcon={
                            <ChevronRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
                          }
                        >
                          Review
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Lean Controller Approval Dialog (45 words) */}
      {selectedApproval && (
        <Modal
          className="operations-dialog"
          isOpen={Boolean(selectedApproval)}
          onClose={() => setSelectedApproval(null)}
          title="Record a second internal sign-off"
          description={`Review invoice ${selectedApproval.invoice_number || selectedApproval.id} before recording an independent sign-off. This action does not send a payment.`}
          maxWidth="md"
          footer={
            <div className="flex items-center justify-end gap-2.5 w-full">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedApproval(null)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmDualApproval}
                isLoading={isSubmittingApproval}
                leftIcon={<ShieldCheck className="w-3.5 h-3.5" />}
              >
                Confirm Controller Sign-Off
              </Button>
            </div>
          }
        >
          <div className="space-y-3.5 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-850 border border-slate-200 dark:border-slate-800 space-y-1.5 font-mono">
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Supplier:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {selectedApproval.vendor_name || "Vendor"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">Total Amount:</span>
                <span className="font-bold text-slate-900 dark:text-white tabular-nums">
                  {formatCurrency(selectedApproval.total_amount, selectedApproval.currency)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-sans">
                  Step 1 Specialist:
                </span>
                <span className="text-indigo-600 dark:text-indigo-400 font-sans">
                  {selectedApproval.first_approver_name ||
                    selectedApproval.first_approver_id ||
                    "Not available"}
                </span>
              </div>
            </div>

            <p className="text-slate-600 dark:text-slate-400 text-[11px] leading-relaxed">
              By confirming, you request a second internal sign-off. The server
              checks your eligibility before recording it; this does not make a
              payment.
            </p>

            <div>
              <label
                htmlFor="controller-note"
                className="font-semibold text-slate-800 dark:text-slate-200 block mb-1"
              >
                Audit Note
              </label>
              <input
                id="controller-note"
                type="text"
                value={controllerNote}
                onChange={(e) => setControllerNote(e.target.value)}
                placeholder="Controller sign-off justification..."
                className="w-full p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
