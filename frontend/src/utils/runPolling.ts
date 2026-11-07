/** Full snapshots make reconnects idempotent; never overlap requests. */
export function pollRun<T>({ load, receive, unavailable, active, schedule = setTimeout, cancel = clearTimeout }: {
  load: (signal: AbortSignal) => Promise<T>;
  receive: (snapshot: T) => void;
  unavailable: (terminal: boolean) => void;
  active: (snapshot: T) => boolean;
  schedule?: typeof setTimeout;
  cancel?: typeof clearTimeout;
}) {
  let stopped = false;
  let failures = 0;
  let timer: ReturnType<typeof setTimeout>;
  let controller: AbortController;
  async function next() {
    controller = new AbortController();
    const timeout = schedule(() => controller.abort(), 15000);
    let again = true;
    try {
      const snapshot = await load(controller.signal);
      if (stopped) return;
      failures = 0;
      receive(snapshot);
      again = active(snapshot);
    } catch (error) {
      if (stopped) return;
      const status = (error as { status?: number }).status;
      const terminal = status === 401 || status === 403 || status === 404;
      unavailable(terminal);
      failures++;
      again = !terminal;
    } finally {
      cancel(timeout);
      if (!stopped && again) timer = schedule(next, Math.min(3000 * 2 ** failures, 30000));
    }
  }
  void next();
  return () => { stopped = true; cancel(timer); controller?.abort(); };
}
