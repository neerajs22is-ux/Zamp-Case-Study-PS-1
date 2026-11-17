const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../engine/templates/sandbox.html'), 'utf8');
const source = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(match => match[1]).find(script => script.includes('function pollProcessingStatus'));

function harness(responses = []) {
  const elements = new Map();
  const timers = new Map();
  let nextTimer = 0;
  const element = id => {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, {
        textContent: '', innerText: '', innerHTML: '', href: '', className: '',
        classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) },
        addEventListener() {},
        appendChild(child) { this.children.push(child); }, children: [],
      });
    }
    return elements.get(id);
  };
  const context = vm.createContext({
    console, Intl, URL, encodeURIComponent,
    localStorage: { getItem: () => null },
    document: { getElementById: element, addEventListener() {}, createElement: () => ({ innerHTML: '', className: '' }) },
    window: { addEventListener() {}, scrollTo() {} },
    performance: { now: () => 51000 },
    setInterval(fn) { const id = ++nextTimer; timers.set(id, fn); return id; },
    clearInterval(id) { timers.delete(id); },
    fetch: async () => {
      assert.ok(responses.length, 'unexpected request');
      const response = responses.shift();
      if (response instanceof Error) throw response;
      return { ok: response.status < 400, status: response.status, json: async () => response.body };
    },
  });
  vm.runInContext(source, context);
  return { context, element, timers };
}

test('slow current job is not replaced by an older completed result', async () => {
  const h = harness([{ status: 200, body: { jobs: [
    { id: 'old', status: 'COMPLETED', events: [] },
    { id: 'current', status: 'PROCESSING', events: [{ stage: 'EXTRACTION', message: 'Reading' }] },
  ] } }]);
  let completed = false;
  h.context.onProcessingComplete = () => { completed = true; };
  h.context.pollProcessingStatus('invoice', 0, 'current');
  await [...h.timers.values()][0]();
  assert.equal(completed, false);
  assert.match(h.element('processing-status-text').textContent, /Still processing/);
  assert.equal(h.element('processing-invoice-link').href, '/invoices/invoice');
});

test('failed job never renders an invoice decision', async () => {
  const h = harness([{ status: 200, body: { jobs: [{ id: 'current', status: 'FAILED', events: [] }] } }]);
  let completed = false;
  h.context.onProcessingComplete = () => { completed = true; };
  h.context.pollProcessingStatus('invoice', 0, 'current');
  await [...h.timers.values()][0]();
  assert.equal(completed, false);
  assert.match(h.element('processing-status-text').textContent, /Processing failed/);
  assert.equal(h.timers.size, 0);
});

test('completed job renders only its own recorded result and checkpoints', async () => {
  const events = [{ stage: 'OUTCOME', status: 'RECORDED', message: 'Match', timestamp: '2026-01-01T00:00:00Z' }];
  const h = harness([
    { status: 200, body: { jobs: [{ id: 'old', status: 'FAILED', events: [] }, { id: 'current', status: 'COMPLETED', events }] } },
    { status: 200, body: { status: 'COMPLETED', job_id: 'current', invoice_id: 'invoice' } },
  ]);
  let received;
  h.context.onProcessingComplete = (data, steps) => { received = { data, steps }; };
  h.context.pollProcessingStatus('invoice', 0, 'current');
  await [...h.timers.values()][0]();
  assert.equal(received.data.mode, 'CURRENT_RUN');
  assert.equal(received.steps[0].message, 'Match');
});

test('stale results and inaccessible status do not render completion', async () => {
  for (const responses of [
    [{ status: 200, body: { jobs: [{ id: 'current', status: 'COMPLETED', events: [] }] } },
      { status: 200, body: { status: 'COMPLETED', job_id: 'other' } }],
    [{ status: 401 }], [{ status: 503 }], [new Error('network')],
  ]) {
    const h = harness(responses);
    let completed = false;
    h.context.onProcessingComplete = () => { completed = true; };
    h.context.pollProcessingStatus('invoice', 0, 'current');
    await [...h.timers.values()][0]();
    assert.equal(completed, false);
    assert.match(h.element('processing-status-text').textContent, /unavailable|changed/i);
  }
});

test('empty audit history and unavailable metadata are not invented', () => {
  const h = harness();
  h.context.renderAuditTimeline([]);
  assert.match(h.element('ch7-timeline-container').textContent, /No recorded processing events/);
  vm.runInContext("currentChapter = 1; activeRunData = { invoice: {}, grounding: {} }; renderCurrentChapterContent()", h.context);
  assert.equal(h.element('ch1-sha256-display').textContent, 'SHA-256: Unavailable');
  assert.equal(h.element('ch1-meta-pages').textContent, 'Unavailable');
  assert.equal(h.element('ch1-meta-size').textContent, 'Unavailable');
  vm.runInContext("currentChapter = 3; renderCurrentChapterContent()", h.context);
  assert.equal(h.element('ch3-tripwire-badge').textContent, 'GROUNDING STATUS UNAVAILABLE');
  assert.equal(h.element('ch3-grounded-count').textContent, 'Unavailable');
});

test('guidance is tied to the actual blocker', () => {
  const h = harness();
  assert.match(h.context.sandboxNextAction({match_gates:[{gate_number:7,status:'FAIL'}]}), /duplicate/i);
  assert.match(h.context.sandboxNextAction({match_gates:[{gate_number:2,status:'FAIL'}]}), /purchase order/i);
  assert.match(h.context.sandboxNextAction({match_gates:[{gate_number:6,status:'PENDING'}]}), /incomplete/i);
  assert.doesNotMatch(h.context.sandboxNextAction({decision:'FLAGGED_EXCEPTION',match_gates:[]}), /price|duplicate/i);
});

test('history uses the invoice id supplied by the runs response', async () => {
  const h = harness([{status:200, body:{items:[{id:'saved-invoice',invoice_number:'TEST-1',decision:'MATCH_CANDIDATE'}]}}]);
  let selected;
  h.context.loadExistingRun = id => { selected = id; };
  await h.context.loadRunHistory();
  h.element('previous-runs-container').children[0].onclick();
  assert.equal(selected, 'saved-invoice');
});
