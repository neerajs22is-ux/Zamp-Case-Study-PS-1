export type CheckResultKind = 'passed' | 'failed' | 'pending' | 'not evaluated' | 'unknown' | 'unavailable';

export function checkResultKind(status: unknown): CheckResultKind {
  if (status === 'PASS') return 'passed';
  if (status === 'FAIL') return 'failed';
  if (status === 'PENDING' || status === 'IN_PROGRESS' || status === 'RUNNING') return 'pending';
  if (status === 'NOT_EVALUATED') return 'not evaluated';
  if (status == null || status === '' || status === 'UNAVAILABLE') return 'unavailable';
  return 'unknown';
}

export function summarizeCheckResults(checks: { status?: unknown }[]): string {
  if (checks.length === 0) return 'Check results unavailable';
  const counts: Record<CheckResultKind, number> = {
    passed: 0, failed: 0, pending: 0, 'not evaluated': 0, unknown: 0, unavailable: 0,
  };
  checks.forEach(check => { counts[checkResultKind(check?.status)] += 1; });
  if (counts.passed === checks.length) return `All ${checks.length} returned ${checks.length === 1 ? 'check' : 'checks'} passed`;
  const order: CheckResultKind[] = ['failed', 'pending', 'not evaluated', 'unknown', 'unavailable', 'passed'];
  return order.filter(kind => counts[kind] > 0).map(kind => `${counts[kind]} ${kind}`).join(' · ');
}
