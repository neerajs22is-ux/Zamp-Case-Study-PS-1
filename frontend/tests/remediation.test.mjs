import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getRemediation } from '../src/utils/remediation.ts';
const invoice = { po_reference: 'PO-1' };
test('guidance follows duplicate, purchase order, variance and pending checks', () => {
  assert.match(getRemediation({gate_number:7,status:'FAIL'}, invoice), /duplicate/i);
  assert.match(getRemediation({gate_number:2,status:'FAIL'}, invoice), /purchase order/i);
  assert.match(getRemediation({gate_number:6,status:'FAIL'}, invoice), /quantity|price/i);
  assert.match(getRemediation({gate_number:6,status:'PENDING'}, invoice), /status/i);
});
