import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pollRun } from '../src/utils/runPolling.ts';

const flush = () => new Promise(resolve => setImmediate(resolve));
function clock() {
  let id = 0;
  const pending = new Map();
  return {
    pending,
    schedule: (fn, ms) => { pending.set(++id, { fn, ms }); return id; },
    cancel: id => pending.delete(id),
    tick: ms => { const item = [...pending].find(([, value]) => value.ms === ms); assert.ok(item, `timer ${ms}`); pending.delete(item[0]); item[1].fn(); },
  };
}
test('full snapshot reconnect replaces data, backs off and stops on completion', async () => {
  const timer = clock();
  const snapshots = [];
  const errors = [];
  let calls = 0;
  const stop = pollRun({ ...timer,
    load: async () => { if (++calls === 2) throw new Error('offline'); return { events: calls === 1 ? [1] : [1,2], active: calls < 3 }; },
    receive: value => snapshots.push(value), unavailable: value => errors.push(value), active: value => value.active,
  });
  await flush(); timer.tick(3000); await flush();
  assert.deepEqual(errors, [false]); timer.tick(6000); await flush();
  assert.deepEqual(snapshots.map(value => value.events), [[1],[1,2]]);
  assert.equal(timer.pending.size, 0); stop();
});
test('pending request never overlaps, cleanup aborts and ignores late response', async () => {
  const timer = clock(); let resolve; let signal; let received = 0;
  const stop = pollRun({ ...timer, load: value => { signal = value; return new Promise(done => { resolve = done; }); },
    receive: () => received++, unavailable: () => assert.fail(), active: () => true });
  assert.equal(timer.pending.size, 1); // Only request timeout, no second poll.
  stop(); assert.equal(signal.aborted,true);
  resolve({}); await flush(); assert.equal(received,0); assert.equal(timer.pending.size,0);
});
for (const status of [401,403,404]) test(`access failure ${status} clears state and stops reconnecting`, async () => {
  const timer = clock(); let denied = false;
  pollRun({ ...timer, load: async () => { throw { status }; }, receive: () => assert.fail(),
    unavailable: value => { denied = value; }, active: () => true });
  await flush(); assert.equal(denied,true); assert.equal(timer.pending.size,0);
});
test('hung request aborts after timeout and retries', async () => {
  const timer = clock(); let unavailable = false;
  const stop = pollRun({ ...timer, load: signal => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')))),
    receive: () => assert.fail(), unavailable: () => { unavailable = true; }, active: () => true });
  timer.tick(15000); await flush(); assert.equal(unavailable,true); timer.tick(6000); stop(); await flush();
  assert.equal(timer.pending.size,0);
});
