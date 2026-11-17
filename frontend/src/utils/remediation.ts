import type { InvoiceDetailInvoice, MatchGateItem } from "../types";

export function getRemediation(gate: MatchGateItem, invoice: InvoiceDetailInvoice): string {
  if (gate.status !== "FAIL") return "Check the recorded status and source documents before proceeding.";
  const num = gate.gate_number;
  const name = (gate.gate_name || "").toLowerCase();

  if (num === 1 || name.includes("vendor")) {
    return "Verify vendor legal identity and GST credentials in ERP master vendor ledger.";
  }
  if (num === 2 || name.includes("po auth")) {
    return invoice.po_reference
      ? "Check the purchase order reference, authorization, and recorded gate evidence."
      : "Non-PO invoice: Obtain departmental approval or register an approved PO.";
  }
  if (num === 3 || name.includes("grn") || name.includes("goods receipt")) {
    return "Check warehouse receiving records or wait for Goods Receipt Note (GRN) posting.";
  }
  if (num === 4 || name.includes("qc") || name.includes("quality")) {
    return "Review the quality inspection record and resolve any recorded hold.";
  }
  if (num === 5 || name.includes("gst") || name.includes("tax")) {
    return "Tax calculation mismatch. Reconcile GST percentage, taxable value, and line sums.";
  }
  if (num === 6 || name.includes("tolerance") || name.includes("price")) {
    return "Review the recorded price or quantity variance against the order and receipt.";
  }
  if (num === 7 || name.includes("duplicate")) {
    return "Potential duplicate document. Compare voucher history and SHA-256 fingerprint in audit ledger.";
  }
  return "Review the recorded safeguard reason and compare available fields with the source document.";
}

