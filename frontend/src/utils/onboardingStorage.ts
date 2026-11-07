export function onboardingStorageKey(userId: string, orgId: string, name: string): string {
  return `ap.onboarding.${JSON.stringify([userId, orgId, name])}`;
}
