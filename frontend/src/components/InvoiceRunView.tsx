import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { pollRun } from '../utils/runPolling';
import './InvoiceRunView.css';

export interface ProcessingEvent {
  id: string; sequence: number; attempt: number; stage: string; status: string;
  timestamp: string; message: string;
  outcome: { stage: string; decision: string; reason: string } | null;
}
export interface ProcessingSnapshot {
  invoice_id: string;
  jobs: { id: string; status: string; created_at: string; retry_count: number;
    lease_expired: boolean; completed_at: string | null; error_recorded: boolean;
    events: ProcessingEvent[] }[];
}
const words = (value: string) => value.toLowerCase().replaceAll('_', ' ');
const time = (value: string) => new Date(value).toLocaleString();

export function InvoiceRunView({ invoiceId, onOutcome }: { invoiceId: string; onOutcome: () => void }) {
  const [snapshot, setSnapshot] = useState<ProcessingSnapshot | null>(null);
  const [connection, setConnection] = useState('Loading recorded checkpoints…');
  const [refresh, setRefresh] = useState(0);
  const callback = useRef(onOutcome);
  useEffect(() => { callback.current = onOutcome; }, [onOutcome]);
  const outcomes = useRef(new Set<string>());
  useEffect(() => pollRun({
    load: signal => api.getInvoiceProcessing(invoiceId, signal),
    receive: next => {
      setSnapshot(next);
      setConnection(`Last checked ${new Date().toLocaleTimeString()}.`);
      const ids = next.jobs.flatMap(job => [
        ...job.events.filter(event => event.status === 'RECORDED').map(event => event.id),
        ...(job.status === 'FAILED' ? [`${job.id}:FAILED`] : []),
      ]);
      const changed = ids.some(id => !outcomes.current.has(id));
      outcomes.current = new Set(ids);
      if (changed) callback.current();
    },
    unavailable: terminal => {
      if (terminal) setSnapshot(null);
      setConnection(terminal ? 'Run view unavailable. Check your session and workspace access.' : 'Updates unavailable; showing the last received snapshot. Reconnecting automatically.');
    },
    active: next => next.jobs.some(job => job.status === 'QUEUED' || job.status === 'PROCESSING'),
  }), [invoiceId, refresh]);
  return <section className="invoice-run" aria-labelledby="invoice-run-title">
    <div className="invoice-run-heading"><h2 id="invoice-run-title">Processing run</h2>
      <button type="button" onClick={() => setRefresh(value => value + 1)}>Refresh checkpoints</button></div>
    <p>Recorded checkpoints, refreshed while processing. Gaps do not confirm completion. Extraction includes grounding and validation; a returned result may still require review.</p>
    <p role="status">{connection}</p>
    {snapshot && snapshot.jobs.length === 0 && <p>No processing job or stage events are available for this invoice. Inspect its recorded decision and history below.</p>}
    {snapshot?.jobs.map(job => <div key={job.id} className="invoice-run-job">
      <h3>{words(job.status)} · {job.id}</h3>
      <p>Created <time dateTime={job.created_at}>{time(job.created_at)}</time> · Failed or interrupted attempts: {job.retry_count}
        {job.completed_at && <> · Completed <time dateTime={job.completed_at}>{time(job.completed_at)}</time></>}</p>
      {job.status === 'QUEUED' && <p>Waiting for a worker. An authorized operator can resume the workspace queue below; this may process another queued invoice first.</p>}
      {job.lease_expired && <p role="status">Worker lease expired. Completion is unconfirmed; an authorized operator must resume the workspace queue to recover this attempt.</p>}
      {job.status === 'FAILED' && <p role="status">Processing stopped after failure. Review the evidence and contact an administrator with this job ID.</p>}
      {job.error_recorded && !job.events.some(event => event.status === 'FAILED' || event.status === 'INTERRUPTED') && <p>An earlier error is recorded, but no structured error checkpoint is available.</p>}
      {job.events.length === 0 ? <p>No stage events were recorded for this job. Its status does not establish which stages completed.</p> :
        <ol>{job.events.map(event => <li key={event.id}>
          <div><strong>{words(event.stage)} · {words(event.status)}</strong> · {event.attempt === 0 ? 'Intake' : `Attempt ${event.attempt}`} · <time dateTime={event.timestamp}>{time(event.timestamp)}</time></div>
          <p>{event.message}</p>
          {event.outcome && <p>Recorded processing outcome: {words(event.outcome.decision)} ({words(event.outcome.stage)}). Later human decisions remain in invoice history.</p>}
        </li>)}</ol>}
    </div>)}
  </section>;
}
