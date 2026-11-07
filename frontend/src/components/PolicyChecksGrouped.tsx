import React from "react";
import { checkResultKind, summarizeCheckResults } from "../utils/checkResults";
import { HelpCircle } from "lucide-react";
import { Badge } from "./ui";

export interface GateExplanation {
  gateName: string;
  questionGroup: "A" | "B" | "C";
  groupTitle: string;
  whatIsChecked: string;
  whyNeeded: string;
  passMeaning: string;
  failMeaning: string;
  actionOnFail: string;
}

export const GATE_KNOWLEDGE_BASE: Record<string, GateExplanation> = {
  "Vendor Identity Registered": {
    gateName: "Vendor Identity Registered",
    questionGroup: "A",
    groupTitle: "A. Is this a legitimate, new invoice?",
    whatIsChecked:
      "Validates that the supplier GSTIN/PAN exists in the authorized Vendor Master with active commercial status.",
    whyNeeded:
      "Prevents fraud, unauthorized purchases, and payments to fake shell companies.",
    passMeaning:
      "Supplier identity is verified in the approved vendor registry.",
    failMeaning:
      "Supplier GSTIN is unrecognized, unverified, or not found in vendor master records.",
    actionOnFail:
      "Verify supplier registration details or request formal vendor onboarding before proceeding.",
  },
  "Duplicate Invoice Check": {
    gateName: "Duplicate Invoice Check",
    questionGroup: "A",
    groupTitle: "A. Is this a legitimate, new invoice?",
    whatIsChecked:
      "Scans the organization database for prior invoices sharing the same invoice number, vendor GSTIN, or SHA-256 fingerprint.",
    whyNeeded:
      "Prevents the company from paying the same bill twice due to re-invoicing or duplicate mail attachments.",
    passMeaning:
      "This is a unique, first-time invoice submission with zero historical collisions.",
    failMeaning:
      "An invoice with the same reference number or document fingerprint was previously registered or paid.",
    actionOnFail:
      "Investigate the prior invoice in the archive. If confirmed duplicate, reject or quarantine.",
  },
  "PO Authorization Valid": {
    gateName: "PO Authorization Valid",
    questionGroup: "B",
    groupTitle: "B. Was this actually ordered and received?",
    whatIsChecked:
      "Cross-checks the Purchase Order reference number against authorized ERP procurement contracts.",
    whyNeeded:
      "Ensures that company funds are only disbursed for purchases formally authorized by procurement managers.",
    passMeaning:
      "Purchase order exists, is currently open/active, and matches the billing entity.",
    failMeaning:
      "The PO number is missing, closed, canceled, or does not exist in procurement snapshot records.",
    actionOnFail:
      "Confirm valid PO reference with the purchasing agent or place the invoice on Hold for Evidence.",
  },
  "GRN Receipt Confirmed": {
    gateName: "GRN Receipt Confirmed",
    questionGroup: "B",
    groupTitle: "B. Was this actually ordered and received?",
    whatIsChecked:
      "Verifies warehouse receiving logs (Goods Receipt Note) confirming the items physically arrived at the facility.",
    whyNeeded:
      "Prevents paying for goods that are still in transit, back-ordered, lost, or never shipped.",
    passMeaning:
      "Warehouse receiving dock has recorded physical arrival and confirmed accepted quantities.",
    failMeaning:
      "No matching Goods Receipt Note (GRN) found in warehouse records for this PO and shipment.",
    actionOnFail:
      "Confirm physical delivery status with the warehouse dock or place the invoice on Hold for Evidence.",
  },
  "QC Inspection Accepted": {
    gateName: "QC Inspection Accepted",
    questionGroup: "B",
    groupTitle: "B. Was this actually ordered and received?",
    whatIsChecked:
      "Checks the technical quality inspection certificate from warehouse QA engineers for received materials.",
    whyNeeded:
      "Protects operations from paying for defective, damaged, or non-compliant parts that were rejected at inspection.",
    passMeaning:
      "Quality control inspectors have signed off and accepted the material batch as compliant.",
    failMeaning:
      "Goods failed technical inspection or the QC release certificate has not been filed.",
    actionOnFail:
      "Request QC release certificate from warehouse QA or request a supplier credit note/debit note.",
  },
  "PO Price & Quantity Tolerance": {
    gateName: "PO Price & Quantity Tolerance",
    questionGroup: "B",
    groupTitle: "B. Was this actually ordered and received?",
    whatIsChecked:
      "Line-by-line comparison enforcing 0.00% quantity variance and contracted unit rate tolerance (±1.50%).",
    whyNeeded:
      "Prevents commercial price creep, unauthorized rate hikes, and billing for excess quantities beyond PO limits.",
    passMeaning:
      "Billed unit rate and quantity strictly align with the contracted PO terms within permitted tolerance.",
    failMeaning:
      "Billed rate exceeds PO contract rate by more than ±1.50%, or billed quantity exceeds authorized order.",
    actionOnFail:
      "Contact supplier for an amended invoice or credit note, or raise an internal debit note.",
  },
  "GST Arithmetic Reconciled": {
    gateName: "GST Arithmetic Reconciled",
    questionGroup: "C",
    groupTitle: "C. Are the financial and tax details correct?",
    whatIsChecked:
      "Validates line-item subtotal addition, applicable GST rates (CGST/SGST/IGST), rounding (within ₹20.00), and final net total.",
    whyNeeded:
      "Helps identify arithmetic and tax discrepancies that need review before internal sign-off.",
    passMeaning:
      "Document mathematical arithmetic and statutory tax schedules reconcile perfectly.",
    failMeaning:
      "Line items do not add up to taxable subtotal, or tax computation deviates from statutory percentages.",
    actionOnFail:
      "Request a revised tax invoice with mathematically reconciled tax schedules from the supplier.",
  },
};

interface PolicyChecksGroupedProps {
  matchGates: any[];
  onOpenGlossary?: (term?: string) => void;
}

export const PolicyChecksGrouped: React.FC<PolicyChecksGroupedProps> = ({
  matchGates,
  onOpenGlossary,
}) => {
  const groups = [
    {
      title: "Supplier identity & duplicates",
      names: ["Vendor Identity Registered", "Duplicate Invoice Check"],
    },
    {
      title: "Orders, receipts & inspection",
      names: [
        "PO Authorization Valid",
        "GRN Receipt Confirmed",
        "QC Inspection Accepted",
        "PO Price & Quantity Tolerance",
      ],
    },
    { title: "Amounts & tax", names: ["GST Arithmetic Reconciled"] },
  ];
  const known = groups.flatMap((group) => group.names);
  groups.push({
    title: "Other returned checks",
    names: matchGates
      .filter((gate) => !known.includes(gate.gate_name))
      .map((gate) => gate.gate_name),
  });
  const tone = (status: unknown) =>
    checkResultKind(status) === "passed"
      ? "success"
      : checkResultKind(status) === "failed"
        ? "error"
        : "neutral";
  const anchor = (index: number) => `invoice-policy-check-${index}`;
  return (
    <div className="checks-report">
      <header className="checks-report-heading">
        <h3>What was checked, and what happened?</h3>
        <p role="status">{summarizeCheckResults(matchGates)}</p>
        <p>
          Each check shows its purpose, why it matters and the result returned
          for this invoice. Unknown, unavailable and not evaluated results do
          not mean passed.
        </p>
      </header>
      {matchGates.length === 0 ? (
        <p>
          No check results were returned. Inspect the original document and
          recorded processing status.
        </p>
      ) : (
        <nav aria-label="Check results overview" className="checks-overview">
          {matchGates.map((gate, index) => (
            <a key={index} href={`#${anchor(index)}`}>
              <span>
                {gate.gate_name || `Check ${gate.gate_number ?? index + 1}`}
              </span>
              <Badge tone={tone(gate.status)}>
                {checkResultKind(gate.status)}
              </Badge>
            </a>
          ))}
        </nav>
      )}
      {groups.map((group) => {
        const gates = matchGates
          .map((gate, index) => ({ gate, index }))
          .filter(({ gate }) => group.names.includes(gate.gate_name));
        if (!gates.length) return null;
        return (
          <section key={group.title} className="checks-group">
            <div className="checks-group-heading">
              <h3>{group.title}</h3>
              <p>{summarizeCheckResults(gates.map(({ gate }) => gate))}</p>
            </div>
            {gates.map(({ gate, index }) => {
              const kb = GATE_KNOWLEDGE_BASE[gate.gate_name];
              const result = checkResultKind(gate.status);
              return (
                <article
                  id={anchor(index)}
                  key={index}
                  className="check-explanation"
                >
                  <header>
                    <h4>
                      {gate.gate_number != null && (
                        <span>Check {gate.gate_number}: </span>
                      )}
                      {gate.gate_name || "Unnamed check"}
                    </h4>
                    <Badge tone={tone(gate.status)}>{result}</Badge>
                  </header>
                  <dl className="check-purpose">
                    <div>
                      <dt>What this check examines</dt>
                      <dd>
                        {kb?.whatIsChecked ||
                          "No explanation is available for this returned check. Its recorded result is shown below."}
                      </dd>
                    </div>
                    <div>
                      <dt>Why it matters</dt>
                      <dd>
                        {kb?.whyNeeded ||
                          "No purpose description was provided for this check."}
                      </dd>
                    </div>
                  </dl>
                  <div className="check-recorded-result">
                    <h5>Result for this invoice: {result}</h5>
                    <p>{gate.notes || "No result explanation was returned."}</p>
                    {gate.evidence_source_id && (
                      <p className="check-evidence">
                        <strong>Evidence reference:</strong>{" "}
                        <code>{gate.evidence_source_id}</code>
                      </p>
                    )}
                  </div>
                  {result === "failed" && kb && (
                    <p className="check-follow-up">
                      <strong>Suggested follow-up:</strong> {kb.actionOnFail}
                    </p>
                  )}
                  {kb && (
                    <details className="check-definitions">
                      <summary>What passed and failed mean</summary>
                      <dl>
                        <div>
                          <dt>What PASS means</dt>
                          <dd>{kb.passMeaning}</dd>
                        </div>
                        <div>
                          <dt>What FAIL means</dt>
                          <dd>{kb.failMeaning}</dd>
                        </div>
                      </dl>
                      <p>
                        These definitions explain the check; the recorded result
                        and notes above describe this invoice.
                      </p>
                    </details>
                  )}
                  {onOpenGlossary && kb && (
                    <button
                      type="button"
                      className="check-glossary"
                      onClick={() => onOpenGlossary(gate.gate_name)}
                    >
                      <HelpCircle size={15} aria-hidden="true" /> Explain terms
                      in glossary
                    </button>
                  )}
                </article>
              );
            })}
          </section>
        );
      })}
    </div>
  );
};
