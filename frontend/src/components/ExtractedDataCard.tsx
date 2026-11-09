import React, { useState } from "react";
import {
  FileText,
  CheckCircle2,
} from "lucide-react";
import { Card, Badge } from "./ui";
import { formatCurrency } from "../utils/currency";
import type { ExtractedFieldItem, InvoiceLineItem, InvoiceDetailInvoice, MatchGateItem } from "../types";

interface ExtractedDataCardProps {
  invoice: InvoiceDetailInvoice;
  extractedFields?: ExtractedFieldItem[];
  lines?: InvoiceLineItem[];
  poSnapshot?: any;
  matchGates?: MatchGateItem[];
}

export const ExtractedDataCard: React.FC<ExtractedDataCardProps> = ({
  invoice,
  extractedFields = [],
  lines = [],
  poSnapshot,
  matchGates = [],
}) => {
  const [showAllLines, setShowAllLines] = useState(false);
  const formatMoney = (val?: number | null) => formatCurrency(val, invoice.currency || "INR");

  // Map extracted fields into a lookup dictionary
  const fieldsMap = React.useMemo(() => {
    const map = new Map<string, ExtractedFieldItem>();
    extractedFields.forEach((f) => {
      map.set(f.field_name, f);
    });
    return map;
  }, [extractedFields]);

  // Helper to extract or fallback
  const getField = (name: string, fallbackVal?: string | number | null) => {
    const item = fieldsMap.get(name);
    if (item && item.value !== null && item.value !== undefined && item.value !== "") {
      return {
        value: String(item.value),
        page: item.source_page ?? 1,
        verified: item.source_page !== null && item.value !== "UNKNOWN",
        conflicting: false,
      };
    }
    if (fallbackVal !== null && fallbackVal !== undefined && fallbackVal !== "") {
      return {
        value: String(fallbackVal),
        page: null,
        verified: fallbackVal !== "UNKNOWN" && fallbackVal !== "Unknown",
        conflicting: false,
      };
    }
    return null;
  };

  const supplierField = getField("supplier_name", invoice.vendor_name);
  const gstinField = getField("supplier_gstin", invoice.vendor_gstin);
  const invNumberField = getField("invoice_number", invoice.invoice_number);
  const dateField = getField("invoice_date", invoice.invoice_date);
  const poField = getField("po_reference", invoice.po_reference);
  const taxableField = getField("taxable_value", invoice.subtotal_amount);
  const totalTaxField = getField("total_tax_amount", invoice.tax_amount);
  const igstField = getField("igst_amount");
  const grandTotalField = getField("grand_total", invoice.total_amount);

  // Epoch date check: Never display 1970-01-01
  const rawDate = dateField?.value || invoice.invoice_date;
  const isEpochOrInvalid =
    !rawDate ||
    rawDate === "1970-01-01" ||
    rawDate.startsWith("1970-01-01") ||
    rawDate === "UNKNOWN";
  const displayDate = isEpochOrInvalid ? "Not found" : rawDate;
  const dateVerified = !isEpochOrInvalid && Boolean(dateField?.verified);

  // Grounding Tripwire sync with actual backend match gates
  const extractionGate = matchGates?.find(
    (g) => g.gate_number >= 8 || g.gate_name?.toLowerCase().includes("extraction evidence")
  );
  const groundingFailed =
    extractionGate?.status === "FAIL" ||
    Boolean(invoice.decision_reason?.toLowerCase().includes("grounding tripwire failed"));
  const tripwireStatus = groundingFailed ? "FAILED" : "PASS";

  // Check if invoice total is genuinely unreadable / unextracted
  const isDegradedOrUnavailable =
    (invoice.total_amount === 0 || invoice.total_amount === null || invoice.total_amount === undefined) &&
    (invoice.vendor_name === "Unknown" ||
      invoice.vendor_name === "Unidentified Supplier" ||
      invoice.invoice_number === "UNKNOWN" ||
      !grandTotalField ||
      grandTotalField.value === "UNKNOWN");

  // Financial values formatting: distinguish genuine zero from missing/unverified
  const formatFinancial = (
    field?: { value?: string | number | null; verified?: boolean } | null,
    fallback?: number | null
  ) => {
    if (isDegradedOrUnavailable) {
      return null;
    }
    if (field && field.value !== null && field.value !== undefined && field.value !== "" && field.value !== "UNKNOWN") {
      const num = Number(field.value);
      if (!isNaN(num)) return formatMoney(num);
    }
    if (fallback !== null && fallback !== undefined && !isNaN(Number(fallback))) {
      if (Number(fallback) === 0 && !field?.value) {
        return null; // Don't claim 0 if there's no extracted evidence
      }
      return formatMoney(Number(fallback));
    }
    return null;
  };

  const taxableFormatted = formatFinancial(taxableField, invoice.subtotal_amount);
  const totalTaxFormatted = formatFinancial(totalTaxField, invoice.tax_amount);
  const grandTotalFormatted = isDegradedOrUnavailable ? null : formatFinancial(grandTotalField, invoice.total_amount);

  const totalFieldsCount = extractedFields.length;
  const verifiedCount = extractedFields.filter(
    (f) => f.source_page !== null && f.value && f.value !== "UNKNOWN"
  ).length;

  const hasLineItems = lines && lines.length > 0;
  const displayLines = showAllLines ? lines : lines.slice(0, 3);

  return (
    <Card className="border border-slate-200 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900 rounded-xl overflow-hidden transition-all">
      {/* 1. Header */}
      <div className="px-3.5 py-2.5 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-100 truncate">
            Extracted Document Data
          </h3>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <Badge tone={verifiedCount > 0 ? "success" : "neutral"} size="sm">
            {verifiedCount > 0 ? `${verifiedCount}/${totalFieldsCount || 10} Grounded` : "Unverified"}
          </Badge>
        </div>
      </div>

      {/* 2. Main Content Inspector */}
      <div className="p-3.5 sm:p-4 space-y-3">
        {/* Supplier Header Row */}
        <div className="pb-2.5 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
              Supplier / Vendor
            </span>
            <h4
              className="text-sm font-bold text-slate-900 dark:text-slate-100 truncate"
              title={supplierField?.value}
            >
              {supplierField?.value || (
                <span className="text-slate-400 italic font-normal">Unidentified Supplier</span>
              )}
            </h4>
          </div>

          {supplierField?.verified ? (
            <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
              <CheckCircle2 className="w-2.5 h-2.5" /> P.{supplierField.page || 1}
            </span>
          ) : (
            <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
              Unverified
            </span>
          )}
        </div>

        {/* Dense Key/Value Metadata Grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 py-1 text-xs">
          <div>
            <span className="text-[10.5px] text-slate-500 dark:text-slate-400 block">Supplier GSTIN</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
                {gstinField?.value || <span className="text-slate-400 font-normal italic">Missing</span>}
              </span>
              {gstinField?.verified && <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />}
            </div>
          </div>

          <div>
            <span className="text-[10.5px] text-slate-500 dark:text-slate-400 block">Invoice Number</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
                {invNumberField?.value && invNumberField.value !== "UNKNOWN" ? (
                  invNumberField.value
                ) : (
                  <span className="text-rose-500 font-normal">UNKNOWN</span>
                )}
              </span>
              {invNumberField?.verified && <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />}
            </div>
          </div>

          <div>
            <span className="text-[10.5px] text-slate-500 dark:text-slate-400 block">Invoice Date</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                {isEpochOrInvalid ? (
                  <span className="text-slate-400 font-normal italic">Not found</span>
                ) : (
                  displayDate
                )}
              </span>
              {dateVerified && <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />}
            </div>
          </div>

          <div>
            <span className="text-[10.5px] text-slate-500 dark:text-slate-400 block">PO Reference</span>
            <span className="font-mono font-medium text-slate-800 dark:text-slate-200 block mt-0.5">
              {poField?.value || <span className="text-slate-400 font-normal italic">None (Direct / Non-PO)</span>}
            </span>
          </div>
        </div>

        {/* Dedicated Financial Summary Strip */}
        <div className="py-2.5 px-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 flex flex-wrap sm:flex-nowrap items-center justify-between gap-2.5 sm:gap-3 text-xs overflow-x-auto">
          <div className="min-w-0">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-medium">
              Taxable Value
            </span>
            <span className="font-mono font-bold text-slate-900 dark:text-slate-100 text-xs sm:text-sm">
              {taxableFormatted ?? <span className="text-slate-400 font-normal italic">Unverified</span>}
            </span>
          </div>

          <div className="border-l border-slate-200 dark:border-slate-700 pl-3 min-w-0">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-medium">
              {igstField && Number(igstField.value) > 0 ? "IGST" : "CGST + SGST"}
            </span>
            <span className="font-mono font-bold text-slate-900 dark:text-slate-100 text-xs sm:text-sm">
              {totalTaxFormatted ?? (isDegradedOrUnavailable ? <span className="text-slate-400 font-normal italic">Unverified</span> : formatMoney(0))}
            </span>
          </div>

          <div className="border-l border-slate-200 dark:border-slate-700 pl-3 min-w-0">
            <span className="text-[10px] uppercase tracking-wider text-indigo-600 dark:text-indigo-400 font-bold block">
              Grand Total
            </span>
            <span className="font-mono font-extrabold text-indigo-950 dark:text-indigo-200 text-sm sm:text-base">
              {grandTotalFormatted ?? <span className="text-rose-500 font-normal italic">Unavailable</span>}
            </span>
          </div>
        </div>

        {/* Line Items Table or Small Explanatory State */}
        {hasLineItems ? (
          <div className="space-y-1.5 pt-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[10.5px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Extracted Line Items ({lines.length})
              </span>
              {lines.length > 3 && (
                <button
                  type="button"
                  onClick={() => setShowAllLines(!showAllLines)}
                  className="text-[10.5px] text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                >
                  {showAllLines ? "Show less" : `View all ${lines.length}`}
                </button>
              )}
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto text-[11px]">
              <table className="w-full text-left divide-y divide-slate-100 dark:divide-slate-800">
                <thead className="bg-slate-50 dark:bg-slate-800/80 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <tr>
                    <th className="px-2.5 py-1.5 w-8">#</th>
                    <th className="px-2.5 py-1.5">Description</th>
                    <th className="px-2.5 py-1.5 text-right w-14">Qty</th>
                    <th className="px-2.5 py-1.5 text-right w-28 whitespace-nowrap">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 bg-white dark:bg-slate-900">
                  {displayLines.map((line, idx) => {
                    const lineQty = (line as any).quantity ?? line.billed_quantity ?? 1;
                    const lineTotal = (line as any).total ?? line.billed_line_total ?? 0;
                    return (
                      <tr key={line.id || idx}>
                        <td className="px-2.5 py-1.5 font-mono text-slate-400 text-[10px]">{line.line_number}</td>
                        <td
                          className="px-2.5 py-1.5 font-medium text-slate-800 dark:text-slate-200 truncate max-w-[170px]"
                          title={line.description}
                        >
                          {line.description}
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-right text-slate-500 whitespace-nowrap">
                          {lineQty}
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-right font-semibold text-slate-900 dark:text-slate-100 whitespace-nowrap">
                          {formatMoney(lineTotal)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-slate-400 italic py-1">
            Single-line document: Grand total was parsed directly from the summary invoice block.
          </p>
        )}

        {/* Compact Footer: Procurement References & Grounding Status */}
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[10.5px] text-slate-500 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 truncate">
            <span>
              PO: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.po_number || "None"}</strong>
            </span>
            <span>
              GRN: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.grn?.grn_number || "Not on file"}</strong>
            </span>
            <span>
              QC: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.qc?.status || "None"}</strong>
            </span>
          </div>

          <span
            className={`font-mono text-[10px] font-bold shrink-0 ${
              groundingFailed ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"
            }`}
          >
            Tripwire: {tripwireStatus}
          </span>
        </div>
      </div>
    </Card>
  );
};
