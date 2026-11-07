import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  RefreshCw,
  FileInput,
  FileText,
  Search,
  ListChecks,
  Clock3,
  ChevronDown,
  AlertTriangle,
  History,
  ExternalLink,
} from "lucide-react";
import { api } from "../api/client";
import type {
  AuthenticatedUser,
  DashboardMetrics,
  HealthResponse,
  InboxResponse,
  InvoiceItem,
} from "../types";
import "./DashboardPage.css";

interface DashboardPageProps {
  onNavigate?: (route: string) => void;
  currentUser?: AuthenticatedUser | null;
}
type Exposure = Awaited<ReturnType<typeof api.getDashboardExposure>>;
type ExceptionRecord = Awaited<
  ReturnType<typeof api.getExceptions>
>["items"][number];
type AuditRecord = Awaited<ReturnType<typeof api.getAudit>>["items"][number];
const number = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-IN")
    : "Unavailable";
const money = (value: unknown, currency = "INR") => {
  if (typeof value !== "number" || !Number.isFinite(value))
    return "Amount unavailable";
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${number(value)} ${currency}`;
  }
};
const words = (value?: string | null) =>
  value
    ? value
        .toLowerCase()
        .replace(/_/g, " ")
        .replace(/^./, (c) => c.toUpperCase())
    : "Not reported";
const decisionLabel = (value: string) =>
  ({
    AUTO_APPROVED: "Automatically approved internally",
    MANUALLY_APPROVED: "Approved by a reviewer",
    MATCH_CANDIDATE: "Match found; review required",
    NEEDS_REVIEW: "Review required",
    HOLD_PENDING_EVIDENCE: "Waiting for supporting evidence",
    QUARANTINED: "Set aside for investigation",
    REJECTED: "Rejected",
    ACTION_REQUIRED: "Correction or follow-up needed",
  })[value] || words(value);
const date = (value?: string | null) =>
  value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString("en-IN", {
        year: "numeric",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Time unavailable";
function invoiceState(invoice: InvoiceItem): { text: string; tone: string } {
  if (invoice.stage === "INTERNAL_APPROVAL_COMPLETE")
    return { text: "Internal sign-off complete", tone: "success" };
  if (invoice.decision === "REJECTED")
    return { text: "Rejected", tone: "danger" };
  if (invoice.stage === "PENDING_SECOND_APPROVAL")
    return { text: "Second sign-off needed", tone: "attention" };
  if (invoice.job_status === "FAILED")
    return { text: "Processing failed", tone: "danger" };
  if (invoice.stage === "ACTION_REQUIRED")
    return { text: "Needs attention", tone: "attention" };
  if (invoice.job_status === "QUEUED" || invoice.job_status === "PROCESSING")
    return {
      text:
        invoice.job_status === "QUEUED"
          ? invoice.job_error
            ? "Retry queue reported"
            : "Queue reported at last refresh"
          : "Processing at last refresh",
      tone: "info",
    };
  return { text: words(invoice.stage), tone: "neutral" };
}

export const DashboardPage: React.FC<DashboardPageProps> = (props) => (
  <DashboardContent
    key={JSON.stringify([props.currentUser?.id, props.currentUser?.org_id])}
    {...props}
  />
);

const SOURCES = [
  "Workload",
  "Financial context",
  "Attention queue",
  "Decision history",
  "Invoice history",
  "System status",
];

const DashboardContent: React.FC<DashboardPageProps> = ({
  currentUser,
  onNavigate,
}) => {
  const navigate = useNavigate();
  const go = (route: string) =>
    onNavigate ? onNavigate(route) : navigate(route);
  const followLink = (
    event: React.MouseEvent<HTMLAnchorElement>,
    route: string,
  ) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    event.preventDefault();
    go(route);
  };
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [exposure, setExposure] = useState<Exposure | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionRecord[] | null>(null);
  const [audits, setAudits] = useState<AuditRecord[] | null>(null);
  const [inbox, setInbox] = useState<InboxResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [receivedAt, setReceivedAt] = useState<Record<string, string>>({});
  const [pendingSources, setPendingSources] = useState<string[]>(SOURCES);
  const sequence = useRef(0);
  const load = useCallback(async () => {
    const request = ++sequence.current;
    // Independent reads render as they settle. Slow optional sources cannot hide invoices.
    const read = async <T,>(
      source: string,
      fetcher: () => Promise<T>,
      valid: (value: T) => boolean,
      commit: (value: T) => void,
    ) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        const value = await Promise.race([
          fetcher(),
          new Promise<never>((_, reject) => {
            timer = setTimeout(
              () => reject(new Error("Dashboard source timed out")),
              20000,
            );
          }),
        ]);
        if (request !== sequence.current) return;
        if (!valid(value)) throw new Error("Dashboard source unavailable");
        commit(value);
        setReceivedAt((previous) => ({
          ...previous,
          [source]: new Date().toISOString(),
        }));
        setFailed((previous) => previous.filter((item) => item !== source));
      } catch {
        if (request === sequence.current)
          setFailed((previous) =>
            previous.includes(source) ? previous : [...previous, source],
          );
      } finally {
        clearTimeout(timer);
        if (request === sequence.current)
          setPendingSources((previous) =>
            previous.filter((item) => item !== source),
          );
      }
    };
    await Promise.all([
      read(
        "Workload",
        api.getDashboardMetrics,
        (value) => value.status === "active" && !!value.summary,
        setMetrics,
      ),
      read(
        "Financial context",
        api.getDashboardExposure,
        (value) =>
          !value.statutory_msme_note
            ?.toLowerCase()
            .includes("database not connected"),
        setExposure,
      ),
      read(
        "Attention queue",
        api.getExceptions,
        (value) => !value.message && Array.isArray(value.items),
        (value) => setExceptions(value.items),
      ),
      read(
        "Decision history",
        () => api.getAudit({ limit: 5 }),
        (value) => !value.message && Array.isArray(value.items),
        (value) => setAudits(value.items),
      ),
      read(
        "Invoice history",
        () => api.getInbox({ page: 1 }),
        (value) => !value.message && Array.isArray(value.items),
        setInbox,
      ),
      read(
        "System status",
        api.getHealth,
        (value) => !!value.overall_status,
        setHealth,
      ),
    ]);
    if (request !== sequence.current) return;
    setLoading(false);
  }, []);
  useEffect(() => {
    void load();
    return () => {
      sequence.current += 1;
    };
  }, [load]);
  const summary = metrics?.summary as
    | (DashboardMetrics["summary"] & {
        pending_second_approval?: number;
        ready_to_approve?: number;
      })
    | undefined;
  const pending = summary?.pending_second_approval;
  const refresh = () => {
    setLoading(true);
    setPendingSources(SOURCES);
    void load();
  };
  const sectionState = (source: string) => (
    <p
      className={
        failed.includes(source) ? "today-source-warning" : "today-source-time"
      }
    >
      {failed.includes(source)
        ? `${source} could not refresh. ${receivedAt[source] ? `Previous result fetched ${date(receivedAt[source])}; it may be out of date.` : "No result available."}`
        : receivedAt[source]
          ? `${pendingSources.includes(source) ? "Refreshing; showing previous result. " : ""}Fetched ${date(receivedAt[source])}`
          : loading
            ? "Loading recorded data…"
            : "No result available."}
    </p>
  );
  const visibleInvoices = (inbox?.items || []).filter((invoice) =>
    [invoice.invoice_number, invoice.id, invoice.vendor_name].some((value) =>
      value?.toLowerCase().includes(query.trim().toLowerCase()),
    ),
  );
  const selected =
    visibleInvoices.find((invoice) => invoice.id === selectedId) ||
    visibleInvoices[0];
  const selectedState = selected ? invoiceState(selected) : null;
  const unavailable = (label: string) => (
    <div className="today-empty">
      <strong>{loading ? `Loading ${label}…` : `${label} unavailable`}</strong>
      <p>
        {pendingSources.includes(label)
          ? "Retrieving recorded workspace data."
          : "Try refreshing this page. No empty result has been assumed."}
      </p>
    </div>
  );
  return (
    <div className="today-page" aria-label="Today overview">
      <header className="today-heading">
        <div>
          <h1>Invoice operations</h1>
          <p>
            See what arrived, what needs attention and why a decision was made.
          </p>
        </div>
        <button className="today-button" disabled={loading} onClick={refresh}>
          <RefreshCw size={16} aria-hidden="true" />
          {loading ? "Refreshing…" : "Refresh data"}
        </button>
      </header>
      {failed.length > 0 && (
        <div className="today-error" role="alert">
          <AlertTriangle size={20} aria-hidden="true" />
          <div>
            <strong>Some information could not be refreshed</strong>
            <p>
              {failed.join(" · ")}. Previously loaded results are retained and
              may be out of date.
            </p>
          </div>
          <button className="today-button" disabled={loading} onClick={refresh}>
            Retry
          </button>
        </div>
      )}
      <div className="today-intro">
        <section className="today-start" aria-labelledby="today-start-title">
          <div>
            <FileInput size={22} aria-hidden="true" />
            <div>
              <h2 id="today-start-title">
                {currentUser?.role === "AUDITOR"
                  ? "Explore a recorded invoice"
                  : "Start with an invoice"}
              </h2>
              <span>
                {currentUser?.role === "AUDITOR"
                  ? "Choose a record below to inspect the evidence."
                  : "Start in the inbox with a PDF, or follow an existing record below."}
              </span>
            </div>
          </div>
          <a
            className="today-button today-primary"
            href={"/invoices"}
            onClick={(event) => followLink(event, "/invoices")}
          >
            {currentUser?.role === "AUDITOR"
              ? "Browse invoices"
              : "Open inbox to upload"}
            <ArrowRight size={17} aria-hidden="true" />
          </a>
          <p className="today-boundary">
            Internal sign-off only. This app does not send payments.
          </p>
        </section>
        <section className="today-guide" aria-labelledby="today-guide-title">
          <h2 id="today-guide-title">How an invoice becomes a decision</h2>
          <p>
            Follow the document, the checks and the reason behind the outcome.
          </p>
          <ol>
            <li>
              <strong>Receive the PDF</strong>
              <p>Upload in the inbox or import from a connected mailbox.</p>
            </li>
            <li>
              <strong>Read the invoice</strong>
              <p>Extract supplier details, amounts and line items.</p>
            </li>
            <li>
              <strong>Check the evidence</strong>
              <p>
                Compare with purchase orders, goods receipts and inspection
                records.
              </p>
            </li>
            <li>
              <strong>Explain the outcome</strong>
              <p>
                Inspect the reason, resolve blockers and obtain authorized
                internal sign-off.
              </p>
            </li>
          </ol>
          <p>
            This is a process guide, not live progress. The dashboard shows
            recorded states; individual execution stages are not streamed.
            Internal sign-off does not send a payment.
          </p>
        </section>
      </div>
      <section
        className="today-workload"
        data-tour="today-kpi-bar"
        aria-labelledby="today-workload-title"
      >
        <div className="today-section-heading">
          <h2 id="today-workload-title">Workspace workload</h2>
          <span>
            {loading
              ? "Refreshing recorded data…"
              : metrics
                ? `Workload snapshot · ${date(metrics.timestamp)}`
                : "Workload unavailable"}
          </span>
        </div>
        {sectionState("Workload")}
        {failed.includes("Financial context") &&
          sectionState("Financial context")}
        <dl className="today-stat-strip">
          <div>
            <dt>Invoices received</dt>
            <dd>
              {loading && !summary ? "…" : number(summary?.total_invoices)}
              <p>All recorded invoices</p>
            </dd>
          </div>
          <div>
            <dt>Intake jobs in progress</dt>
            <dd>
              {loading && !summary
                ? "…"
                : number(summary?.active_ingestion_jobs)}
              <p>Queued or processing jobs</p>
            </dd>
          </div>
          <div>
            <dt>Open issue records</dt>
            <dd className="today-amber">
              {loading && !summary ? "…" : number(summary?.open_exceptions)}
              <p>One invoice may have several issues</p>
            </dd>
          </div>
          <div>
            <dt>Internal sign-off complete</dt>
            <dd>
              {loading && !exposure
                ? "…"
                : number(exposure?.cleared_invoices_count)}
              <p>Invoices cleared for ERP posting</p>
            </dd>
          </div>
        </dl>
        <p className="today-footnote">
          These are different datasets, not a single pipeline total. Intake jobs
          and issue records are not invoice counts.
        </p>
      </section>
      <section
        className="today-panel today-records"
        aria-labelledby="today-records-title"
        aria-busy={pendingSources.includes("Invoice history")}
      >
        <div className="today-section-heading">
          <div>
            <h2 id="today-records-title">Follow an invoice</h2>
            <p>
              Select a recent record. See its outcome, then inspect the evidence
              behind it.
            </p>
          </div>
          <a
            className="today-text-button"
            href={"/invoices"}
            onClick={(event) => followLink(event, "/invoices")}
          >
            All invoices <ArrowRight size={16} aria-hidden="true" />
          </a>
        </div>
        {sectionState("Invoice history")}
        {inbox === null ? (
          unavailable("Invoice history")
        ) : inbox.items.length === 0 ? (
          <div className="today-empty">
            <FileInput size={32} aria-hidden="true" />
            <h3>Your first invoice starts here</h3>
            <p>
              No invoice records were returned.{" "}
              {currentUser?.role === "AUDITOR"
                ? "A workspace colleague can upload a PDF; you can inspect its evidence once it arrives."
                : "Open the inbox to upload a PDF. Return here and refresh to follow the recorded result."}
            </p>
            <div className="today-empty-actions">
              <a
                className="today-button today-primary"
                href={"/invoices"}
                onClick={(event) => followLink(event, "/invoices")}
              >
                Open inbox
              </a>
              <a
                className="today-button"
                href={"/setup"}
                onClick={(event) => followLink(event, "/setup")}
              >
                Review workspace setup
              </a>
            </div>
          </div>
        ) : (
          <>
            <div className="today-case-workspace">
              <div className="today-record-picker">
                <label className="today-search" htmlFor="today-invoice-search">
                  <span>Find in these {inbox.items.length} recent records</span>
                  <div>
                    <Search size={17} aria-hidden="true" />
                    <input
                      id="today-invoice-search"
                      type="search"
                      name="recent-invoice-search"
                      autoComplete="off"
                      spellCheck={false}
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Invoice or supplier"
                    />
                  </div>
                </label>
                <a
                  className="today-summary-jump"
                  href="#today-selected-invoice"
                >
                  Jump to selected invoice summary
                </a>
                <ul className="today-invoice-list" aria-label="Recent invoices">
                  {visibleInvoices.map((invoice) => {
                    const state = invoiceState(invoice);
                    return (
                      <li key={invoice.id}>
                        <button
                          className="today-invoice-choice"
                          aria-pressed={selected?.id === invoice.id}
                          aria-controls="today-selected-invoice"
                          onClick={() => setSelectedId(invoice.id)}
                        >
                          <span className="today-choice-top">
                            <strong>
                              {invoice.invoice_number || invoice.id}
                            </strong>
                            <span className="today-choice-amount">
                              {money(invoice.total_amount, invoice.currency)}
                            </span>
                          </span>
                          <span className="today-choice-supplier">
                            {invoice.vendor_name || "Supplier not reported"}
                          </span>
                          <span className="today-choice-bottom">
                            <span
                              className={`today-status today-status-${state.tone}`}
                            >
                              {state.text}
                            </span>
                            <span className="today-choice-date">
                              {date(invoice.created_at)}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {visibleInvoices.length === 0 && (
                  <div className="today-empty">
                    <strong>No match in the loaded records</strong>
                    <p>
                      This search only covers the latest {inbox.items.length}{" "}
                      invoices.
                    </p>
                    <button
                      className="today-button"
                      onClick={() => setQuery("")}
                    >
                      Clear search
                    </button>
                  </div>
                )}
              </div>
              <section
                id="today-selected-invoice"
                tabIndex={-1}
                className="today-case"
                aria-label="Selected invoice summary"
              >
                {selected && selectedState ? (
                  <>
                    <div className="today-case-heading">
                      <FileText size={24} aria-hidden="true" />
                      <div>
                        <h3>{selected.invoice_number || selected.id}</h3>
                        <p>{selected.vendor_name || "Supplier not reported"}</p>
                      </div>
                    </div>
                    <dl className="today-case-facts">
                      <div>
                        <dt>Billed amount</dt>
                        <dd>
                          {money(selected.total_amount, selected.currency)}
                        </dd>
                      </div>
                      <div>
                        <dt>Purchase order reference</dt>
                        <dd>{selected.po_reference || "Not reported"}</dd>
                      </div>
                    </dl>
                    <div className="today-case-state">
                      <span
                        className={`today-status today-status-${selectedState.tone}`}
                      >
                        {selectedState.text}
                      </span>
                      <span>Record updated {date(selected.updated_at)}</span>
                    </div>
                    <div className="today-outcome">
                      <h4>Recorded decision</h4>
                      <strong>{decisionLabel(selected.decision)}</strong>
                      <p>
                        {selected.decision_reason?.startsWith(
                          "Processing failed:",
                        )
                          ? "The document could not be processed. Open the invoice to inspect the available evidence."
                          : selected.decision_reason ||
                            "No decision reason was returned. Open the invoice to inspect available results."}
                      </p>
                    </div>
                    <div className="today-next">
                      <h4>What to do next</h4>
                      <p>
                        {selected.job_status === "FAILED"
                          ? "Open the invoice to inspect the processing error and any available source document. A failed job is not an approval decision."
                          : selected.job_status === "QUEUED" ||
                              selected.job_status === "PROCESSING"
                            ? "The last refresh reported a queued or processing job. This may be a retry after an earlier failed attempt. Refresh to check for a newer status; any recorded decision may predate this job."
                            : selected.stage === "INTERNAL_APPROVAL_COMPLETE"
                              ? "Inspect the recorded sign-off and its supporting evidence. This confirms internal review, not supplier payment."
                              : selected.decision === "REJECTED"
                                ? "Inspect the rejection reason and supporting checks. The recorded rejection is an outcome, not evidence that a payment was made."
                                : selected.stage === "PENDING_SECOND_APPROVAL"
                                  ? "Inspect the first sign-off and eligibility for a second reviewer. Authorization is checked in the approval workflow."
                                  : "Open the invoice to inspect checks, missing evidence and any differences in amounts before deciding what happens next."}
                      </p>
                    </div>
                    <a
                      className="today-button today-primary today-open-evidence"
                      href={`/invoices/${encodeURIComponent(selected.id)}`}
                      onClick={(event) =>
                        followLink(
                          event,
                          `/invoices/${encodeURIComponent(selected.id)}`,
                        )
                      }
                    >
                      Open invoice & evidence{" "}
                      <ArrowRight size={17} aria-hidden="true" />
                    </a>
                    <div className="today-evidence-key">
                      <span>
                        <FileText size={15} aria-hidden="true" /> Source
                        document
                      </span>
                      <span>
                        <ListChecks size={15} aria-hidden="true" /> Check
                        results
                      </span>
                      <span>
                        <History size={15} aria-hidden="true" /> Decision
                        history
                      </span>
                    </div>
                    <p className="today-footnote">
                      Evidence availability depends on the record. Opening an
                      invoice does not submit a decision.
                    </p>
                    <details className="today-record-metadata">
                      <summary>
                        Record details{" "}
                        <ChevronDown size={15} aria-hidden="true" />
                      </summary>
                      <dl>
                        <div>
                          <dt>Invoice ID</dt>
                          <dd>{selected.id}</dd>
                        </div>
                        <div>
                          <dt>Recorded stage</dt>
                          <dd>{selected.stage || "Not reported"}</dd>
                        </div>
                        <div>
                          <dt>Processing job status</dt>
                          <dd>{selected.job_status || "Not reported"}</dd>
                        </div>
                      </dl>
                    </details>
                  </>
                ) : (
                  <div className="today-empty">
                    <Search size={28} aria-hidden="true" />
                    <p>
                      Clear the search or open the inbox to find another
                      invoice.
                    </p>
                  </div>
                )}
              </section>
            </div>
            <p className="today-table-note">
              Latest {inbox.items.length} of {number(inbox.total_count)} invoice
              records, newest received first. These are invoice records, not
              separate execution runs. The inbox may retain your period filters.
            </p>
            <span role="status" className="today-sr-only">
              {selected
                ? `Selected ${selected.invoice_number || selected.id}. ${selectedState?.text}. Summary follows the invoice list.`
                : "No matching recent invoices."}
            </span>
          </>
        )}
      </section>
      <div className="today-lower-grid">
        <section
          className="today-panel"
          aria-labelledby="today-attention-title"
        >
          <div className="today-section-heading">
            <div>
              <h2 id="today-attention-title">Issues to resolve</h2>
              <p>Investigate the recorded issue before making a decision.</p>
            </div>
            <AlertTriangle
              size={21}
              className="today-amber"
              aria-hidden="true"
            />
          </div>
          {sectionState("Attention queue")}
          {summary?.open_exceptions != null &&
            exceptions &&
            summary.open_exceptions !== exceptions.length && (
              <p className="today-source-warning">
                Workload reports {number(summary.open_exceptions)} open issue
                records; the queue returned {exceptions.length}. These responses
                differ. Refresh before relying on the count.
              </p>
            )}
          {exceptions === null ? (
            unavailable("Attention queue")
          ) : exceptions.length === 0 ? (
            <div className="today-empty">
              <strong>No open issue records returned</strong>
              <p>
                This describes the exception queue only. Other invoices may
                still be processing or waiting for sign-off.
              </p>
            </div>
          ) : (
            <ul className="today-issues">
              {exceptions.slice(0, 3).map((item) => (
                <li key={item.exception_id}>
                  <span className="today-status today-status-attention">
                    Issue record
                  </span>
                  <h3>
                    {item.blocking_gate_name || "Issue description unavailable"}
                  </h3>
                  <p>
                    {item.invoice_number || item.invoice_id} ·{" "}
                    {item.vendor_name || "Supplier unavailable"}
                  </p>
                  <div>
                    <span>
                      Recorded exposure{" "}
                      <strong>{item.exposure_amount_inr == null ? `INR equivalent unavailable (${item.currency})` : money(item.exposure_amount_inr)}</strong>
                    </span>
                    <a
                      className="today-text-button"
                      href={`/invoices/${encodeURIComponent(item.invoice_id)}`}
                      onClick={(click) =>
                        followLink(
                          click,
                          `/invoices/${encodeURIComponent(item.invoice_id)}`,
                        )
                      }
                    >
                      Inspect invoice{" "}
                      <ArrowRight size={15} aria-hidden="true" />
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="today-section-footer">
            <a
              className="today-text-button"
              href={"/exceptions"}
              onClick={(event) => followLink(event, "/exceptions")}
            >
              Open exception queue <ArrowRight size={16} aria-hidden="true" />
            </a>
          </div>
          <div className="today-signoff">
            {failed.includes("Workload") && sectionState("Workload")}
            <div>
              <p className="today-first-review">
                {number(summary?.ready_to_approve)} match candidates ready for
                review{" "}
                <a
                  className="today-text-button"
                  href="/invoices"
                  onClick={(event) => followLink(event, "/invoices")}
                >
                  Find in inbox
                </a>
              </p>
              <strong>{number(pending)} pending second sign-off</strong>
              <p>
                Second sign-off requests require another authorized person.
                These are not payments due.
              </p>
            </div>
            {currentUser?.role === "AUDITOR" ? (
              <span>Queue restricted for auditors</span>
            ) : (
              <a
                className="today-button"
                href={"/approvals"}
                onClick={(event) => followLink(event, "/approvals")}
              >
                Second sign-off queue{" "}
                <ArrowRight size={15} aria-hidden="true" />
              </a>
            )}
          </div>
        </section>
        <section className="today-panel" aria-labelledby="today-history-title">
          <div className="today-section-heading">
            <div>
              <h2 id="today-history-title">Recent activity</h2>
              <p>
                Recent recorded events, including corrections and decisions.
              </p>
            </div>
            <History size={21} aria-hidden="true" />
          </div>
          {sectionState("Decision history")}
          {audits === null ? (
            unavailable("Decision history")
          ) : audits.length === 0 ? (
            <div className="today-empty">
              <strong>No audit events returned</strong>
              <p>Recorded actions will appear here when they are available.</p>
            </div>
          ) : (
            <ol className="today-events">
              {audits.map((event) => (
                <li key={event.id}>
                  <div className="today-event-heading">
                    <strong>{words(event.action)}</strong>
                    <time dateTime={event.timestamp}>
                      {date(event.timestamp)}
                    </time>
                  </div>
                  <p>{event.reason || "No reason recorded for this event."}</p>
                  {event.correlation_id && (
                    <span className="today-event-actor">
                      Process reference: {event.correlation_id}
                    </span>
                  )}
                  <span className="today-event-actor">
                    Actor: {event.actor_id || "Not reported"} ·{" "}
                    {words(event.actor_role)}
                  </span>
                  {event.invoice_id && (
                    <a
                      className="today-text-button"
                      href={`/invoices/${encodeURIComponent(event.invoice_id!)}`}
                      onClick={(click) =>
                        followLink(
                          click,
                          `/invoices/${encodeURIComponent(event.invoice_id!)}`,
                        )
                      }
                    >
                      Invoice evidence{" "}
                      <ExternalLink size={14} aria-hidden="true" />
                    </a>
                  )}
                </li>
              ))}
            </ol>
          )}
          <div className="today-section-footer">
            <a
              className="today-text-button"
              href={"/audit"}
              onClick={(event) => followLink(event, "/audit")}
            >
              Browse audit events <ArrowRight size={16} aria-hidden="true" />
            </a>
            <p>
              The Audit screen shows up to 100 events. It is not a complete
              ledger or a list of all execution runs.
            </p>
          </div>
        </section>
      </div>
      <details className="today-financial">
        <summary>
          Financial context{" "}
          <span>Amounts, supplier exposure and automation</span>
          <ChevronDown size={18} aria-hidden="true" />
        </summary>
        <div className="today-section-heading">
          <div>
            <h2 id="today-financial-title">Financial context</h2>
            <p>
              Recorded amounts and approvals help explain the workload. They do
              not confirm payment.
            </p>
          </div>
          <a
            className="today-text-button"
            href={"/invoices"}
            onClick={(event) => followLink(event, "/invoices")}
          >
            Inspect invoices <ArrowRight size={16} aria-hidden="true" />
          </a>
        </div>
        <p className="today-footnote">
          The totals service counts missing invoice amounts as zero and does not
          report how many are missing. Inspect individual invoices before
          relying on these totals.
        </p>
        {exposure && exposure.non_inr_invoices_excluded > 0 && (
          <p className="today-footnote">INR totals exclude {number(exposure.non_inr_invoices_excluded)} non-INR invoice(s) across the workspace. No currency conversion is available.</p>
        )}
        {sectionState("Financial context")}
        {failed.includes("Workload") && sectionState("Workload")}
        <dl>
          <div>
            <dt>Invoice liability not cleared</dt>
            <dd>
              {money(exposure?.total_blocked_liability_inr)}
              <p>
                {number(exposure?.blocked_invoices_count)} invoices received or
                awaiting action or sign-off, excluding rejected invoices
              </p>
            </dd>
          </div>
          <div>
            <dt>Cleared for ERP posting</dt>
            <dd>
              {money(exposure?.cleared_for_erp_inr)}
              <p>Internal sign-off recorded; no payment is sent</p>
            </dd>
          </div>
          <div>
            <dt>Verified MSME supplier invoices</dt>
            <dd>
              {money(exposure?.statutory_msme_verified_due_inr)}
              <p>
                {number(exposure?.statutory_msme_verified_count)} invoices for
                verified micro, small or medium enterprise suppliers; inspect
                invoice deadlines
              </p>
            </dd>
          </div>
          <div>
            <dt>Automatic approval rate</dt>
            <dd>
              {summary?.touchless_rate_pct == null
                ? "Not reported"
                : `${number(summary.touchless_rate_pct)}%`}
              <p>
                API-defined rate: auto-approved ÷ (auto-approved + rejected).
                Manual sign-offs are excluded.
              </p>
            </dd>
          </div>
        </dl>
      </details>
      <footer className="today-page-footer">
        <span>
          <Clock3 size={15} aria-hidden="true" /> System report:{" "}
          <strong>
            {health
              ? words(health.overall_status)
              : loading
                ? "Loading…"
                : "Unavailable"}
          </strong>
        </span>
        <a
          className="today-text-button"
          href={"/settings/connections"}
          onClick={(event) => followLink(event, "/settings/connections")}
        >
          Connections & setup status <ArrowRight size={15} aria-hidden="true" />
        </a>
      </footer>
      {failed.includes("System status") && sectionState("System status")}
      <p className="today-snapshot-note">
        Snapshots update when you refresh. No live stage-by-stage execution feed
        is available here. Internal sign-off does not send payments.
      </p>
      <span className="today-sr-only" role="status">
        {loading
          ? "Refreshing dashboard data"
          : failed.length
            ? "Dashboard refreshed with unavailable sources"
            : "Dashboard data loaded"}
      </span>
    </div>
  );
};
