import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { pollRun } from '../utils/runPolling';
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  FileText,
  Layers,
} from 'lucide-react';
import { Badge } from './ui';
import './InvoiceRunView.css';

export interface ProcessingEvent {
  id: string;
  sequence: number;
  attempt: number;
  stage: string;
  status: string;
  timestamp: string;
  message: string;
  outcome: { stage: string; decision: string; reason: string } | null;
}

export interface ProcessingSnapshot {
  invoice_id: string;
  jobs: {
    id: string;
    status: string;
    created_at: string;
    retry_count: number;
    lease_expired: boolean;
    completed_at: string | null;
    error_recorded: boolean;
    error_message?: string | null;
    events: ProcessingEvent[];
  }[];
}

const words = (value?: string | null) =>
  value ? String(value).toLowerCase().replaceAll('_', ' ') : '—';

const time = (value?: string | null) => {
  if (!value) return '—';
  try {
    const d = new Date(value);
    return isNaN(d.getTime()) ? '—' : d.toLocaleString();
  } catch {
    return '—';
  }
};

export function InvoiceRunView({
  invoiceId,
  onOutcome,
  invoiceStage,
  invoiceDecision,
  onRetry,
  retrying = false,
}: {
  invoiceId: string;
  onOutcome: () => void;
  invoiceStage?: string | null;
  invoiceDecision?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const [snapshot, setSnapshot] = useState<ProcessingSnapshot | null>(null);
  const [connection, setConnection] = useState('Loading recorded checkpoints…');
  // refresh trigger removed
  // Collapsed by default for completed, rejected, held, or finished invoices
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const callback = useRef(onOutcome);
  useEffect(() => {
    callback.current = onOutcome;
  }, [onOutcome]);
  const outcomes = useRef(new Set<string>());

  useEffect(
    () =>
      pollRun({
        load: (signal) => api.getInvoiceProcessing(invoiceId, signal),
        receive: (next) => {
          setSnapshot(next);
          setConnection(`Last checked ${new Date().toLocaleTimeString()}.`);
          const ids = next.jobs.flatMap((job) => [
            ...job.events
              .filter((event) => event.status === 'RECORDED')
              .map((event) => event.id),
            ...(job.status === 'FAILED' ? [`${job.id}:FAILED`] : []),
          ]);
          const changed = ids.some((id) => !outcomes.current.has(id));
          outcomes.current = new Set(ids);
          if (changed) callback.current();
        },
        unavailable: (terminal) => {
          if (terminal) setSnapshot(null);
          setConnection(
            terminal
              ? 'Run view unavailable. Check your session and workspace access.'
              : 'Updates unavailable; showing the last received snapshot. Reconnecting automatically.',
          );
        },
        active: (next) =>
          next.jobs.some(
            (job) =>
              job.status === 'QUEUED' ||
              (job.status === 'PROCESSING' && !job.lease_expired),
          ),
      }),
    [invoiceId],
  );

  const latestJob = snapshot?.jobs[0];
  const allEvents = snapshot?.jobs.flatMap((j) => j.events) || [];
  const totalEvents = allEvents.length;

  const latestOutcomeEvent = latestJob?.events.slice().reverse().find((e) => e.outcome);
  const outcome = latestOutcomeEvent?.outcome;

  const isCompleted = latestJob?.status === 'COMPLETED';
  const isFailed = latestJob?.status === 'FAILED';
  const isQueued = latestJob?.status === 'QUEUED';
  const isProcessing = latestJob?.status === 'PROCESSING';
  const isStalled = Boolean(isProcessing && latestJob?.lease_expired);
  const isActivelyProcessing = Boolean(isProcessing && !isStalled);

  const completedTime = latestJob?.completed_at
    ? time(latestJob.completed_at)
    : null;
  const jobError =
    latestJob?.error_message ||
    (latestJob?.error_recorded
      ? 'An error was recorded during processing.'
      : null);

  const statusTone = isCompleted
    ? 'success'
    : isFailed
      ? 'error'
      : isStalled
        ? 'warning'
        : isActivelyProcessing
          ? 'info'
          : isQueued
            ? 'warning'
            : 'neutral';

  return (
    <section
      className="invoice-run-container border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900 shadow-2xs overflow-hidden transition-all duration-150"
      aria-label="Processing run status"
    >
      {/* 1. Compact Status Summary Bar (Always visible) */}
      <div className="invoice-run-summary flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 sm:px-4">
        <div className="flex items-center gap-2.5 flex-wrap min-w-0">
          {/* Status Icon */}
          {isCompleted ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          ) : isFailed || isStalled ? (
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          ) : isActivelyProcessing ? (
            <RefreshCw className="w-4 h-4 text-indigo-600 dark:text-indigo-400 animate-spin shrink-0" />
          ) : isQueued ? (
            <Clock className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          ) : (
            <FileText className="w-4 h-4 text-slate-400 shrink-0" />
          )}

          {/* Status Badge */}
          <Badge tone={statusTone} size="sm">
            {isStalled
              ? 'STALLED'
              : isFailed
                ? 'FAILED'
                : latestJob ? words(latestJob.status).toUpperCase() : 'QUEUED'}
          </Badge>

          {/* Processing Outcome Description */}
          <span className="font-semibold text-xs text-slate-800 dark:text-slate-100 truncate">
            {outcome
              ? `Outcome: ${words(outcome.decision)} (${words(outcome.stage)})`
              : isStalled
                ? 'Processing stalled — worker lease expired'
                : invoiceDecision
                  ? `Recorded decision: ${words(invoiceDecision)}${invoiceStage ? ` (${words(invoiceStage)})` : ''}`
                  : isCompleted
                    ? 'Extraction and matching completed'
                    : isActivelyProcessing
                      ? 'Extraction and verification in progress…'
                      : 'Queued for processing'}
          </span>

          <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">
            •
          </span>

          {/* Completion Time & Checkpoints Count */}
          <span className="text-xs text-slate-500 dark:text-slate-400 truncate">
            {completedTime
              ? `Completed ${completedTime}`
              : isStalled
                ? 'Recovery required'
                : isActivelyProcessing
                  ? 'Processing active'
                  : 'Intake registered'}
            {totalEvents > 0 &&
              ` · ${totalEvents} checkpoint${totalEvents === 1 ? '' : 's'} recorded`}
          </span>

          {/* Error Message Pill if present */}
          {jobError && (
            <span className="text-rose-600 dark:text-rose-400 font-medium px-2 py-0.5 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-[11px]">
              {jobError}
            </span>
          )}
        </div>

        {/* Action Toggle Button */}
        <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
          {onRetry && (isStalled || isFailed || isQueued) && (
            <button
              type="button"
              onClick={onRetry}
              disabled={retrying}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-950 disabled:opacity-60 transition-colors shadow-2xs cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
              <span>{retrying ? 'Retrying…' : 'Retry processing'}</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-750 text-slate-700 dark:text-slate-200 transition-colors shadow-2xs cursor-pointer"
            aria-expanded={isExpanded}
            aria-controls="invoice-run-history"
          >
            <Layers className="w-3.5 h-3.5 text-slate-400" />
            <span>
              {isExpanded
                ? 'Hide Processing History'
                : 'View Processing History'}
            </span>
            {isExpanded ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            )}
          </button>
        </div>
      </div>

      {/* 2. Expandable Full Processing History (Only visible when toggled open) */}
      {isExpanded && (
        <div
          id="invoice-run-history"
          className="invoice-run-details border-t border-slate-200 dark:border-slate-800 p-4 sm:p-5 bg-slate-50/50 dark:bg-slate-950/40 space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-200/80 dark:border-slate-800">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <span>Checkpoint History & Pipeline Trace</span>
                <span className="text-xs font-normal text-slate-500">
                  ({totalEvents} recorded events)
                </span>
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Recorded checkpoints refreshed while processing. Extraction
                includes grounding and validation.
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-[11px] text-slate-400" role="status">
                {connection}
              </span>
            </div>
          </div>

          {snapshot && snapshot.jobs.length === 0 && (
            <p className="text-xs text-slate-400 italic py-2">
              No processing job or stage events are available for this invoice.
            </p>
          )}

          {snapshot?.jobs.map((job) => (
            <div
              key={job.id}
              className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                <span className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2 font-mono">
                  <span>Job: {job.id}</span>
                  <Badge tone={statusTone} size="sm">
                    {words(job.status)}
                  </Badge>
                </span>
                <span className="text-slate-500 text-[11px]">
                  Created {time(job.created_at)} · Retries: {job.retry_count}
                  {job.completed_at && ` · Completed ${time(job.completed_at)}`}
                </span>
              </div>

              {job.status === 'QUEUED' && (
                <p className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 p-2 rounded border border-amber-200 dark:border-amber-900">
                  Waiting for a worker. Use Retry processing to claim this
                  invoice; the action is scoped to this document only.
                </p>
              )}

              {job.lease_expired && (
                <p
                  role="status"
                  className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 p-2 rounded border border-amber-200 dark:border-amber-900"
                >
                  Worker lease expired. Completion is unconfirmed. Use Retry
                  processing to recover this invoice; stale results cannot commit.
                </p>
              )}

              {job.status === 'FAILED' && (
                <p
                  role="status"
                  className="text-xs text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 p-2 rounded border border-rose-200 dark:border-rose-900"
                >
                  Processing stopped after failure. Review the evidence and
                  contact an administrator.
                </p>
              )}

              {job.events.length === 0 ? (
                <p className="text-xs text-slate-400 italic">
                  No stage events recorded for this job.
                </p>
              ) : (
                <ol className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  {job.events.map((event) => (
                    <li
                      key={event.id}
                      className="py-2.5 first:pt-1 last:pb-1 space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0" />
                          <strong className="font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider text-[11px]">
                            {words(event.stage)}
                          </strong>
                          <span className="text-slate-400">·</span>
                          <span className="text-slate-600 dark:text-slate-300 font-mono text-[11px]">
                            {words(event.status)}
                          </span>
                          <span className="text-slate-400">·</span>
                          <span className="text-slate-500 text-[11px]">
                            {event.attempt === 0
                              ? 'Intake'
                              : `Attempt ${event.attempt}`}
                          </span>
                        </div>
                        <time
                          dateTime={event.timestamp}
                          className="text-[11px] font-mono text-slate-400"
                        >
                          {time(event.timestamp)}
                        </time>
                      </div>
                      <p className="text-slate-600 dark:text-slate-400 text-xs pl-3.5">
                        {event.message || '—'}
                      </p>
                      {event.outcome && (
                        <div className="pl-3.5 text-xs text-indigo-700 dark:text-indigo-300 bg-indigo-50/70 dark:bg-indigo-950/40 p-2 rounded mt-1 border border-indigo-100 dark:border-indigo-900">
                          <span className="font-semibold">
                            Recorded processing outcome:
                          </span>{' '}
                          {words(event.outcome.decision)} (
                          {words(event.outcome.stage)})
                          {event.outcome.reason && (
                            <span className="block text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                              {event.outcome.reason}
                            </span>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
