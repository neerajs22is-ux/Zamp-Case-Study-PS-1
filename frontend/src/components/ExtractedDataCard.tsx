import React, { useState } from "react";
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Layers,
  ChevronDown,
  ChevronUp,
  Hash,
  Building,
  Calendar,
  Receipt,
  Tag,
} from "lucide-react";
import { Card, Badge } from "./ui";
import { formatCurrency } from "../utils/currency";
import type { ExtractedFieldItem, InvoiceLineItem, InvoiceDetailInvoice } from "../types";

interface ExtractedDataCardProps {
  invoice: InvoiceDetailInvoice;
  extractedFields?: ExtractedFieldItem[];
  lines?: InvoiceLineItem[];
  poSnapshot?: any;
}

export const ExtractedDataCard: React.FC<ExtractedDataCardProps> = ({
  invoice,
  extractedFields = [],
  lines = [],
  poSnapshot,
}) => {
  const [showAllLines, setShowAllLines] = useState(false);
  const formatMoney = (val?: number | null) => formatCurrency(val, invoice.currency || 'INR');

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

  const totalFieldsCount = extractedFields.length;
  const verifiedCount = extractedFields.filter(
    (f) => f.source_page !== null && f.value && f.value !== "UNKNOWN"
  ).length;

  const hasLineItems = lines && lines.length > 0;
  const displayLines = showAllLines ? lines : lines.slice(0, 3);

  return (
    <Card className="border border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 rounded-xl overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="p-3 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0">
            <FileText className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-100 truncate">
              Extracted Document Data
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <Badge tone={verifiedCount > 0 ? "success" : "neutral"} size="sm">
            {verifiedCount > 0 ? `${verifiedCount}/${totalFieldsCount} Grounded` : "Unverified"}
          </Badge>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="p-3.5 sm:p-4 space-y-4 flex-1">
        {/* Core Financial & Commercial Fields Grid */}
        <div className="grid grid-cols-2 gap-2.5">
          {/* Supplier Name */}
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 col-span-2">
            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Building className="w-3 h-3 text-slate-400" />
                Supplier
              </span>
              {supplierField?.verified ? (
                <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-0.5">
                  <CheckCircle2 className="w-2.5 h-2.5" /> P.{supplierField.page}
                </span>
              ) : (
                <span className="text-[9.5px] text-amber-600 dark:text-amber-400 font-medium">
                  Unverified
                </span>
              )}
            </div>
            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate" title={supplierField?.value}>
              {supplierField?.value || <span className="text-slate-400 font-normal italic">Not found</span>}
            </p>
          </div>

          {/* Supplier GSTIN */}
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Hash className="w-3 h-3 text-slate-400" />
                Supplier GSTIN
              </span>
              {gstinField?.verified ? (
                <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-0.5">
                  <CheckCircle2 className="w-2.5 h-2.5" /> Verified
                </span>
              ) : (
                <span className="text-[9.5px] text-slate-400">Missing</span>
              )}
            </div>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate" title={gstinField?.value}>
              {gstinField?.value || <span className="text-slate-400 font-normal italic">Missing</span>}
            </p>
          </div>

          {/* Invoice Number */}
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Receipt className="w-3 h-3 text-slate-400" />
                Invoice #
              </span>
              {invNumberField?.value && invNumberField.value !== "UNKNOWN" ? (
                <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-0.5">
                  <CheckCircle2 className="w-2.5 h-2.5" /> P.{invNumberField.page || 1}
                </span>
              ) : (
                <span className="text-[9.5px] text-rose-500 font-medium flex items-center gap-0.5">
                  <AlertCircle className="w-2.5 h-2.5" /> Absent
                </span>
              )}
            </div>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate" title={invNumberField?.value}>
              {invNumberField?.value && invNumberField.value !== "UNKNOWN" ? (
                invNumberField.value
              ) : (
                <span className="text-rose-500 dark:text-rose-400 font-medium">UNKNOWN</span>
              )}
            </p>
          </div>

          {/* Invoice Date */}
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" />
                Invoice Date
              </span>
              {dateField?.verified && (
                <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400 font-medium">P.{dateField.page}</span>
              )}
            </div>
            <p className="text-xs font-mono text-slate-900 dark:text-slate-100 truncate">
              {dateField?.value || <span className="text-slate-400 italic">Not found</span>}
            </p>
          </div>

          {/* PO Reference */}
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Tag className="w-3 h-3 text-slate-400" />
                PO Reference
              </span>
              <span className="text-[9.5px] text-slate-400">
                {poField?.value ? "Billed PO" : "Non-PO"}
              </span>
            </div>
            <p className="text-xs font-mono font-semibold text-slate-900 dark:text-slate-100 truncate">
              {poField?.value || <span className="text-slate-400 font-normal italic">None (Direct)</span>}
            </p>
          </div>


        </div>

        {/* GST & Financial Amounts Summary Card */}
        <div className="p-3 rounded-lg bg-slate-50/80 dark:bg-slate-850/80 border border-slate-200 dark:border-slate-800">
          <div className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center justify-between">
            <span>Taxable & GST Breakdown</span>
            <span className="text-[10px] text-slate-400 font-normal font-sans">
              Indian AP Compliance Engine
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div>
              <span className="text-[10px] text-slate-500 block">Taxable Value</span>
              <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
                {taxableField ? formatMoney(Number(taxableField.value)) : "—"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-500 block">
                {igstField && Number(igstField.value) > 0 ? "IGST (Interstate)" : "CGST + SGST"}
              </span>
              <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
                {totalTaxField ? formatMoney(Number(totalTaxField.value)) : "₹0.00"}
              </span>
            </div>
            <div className="col-span-2 sm:col-span-2 flex items-center justify-between bg-indigo-50/70 dark:bg-indigo-950/40 px-3 py-1.5 rounded-lg border border-indigo-200/80 dark:border-indigo-800/60">
              <div>
                <span className="text-[10px] font-bold uppercase text-indigo-700 dark:text-indigo-300 block">
                  Extracted Grand Total
                </span>
                <span className="text-sm font-mono font-extrabold text-indigo-950 dark:text-indigo-200">
                  {grandTotalField ? formatMoney(Number(grandTotalField.value)) : formatMoney(invoice.total_amount)}
                </span>
              </div>
              <span className="text-[10px] font-medium text-indigo-600 dark:text-indigo-400 bg-white dark:bg-slate-900 px-2 py-0.5 rounded shadow-2xs">
                {grandTotalField?.verified ? "Grounded" : "Unverified"}
              </span>
            </div>
          </div>
        </div>

        {/* Extracted Line Items Section */}
        {hasLineItems ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-slate-400" />
                Extracted Line Items ({lines.length})
              </span>
              {lines.length > 3 && (
                <button
                  type="button"
                  onClick={() => setShowAllLines(!showAllLines)}
                  className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  {showAllLines ? (
                    <>
                      <span>Show less</span>
                      <ChevronUp className="w-3 h-3" />
                    </>
                  ) : (
                    <>
                      <span>View all {lines.length} lines</span>
                      <ChevronDown className="w-3 h-3" />
                    </>
                  )}
                </button>
              )}
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden text-xs">
              <div className="grid grid-cols-12 bg-slate-100 dark:bg-slate-800 px-2.5 py-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <div className="col-span-1">#</div>
                <div className="col-span-6">Description</div>
                <div className="col-span-2 text-right">Qty</div>
                <div className="col-span-3 text-right">Total</div>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-800/80 bg-white dark:bg-slate-900">
                {displayLines.map((line, idx) => (
                  <div key={line.id || idx} className="grid grid-cols-12 px-2.5 py-2 items-center text-slate-800 dark:text-slate-200 text-[11px]">
                    <div className="col-span-1 font-mono text-slate-400 text-[10px]">{line.line_number}</div>
                    <div className="col-span-6 truncate font-medium" title={line.description}>
                      {line.description}
                    </div>
                    <div className="col-span-2 text-right font-mono text-slate-500 text-[10.5px]">
                      {line.billed_quantity || (line as any).quantity || 1}
                    </div>
                    <div className="col-span-3 text-right font-mono font-semibold">
                      {formatMoney(line.billed_line_total ?? (line as any).total ?? 0)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400">
            No itemized line items extracted. Bill total was parsed directly from the summary block.
          </div>
        )}

        {/* Procurement Snapshot References (GRN / QC / Contract) */}
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span>
              PO Status: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.po_number ? poSnapshot.po_number : "No Contract"}</strong>
            </span>
            <span>
              GRN: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.grn_number || "Not on file"}</strong>
            </span>
            <span>
              QC Certificate: <strong className="text-slate-700 dark:text-slate-300">{poSnapshot?.qc_number || "None"}</strong>
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            Tripwire: {verifiedCount >= 5 ? "PASS" : "ATTN_REQUIRED"}
          </span>
        </div>
      </div>
    </Card>
  );
};
