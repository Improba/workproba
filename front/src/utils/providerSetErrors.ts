import type { ProviderSetReadinessIssue } from '@utils/providerSetValidation';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';

const PROVIDER_SET_READINESS_ISSUES: ReadonlySet<ProviderSetReadinessIssue> = new Set([
  'no_set',
  'missing_api_key',
  'cloud_not_enrolled',
  'not_subscribed',
  'quota_exceeded',
  'cloud_unreachable',
]);

export function normalizeReadinessIssue(code: string): ProviderSetReadinessIssue | null {
  if (code === 'api_key_missing') return 'missing_api_key';
  if (PROVIDER_SET_READINESS_ISSUES.has(code as ProviderSetReadinessIssue)) {
    return code as ProviderSetReadinessIssue;
  }
  return null;
}

export function isProviderSetReadinessIssue(code: string): code is ProviderSetReadinessIssue {
  return normalizeReadinessIssue(code) !== null;
}

export class ProviderSetNotReadyError extends Error {
  readonly reason: ProviderSetReadinessIssue;
  readonly notified: boolean;

  constructor(reason: ProviderSetReadinessIssue, notified = true) {
    super(chatErrorMessageForReadiness(reason));
    this.name = 'ProviderSetNotReadyError';
    this.reason = reason;
    this.notified = notified;
  }
}
