import { describe, expect, it } from 'vitest';
import {
  isMistralOutageCode,
  isNonRetryableCloudLlmCode,
} from '@utils/chatCloudErrors';

describe('chatCloudErrors', () => {
  it('marque les erreurs cloud comme non retryables', () => {
    expect(isNonRetryableCloudLlmCode('cloud_not_enrolled')).toBe(true);
    expect(isNonRetryableCloudLlmCode('quota_exceeded')).toBe(true);
    expect(isNonRetryableCloudLlmCode('turn_timeout')).toBe(false);
  });

  it('regroupe les codes mistral_*', () => {
    expect(isMistralOutageCode('mistral_timeout')).toBe(true);
    expect(isMistralOutageCode('not_subscribed')).toBe(false);
  });
});
