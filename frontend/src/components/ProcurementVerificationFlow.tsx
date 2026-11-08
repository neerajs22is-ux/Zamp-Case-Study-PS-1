import { useDialogFocus } from "../hooks/useDialogFocus";
import React, { useState } from "react";
import {
  ShoppingCart,
  Truck,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Columns,
  Layers,
  Edit3,
  Save,
  X,
  AlertTriangle,
} from "lucide-react";

interface InvoiceLine {
  id?: string;
  line_number: number;
  description: string;
  quantity: number;
  rate: number;
  total: number;
  is_corrected?: boolean;
  previous_unit_rate?: number | null;
  line_version?: number;
}

interface POLine {
  line_number: number;
  item_code?: string;
  description: string;
  authorized_quantity: number;
  contracted_unit_rate: number;
  authorized_line_total: number;
}

interface ProcurementVerificationFlowProps {
  invoice: any;
  lines: InvoiceLine[];
  poSnapshot?: {
    po_number: string;
    vendor_code?: string;
    total_authorized_amount?: number;
    remaining_balance?: number;
    currency?: string;
    status?: string;
    retrieved_at?: string;
    lines?: POLine[];
    grn?: {
      grn_number?: string;
      received_date?: string;
      lines?: any[];
    } | null;
    qc?: {
      qc_certificate_number?: string;
      overall_status?: string;
    } | null;
  } | null;
  rateTolerancePercent?: number;
  onOpenGlossary?: (term?: string) => void;
  onCorrectLine?: (
    lineId: string,
    payload: {
      billed_quantity: number;
      billed_unit_rate: number;
      correction_reason: string;
    },
  ) => Promise<void>;
  isAuditor?: boolean;
}

export const ProcurementVerificationFlow: React.FC<
  ProcurementVerificationFlowProps
> = ({
  invoice,
  lines,
  poSnapshot,
  rateTolerancePercent = 1.5,
  onOpenGlossary,
  onCorrectLine,
  isAuditor = false,
}) => {
  const [viewMode, setViewMode] = useState<"comparison" | "detailed">(
    "comparison",
  );
  const [editingLine, setEditingLine] = useState<InvoiceLine | null>(null);
  const [editQty, setEditQty] = useState<number>(0);
  const [editRate, setEditRate] = useState<number>(0);
  const [editReason, setEditReason] = useState<string>("");
  const [isSubmittingEdit, setIsSubmittingEdit] = useState<boolean>(false);
  const [editError, setEditError] = useState<string | null>(null);

  const startEdit = (line: InvoiceLine) => {
    if (isAuditor || !onCorrectLine) return;
    setEditingLine(line);
    setEditQty(line.quantity);
    setEditRate(line.rate);
    setEditReason("");
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingLine(null);
    setEditError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingLine || !onCorrectLine) return;
    if (editQty <= 0) {
      setEditError("Quantity must be greater than zero.");
      return;
    }
    if (editRate <= 0) {
      setEditError("Unit rate must be greater than zero.");
      return;
    }
    if (!editReason.trim() || editReason.trim().length < 3) {
      setEditError(
        "A specific correction reason (min 3 characters) is required for audit compliance.",
      );
      return;
    }

    try {
      setIsSubmittingEdit(true);
      setEditError(null);
      const lineId =
        editingLine.id || `line_${invoice.id}_${editingLine.line_number}`;
      await onCorrectLine(lineId, {
        billed_quantity: editQty,
        billed_unit_rate: editRate,
        correction_reason: editReason.trim(),
      });
      setEditingLine(null);
    } catch (err: any) {
      setEditError(err.message || "Failed to apply line correction.");
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  const formatINR = (val: number | null | undefined) => {
    if (val === null || val === undefined) return "—";
    if (invoice.currency !== "INR") return "INR equivalent unavailable";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(val);
  };

  const hasPo = Boolean(poSnapshot);
  const poLines = poSnapshot?.lines || [];
  const grn = poSnapshot?.grn;
  const qc = poSnapshot?.qc;

  const correctionRef = useDialogFocus(Boolean(editingLine), cancelEdit);

  return (
    <div className="space-y-4 max-w-full">
      {/* Consolidated Procurement Provenance Reference Bar */}
      <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
        <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
          <div className="flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-200">
            <Layers className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>Procurement Reference Evidence</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <span>Rate Tolerance: ±{rateTolerancePercent.toFixed(2)}% • Qty: 0.00%</span>
            {onOpenGlossary && (
              <button
                type="button"
                onClick={() => onOpenGlossary("Three-Way Match")}
                className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
              >
                Glossary
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-0.5">
          {/* PO Contract */}
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800 shadow-2xs flex flex-col justify-between">
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                <ShoppingCart className="w-3 h-3 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span>PO Contract</span>
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold ${
                hasPo
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
              }`}>
                {hasPo ? "Authorized" : "Missing"}
              </span>
            </div>
            <div className="font-mono text-xs flex justify-between items-baseline gap-2">
              <span className="font-bold text-slate-900 dark:text-white truncate">
                {invoice.po_reference || "NONE"}
              </span>
              <span className="text-[11px] text-slate-500 tabular-nums">
                {hasPo && poSnapshot?.total_authorized_amount ? formatINR(poSnapshot.total_authorized_amount) : "—"}
              </span>
            </div>
          </div>

          {/* Receiving (GRN) */}
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800 shadow-2xs flex flex-col justify-between">
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                <Truck className="w-3 h-3 text-amber-600 dark:text-amber-400 shrink-0" />
                <span>Goods Receipt</span>
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold ${
                grn
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
              }`}>
                {grn ? "Confirmed" : "Not Logged"}
              </span>
            </div>
            <div className="font-mono text-xs flex justify-between items-baseline gap-2">
              <span className="font-bold text-slate-900 dark:text-white truncate">
                {grn?.grn_number || "Unavailable"}
              </span>
              <span className="text-[11px] font-sans text-slate-600 dark:text-slate-300 truncate">
                {grn ? (grn.lines?.[0] ? `${grn.lines[0].accepted_quantity} units` : "Logged") : "No receipt"}
              </span>
            </div>
          </div>

          {/* Quality (QC) */}
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800 shadow-2xs flex flex-col justify-between">
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                <ShieldCheck className="w-3 h-3 text-purple-600 dark:text-purple-400 shrink-0" />
                <span>Quality Inspection</span>
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-semibold ${
                qc && qc.overall_status === "ACCEPTED"
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
              }`}>
                {qc ? (qc.overall_status === "ACCEPTED" ? "Accepted" : qc.overall_status) : "Not Filed"}
              </span>
            </div>
            <div className="font-mono text-xs flex justify-between items-baseline gap-2">
              <span className="font-bold text-slate-900 dark:text-white truncate">
                {qc?.qc_certificate_number || "Unavailable"}
              </span>
              <span className="text-[11px] font-sans text-slate-600 dark:text-slate-300 truncate">
                {qc ? (qc.overall_status === "ACCEPTED" ? "Passed" : qc.overall_status) : "No inspection"}
              </span>
            </div>
          </div>
        </div>
      </div>

            {/* Line-Level Comparison: Billed vs Authoritative PO */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Line-by-Line Procurement Match ({lines?.length || 0} Billed Lines)
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Contract rate variance tolerance enforced at ±
              {rateTolerancePercent.toFixed(2)}%. Quantity variance tolerance is
              0.00%.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-center">
            {poSnapshot && (
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200/80 dark:border-slate-700/80">
                PO: {poSnapshot.po_number}
              </span>
            )}
            {/* View Mode Toggle: Comparison (Compact, fits split pane) vs Detailed (9-col ledger) */}
            <div className="inline-flex flex-wrap items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[10px] font-medium">
              <button
                type="button"
                onClick={() => setViewMode("comparison")}
                aria-pressed={viewMode === "comparison"}
                className={`recon-mode-button px-2 py-0.5 rounded transition-all flex items-center gap-1 ${
                  viewMode === "comparison"
                    ? "bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
                title="Consolidated Billed vs PO Comparison layout (Fits desktop pane without clipping)"
              >
                <Layers className="w-3 h-3" />
                <span>Comparison</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("detailed")}
                aria-pressed={viewMode === "detailed"}
                className={`recon-mode-button px-2 py-0.5 rounded transition-all flex items-center gap-1 ${
                  viewMode === "detailed"
                    ? "bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-300 shadow-2xs font-semibold"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
                title="Full 9-Column Ledger layout with horizontal scroll"
              >
                <Columns className="w-3 h-3" />
                <span>9-column ledger</span>
              </button>
            </div>
          </div>
        </div>

        
        {!lines || lines.length === 0 ? (
          <div className="text-center py-6 text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
            No line items were returned. Inspect the original document and
            recorded processing status; a ledger cannot be shown without line
            items.
          </div>
        ) : (
          <>
            {/* A. MOBILE STACKED PRESENTATION (< 768px) */}
            <div
              className={`md:hidden space-y-3 ${viewMode === "detailed" ? "hidden" : ""}`}
            >
              {lines.map((l: InvoiceLine, idx: number) => {
                const matchingPoLine =
                  poLines.find((pl) => pl.line_number === l.line_number) ||
                  poLines[idx];
                const hasPoLine = Boolean(matchingPoLine);

                let rateVariancePercent: number | null = null;
                let rateDeltaINR: number | null = null;
                let isRateFailed = false;
                let isQtyFailed = false;

                if (hasPoLine && matchingPoLine) {
                  const poRate = matchingPoLine.contracted_unit_rate;
                  if (poRate > 0) {
                    rateVariancePercent = ((l.rate - poRate) / poRate) * 100;
                    rateDeltaINR = (l.rate - poRate) * l.quantity;
                    if (Math.abs(rateVariancePercent) > rateTolerancePercent) {
                      isRateFailed = true;
                    }
                  }
                  if (l.quantity > matchingPoLine.authorized_quantity) {
                    isQtyFailed = true;
                  }
                }

                const isLineMatch = hasPoLine && !isRateFailed && !isQtyFailed;

                return (
                  <div
                    key={l.line_number}
                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-2.5"
                  >
                    {/* Card Header: Line #, Description, Verdict */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-[10px] font-mono text-slate-500 font-bold shrink-0">
                            #{l.line_number}
                          </span>
                          <h5 className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                            {l.description}
                          </h5>
                        </div>
                        {hasPoLine && matchingPoLine ? (
                          <p className="text-[10px] text-slate-500 font-mono mt-0.5 truncate">
                            <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                              PO Match:
                            </span>{" "}
                            {matchingPoLine.description}
                            {matchingPoLine.item_code && (
                              <span className="text-slate-400">
                                {" "}
                                ({matchingPoLine.item_code})
                              </span>
                            )}
                          </p>
                        ) : (
                          <p className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                            Unmatched against PO schedule
                          </p>
                        )}
                      </div>
                      <div className="shrink-0">
                        {!hasPo ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                            No PO
                          </span>
                        ) : isLineMatch ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Pass
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1">
                            <XCircle className="w-3 h-3 text-rose-600" />
                            Fail
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 2x2 Metric Comparison Grid */}
                    <div className="grid grid-cols-2 gap-2 p-2.5 rounded-md bg-slate-50 dark:bg-slate-950/60 border border-slate-100 dark:border-slate-800 font-mono text-[11px]">
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">
                          Billed / PO Qty
                        </span>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span
                            className={`font-bold tabular-nums ${isQtyFailed ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}
                          >
                            {l.quantity}
                          </span>
                          <span className="text-[10px] text-slate-400 font-normal">
                            /{" "}
                            {hasPoLine && matchingPoLine
                              ? matchingPoLine.authorized_quantity
                              : "—"}
                          </span>
                        </div>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">
                          Billed / PO Rate
                        </span>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span
                            className={`font-bold tabular-nums ${isRateFailed ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}
                          >
                            {formatINR(l.rate)}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400 block font-normal">
                          PO:{" "}
                          {hasPoLine && matchingPoLine
                            ? formatINR(matchingPoLine.contracted_unit_rate)
                            : "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">
                          Rate Variance
                        </span>
                        {rateVariancePercent !== null ? (
                          <div className="mt-0.5 space-y-0.5">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold inline-block ${
                                isRateFailed
                                  ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                                  : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                              }`}
                            >
                              {rateVariancePercent > 0
                                ? `+${rateVariancePercent.toFixed(2)}%`
                                : `${rateVariancePercent.toFixed(2)}%`}
                            </span>
                            {rateDeltaINR !== null &&
                              Math.abs(rateDeltaINR) > 0.01 && (
                                <div
                                  className={`text-[10px] font-mono ${isRateFailed ? "text-rose-600 dark:text-rose-400 font-semibold" : "text-slate-400"}`}
                                >
                                  {rateDeltaINR > 0
                                    ? `+${formatINR(rateDeltaINR)}`
                                    : formatINR(rateDeltaINR)}
                                </div>
                              )}
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-sans block">
                          Billed Total
                        </span>
                        <span className="font-bold text-slate-900 dark:text-white tabular-nums text-xs mt-0.5 block">
                          {formatINR(l.total)}
                        </span>
                      </div>
                    </div>

                    {/* Action if failed */}
                    {isRateFailed && rateDeltaINR && rateDeltaINR > 0 && (
                      <div className="px-2.5 py-1.5 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/40 text-[10px] text-rose-700 dark:text-rose-300 font-mono flex items-center justify-between">
                        <span className="font-sans font-medium">
                          Resolution Action:
                        </span>
                        <span className="font-bold">
                          Debit Note ({formatINR(rateDeltaINR)})
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* B. DESKTOP & TABLET: REBALANCED COMPARISON VIEW (DEFAULT) */}
            {viewMode === "comparison" && (
              <div className="hidden md:block border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden shadow-2xs bg-white dark:bg-slate-900 max-w-full">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[10.5px] select-none">
                    <tr>
                      <th className="py-2 px-2 w-6 text-center font-semibold text-slate-400">
                        #
                      </th>
                      <th className="py-2 px-2 font-semibold">
                        Item & PO Match
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Quantity</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">
                          Billed · PO
                        </div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Unit Rate</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">
                          Billed · PO
                        </div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div className="text-slate-900 dark:text-white font-bold">
                          Variance
                        </div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">
                          % · Δ INR
                        </div>
                      </th>
                      <th className="py-2 px-2 text-right font-semibold">
                        <div>Total</div>
                        <div className="text-[9px] font-normal text-slate-400 font-mono">
                          Billed
                        </div>
                      </th>
                      <th className="py-2 px-2 text-center font-semibold">
                        <div>Verdict</div>
                        <div className="text-[9px] font-normal text-slate-400">
                          Status & Action
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono text-[11px]">
                    {lines.map((l: InvoiceLine, idx: number) => {
                      const matchingPoLine =
                        poLines.find(
                          (pl) => pl.line_number === l.line_number,
                        ) || poLines[idx];
                      const hasPoLine = Boolean(matchingPoLine);

                      let rateVariancePercent: number | null = null;
                      let rateDeltaINR: number | null = null;
                      let isRateFailed = false;
                      let isQtyFailed = false;

                      if (hasPoLine && matchingPoLine) {
                        const poRate = matchingPoLine.contracted_unit_rate;
                        if (poRate > 0) {
                          rateVariancePercent =
                            ((l.rate - poRate) / poRate) * 100;
                          rateDeltaINR = (l.rate - poRate) * l.quantity;
                          if (
                            Math.abs(rateVariancePercent) > rateTolerancePercent
                          ) {
                            isRateFailed = true;
                          }
                        }
                        if (l.quantity > matchingPoLine.authorized_quantity) {
                          isQtyFailed = true;
                        }
                      }

                      const isLineMatch =
                        hasPoLine && !isRateFailed && !isQtyFailed;

                      return (
                        <tr
                          key={l.line_number}
                          className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                        >
                          {/* 1. Line Number */}
                          <td className="py-2 px-2 text-center text-slate-400 font-mono text-xs">
                            {l.line_number}
                          </td>

                          {/* 2. Item & PO Reference */}
                          <td className="py-2 px-2 font-sans text-slate-800 dark:text-slate-200 min-w-0">
                            <div className="font-semibold text-xs leading-snug line-clamp-2">
                              {l.description}
                            </div>
                            {hasPoLine && matchingPoLine ? (
                              <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex flex-wrap items-center gap-1">
                                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                                  PO Match:
                                </span>
                                <span className="text-slate-700 dark:text-slate-300">
                                  {matchingPoLine.description}
                                </span>
                                {matchingPoLine.item_code && (
                                  <span className="text-slate-400">
                                    ({matchingPoLine.item_code})
                                  </span>
                                )}
                              </div>
                            ) : (
                              <div className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                                Unmatched against PO schedule
                              </div>
                            )}
                          </td>

                          {/* 3. Quantity (Billed / PO) */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1">
                              <span
                                className={`font-bold text-xs ${isQtyFailed ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}
                              >
                                {l.quantity}
                              </span>
                              {onCorrectLine && !isAuditor && (
                                <button
                                  type="button"
                                  onClick={() => startEdit(l)}
                                  className="p-0.5 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                                  title="Correct line quantity or rate"
                                >
                                  <Edit3 className="w-2.5 h-2.5" />
                                </button>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-400 font-sans">
                              PO:{" "}
                              {hasPoLine && matchingPoLine
                                ? matchingPoLine.authorized_quantity
                                : "—"}
                            </div>
                          </td>

                          {/* 4. Unit Rate (Billed / PO) */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1">
                              <span
                                className={`font-bold text-xs ${isRateFailed ? "text-rose-600 dark:text-rose-400" : "text-slate-900 dark:text-white"}`}
                              >
                                {formatINR(l.rate)}
                              </span>
                              {l.is_corrected && (
                                <span
                                  className="text-[9px] bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 px-1 py-0.2 rounded font-sans"
                                  title={`Corrected (was ₹${l.previous_unit_rate})`}
                                >
                                  Corrected
                                </span>
                              )}
                              {onCorrectLine && !isAuditor && (
                                <button
                                  type="button"
                                  onClick={() => startEdit(l)}
                                  className="p-0.5 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                                  title="Correct line rate or quantity"
                                >
                                  <Edit3 className="w-2.5 h-2.5" />
                                </button>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-400 font-sans">
                              PO:{" "}
                              {hasPoLine && matchingPoLine
                                ? formatINR(matchingPoLine.contracted_unit_rate)
                                : "—"}
                            </div>
                          </td>

                          {/* 5. Rate Variance: Bold % Pill & INR Delta */}
                          <td className="py-2 px-2 text-right tabular-nums whitespace-nowrap">
                            {rateVariancePercent !== null ? (
                              <div className="inline-flex flex-col items-end gap-0.5">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-tight inline-block ${
                                    isRateFailed
                                      ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                  }`}
                                >
                                  {rateVariancePercent > 0
                                    ? `+${rateVariancePercent.toFixed(2)}%`
                                    : `${rateVariancePercent.toFixed(2)}%`}
                                </span>
                                {rateDeltaINR !== null &&
                                  Math.abs(rateDeltaINR) > 0.01 && (
                                    <span
                                      className={`text-[10px] font-mono leading-none ${
                                        isRateFailed
                                          ? "text-rose-600 dark:text-rose-400 font-semibold"
                                          : "text-slate-400"
                                      }`}
                                    >
                                      {rateDeltaINR > 0
                                        ? `+${formatINR(rateDeltaINR)}`
                                        : formatINR(rateDeltaINR)}
                                    </span>
                                  )}
                              </div>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>

                          {/* 6. Line Total */}
                          <td className="py-2 px-2 text-right tabular-nums font-bold text-xs text-slate-900 dark:text-white whitespace-nowrap">
                            {formatINR(l.total)}
                          </td>

                          {/* 7. Match Verdict & Action */}
                          <td className="py-2 px-2 text-center min-w-0">
                            {!hasPo ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 inline-block whitespace-nowrap">
                                No PO
                              </span>
                            ) : isLineMatch ? (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1 whitespace-nowrap">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                                  Pass
                                </span>
                                <span className="text-[9px] text-emerald-700 dark:text-emerald-400 mt-0.5 font-sans whitespace-nowrap">
                                  ±{rateTolerancePercent.toFixed(2)}%
                                </span>
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center gap-0.5">
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1 whitespace-nowrap">
                                  <XCircle className="w-3 h-3 text-rose-600 shrink-0" />
                                  {isRateFailed && isQtyFailed
                                    ? "Rate & Qty Fail"
                                    : isRateFailed
                                      ? "Rate Exceeded"
                                      : "Qty Exceeded"}
                                </span>
                                {isRateFailed &&
                                  rateDeltaINR &&
                                  rateDeltaINR > 0 && (
                                    <span className="text-[9px] text-rose-600 dark:text-rose-400 font-mono font-semibold">
                                      Debit Note: {formatINR(rateDeltaINR)}
                                    </span>
                                  )}
                                {onCorrectLine && !isAuditor && (
                                  <button
                                    type="button"
                                    onClick={() => startEdit(l)}
                                    className="mt-0.5 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:hover:bg-indigo-900 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 transition-colors"
                                  >
                                    Correct Rate
                                  </button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* C. DESKTOP & TABLET: DETAILED 9-COLUMN LEDGER VIEW (OPTIONAL EXPANDED) */}
            {viewMode === "detailed" && (
              <div
                tabIndex={0}
                role="region"
                aria-label="Nine-column invoice ledger; scroll horizontally for all columns"
                className="recon-ledger-scroll block border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto shadow-2xs bg-white dark:bg-slate-900 max-w-full"
              >
                <table className="w-full text-left text-xs min-w-[700px] border-collapse">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 text-[11px] select-none">
                    <tr>
                      <th className="py-2.5 px-2 w-6 text-center font-semibold text-slate-400">
                        #
                      </th>
                      <th className="py-2.5 px-2.5 min-w-[120px] font-semibold">
                        Billed Item & PO Reference
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">
                        Billed Qty
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">
                        PO Qty
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">
                        Billed Rate
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">
                        PO Rate
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap text-slate-900 dark:text-white font-bold">
                        Rate Variance
                      </th>
                      <th className="py-2.5 px-2 text-right font-semibold whitespace-nowrap">
                        Line Total
                      </th>
                      <th className="py-2.5 px-2.5 text-center font-semibold min-w-[110px]">
                        Match Verdict & Action
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono text-[11px]">
                    {lines.map((l: InvoiceLine, idx: number) => {
                      const matchingPoLine =
                        poLines.find(
                          (pl) => pl.line_number === l.line_number,
                        ) || poLines[idx];
                      const hasPoLine = Boolean(matchingPoLine);

                      let rateVariancePercent: number | null = null;
                      let rateDeltaINR: number | null = null;
                      let isRateFailed = false;
                      let isQtyFailed = false;

                      if (hasPoLine && matchingPoLine) {
                        const poRate = matchingPoLine.contracted_unit_rate;
                        if (poRate > 0) {
                          rateVariancePercent =
                            ((l.rate - poRate) / poRate) * 100;
                          rateDeltaINR = (l.rate - poRate) * l.quantity;
                          if (
                            Math.abs(rateVariancePercent) > rateTolerancePercent
                          ) {
                            isRateFailed = true;
                          }
                        }
                        if (l.quantity > matchingPoLine.authorized_quantity) {
                          isQtyFailed = true;
                        }
                      }

                      const isLineMatch =
                        hasPoLine && !isRateFailed && !isQtyFailed;

                      return (
                        <tr
                          key={l.line_number}
                          className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                        >
                          <td className="py-2.5 px-2 text-center text-slate-400 font-mono text-xs">
                            {l.line_number}
                          </td>
                          <td className="py-2.5 px-2.5 font-sans text-slate-800 dark:text-slate-200">
                            <div className="font-semibold text-xs leading-snug">
                              {l.description}
                            </div>
                            {hasPoLine && matchingPoLine ? (
                              <div className="text-[10px] text-slate-500 font-mono mt-0.5 flex flex-wrap items-center gap-1">
                                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">
                                  Matched:
                                </span>
                                <span>{matchingPoLine.description}</span>
                                {matchingPoLine.item_code && (
                                  <span className="text-slate-400">
                                    ({matchingPoLine.item_code})
                                  </span>
                                )}
                              </div>
                            ) : (
                              <div className="text-[10px] text-amber-600 dark:text-amber-400 font-sans mt-0.5">
                                Unmatched against PO schedule
                              </div>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                            {l.quantity}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-500">
                            {hasPoLine && matchingPoLine
                              ? matchingPoLine.authorized_quantity
                              : "—"}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-900 dark:text-white font-semibold">
                            {formatINR(l.rate)}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums text-slate-500">
                            {hasPoLine && matchingPoLine
                              ? formatINR(matchingPoLine.contracted_unit_rate)
                              : "—"}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums">
                            {rateVariancePercent !== null ? (
                              <div className="inline-flex flex-col items-end gap-0.5">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    isRateFailed
                                      ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                  }`}
                                >
                                  {rateVariancePercent > 0
                                    ? `+${rateVariancePercent.toFixed(2)}%`
                                    : `${rateVariancePercent.toFixed(2)}%`}
                                </span>
                                {rateDeltaINR !== null &&
                                  Math.abs(rateDeltaINR) > 0.01 && (
                                    <span
                                      className={`text-[10px] font-mono ${
                                        isRateFailed
                                          ? "text-rose-600 dark:text-rose-400 font-semibold"
                                          : "text-slate-400"
                                      }`}
                                    >
                                      {rateDeltaINR > 0
                                        ? `+${formatINR(rateDeltaINR)}`
                                        : formatINR(rateDeltaINR)}
                                    </span>
                                  )}
                              </div>
                            ) : (
                              <span className="text-slate-400">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-right tabular-nums font-bold text-slate-900 dark:text-white">
                            {formatINR(l.total)}
                          </td>
                          <td className="py-2.5 px-2.5 text-center">
                            {!hasPo ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-sans font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                                No PO Record
                              </span>
                            ) : isLineMatch ? (
                              <div className="inline-flex flex-col items-center">
                                <span className="px-2 py-0.5 rounded text-[10px] font-sans font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 inline-flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                  Pass
                                </span>
                                <span className="text-[9px] text-emerald-700 dark:text-emerald-400 mt-0.5 font-sans">
                                  Within ±{rateTolerancePercent.toFixed(2)}%
                                </span>
                              </div>
                            ) : (
                              <div className="inline-flex flex-col items-center gap-0.5">
                                <span className="px-2 py-0.5 rounded text-[10px] font-sans font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 inline-flex items-center gap-1">
                                  <XCircle className="w-3 h-3 text-rose-600" />
                                  {isRateFailed && isQtyFailed
                                    ? "Rate & Qty Exceeded"
                                    : isRateFailed
                                      ? "Rate Exceeded"
                                      : "Qty Exceeded"}
                                </span>
                                {isRateFailed &&
                                  rateDeltaINR &&
                                  rateDeltaINR > 0 && (
                                    <span className="text-[9px] text-rose-600 dark:text-rose-400 font-mono font-semibold">
                                      Debit Note: {formatINR(rateDeltaINR)}
                                    </span>
                                  )}
                                {onCorrectLine && !isAuditor && (
                                  <button
                                    type="button"
                                    onClick={() => startEdit(l)}
                                    className="mt-0.5 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:hover:bg-indigo-900 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 transition-colors"
                                  >
                                    Correct Rate
                                  </button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Stage A1 (OPP-01): Audited In-Place Line Correction Dialog */}
      {editingLine && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div
            ref={correctionRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="Correct an extracted invoice line"
            className="product-dialog correction-dialog bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl max-w-lg w-full p-5 space-y-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>
                    Audited Line-Item Correction — #{editingLine.line_number}
                  </span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-1">
                  {editingLine.description}
                </p>
              </div>
              <button
                type="button"
                aria-label="Cancel line correction"
                onClick={cancelEdit}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-lg bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-900/40 text-xs text-sky-900 dark:text-sky-300">
              <p>
                <strong>Correction:</strong> Change a value only when the source
                document supports it. Saving records your reason and
                re-evaluates the checks; it does not approve the invoice.
              </p>
            </div>

            {editError && (
              <div
                role="alert"
                className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2"
              >
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-medium mb-1">
                  Billed Quantity
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.0001"
                  aria-label="Billed quantity"
                  value={editQty}
                  onChange={(e) => setEditQty(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-medium mb-1">
                  Billed Unit Rate (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  aria-label="Billed unit rate in rupees"
                  value={editRate}
                  onChange={(e) => setEditRate(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-slate-900 dark:text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="text-xs">
              <label className="block text-slate-600 dark:text-slate-400 font-medium mb-1">
                Mandatory Audit Justification / Reason{" "}
                <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={2}
                aria-label="Reason for the line correction (required)"
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                placeholder="e.g., OCR misread decimal placement on unit rate (was 14500.00, corrected to contracted 13900.00)"
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg p-2.5 text-slate-900 dark:text-white text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                aria-label="Cancel line correction"
                onClick={cancelEdit}
                disabled={isSubmittingEdit}
                className="px-3.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={isSubmittingEdit}
                className="recon-submit inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs disabled:opacity-50"
              >
                <Save className="w-3.5 h-3.5" />
                <span>
                  {isSubmittingEdit
                    ? "Re-evaluating Gates..."
                    : "Save & Re-evaluate"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
