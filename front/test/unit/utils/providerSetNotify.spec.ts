import { describe, expect, it } from 'vitest';
import {
  isProviderSetReadinessIssue,
  normalizeReadinessIssue,
  ProviderSetNotReadyError,
} from '@utils/providerSetErrors';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';

describe('providerSetErrors', () => {
  it('reconnaît les codes readiness et l’alias api_key_missing', () => {
    expect(isProviderSetReadinessIssue('missing_api_key')).toBe(true);
    expect(isProviderSetReadinessIssue('api_key_missing')).toBe(true);
    expect(isProviderSetReadinessIssue('cloud_not_enrolled')).toBe(true);
    expect(isProviderSetReadinessIssue('not_subscribed')).toBe(true);
    expect(isProviderSetReadinessIssue('quota_exceeded')).toBe(true);
    expect(isProviderSetReadinessIssue('cloud_unreachable')).toBe(true);
    expect(isProviderSetReadinessIssue('no_set')).toBe(true);
    expect(isProviderSetReadinessIssue('meeting_failed')).toBe(false);
    expect(isProviderSetReadinessIssue('unavailable')).toBe(false);
  });

  it('normalise api_key_missing vers missing_api_key', () => {
    expect(normalizeReadinessIssue('api_key_missing')).toBe('missing_api_key');
    expect(normalizeReadinessIssue('cloud_not_enrolled')).toBe('cloud_not_enrolled');
    expect(normalizeReadinessIssue('unknown')).toBeNull();
  });

  it('ProviderSetNotReadyError expose reason et message readiness', () => {
    const err = new ProviderSetNotReadyError('cloud_not_enrolled');
    expect(err).toBeInstanceOf(ProviderSetNotReadyError);
    expect(err.notified).toBe(true);
    expect(err.reason).toBe('cloud_not_enrolled');
    expect(err.message).toBe(chatErrorMessageForReadiness('cloud_not_enrolled'));
  });

  it('ProviderSetNotReadyError accepte notified=false', () => {
    const err = new ProviderSetNotReadyError('missing_api_key', false);
    expect(err.notified).toBe(false);
  });
});
