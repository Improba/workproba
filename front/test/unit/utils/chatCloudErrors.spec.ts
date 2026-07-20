import { describe, expect, it } from 'vitest';
import { normalizeChatErrorCode } from '#types';
import {
  isMistralOutageCode,
  isNonRetryableCloudLlmCode,
} from '@utils/chatCloudErrors';

describe('chatCloudErrors', () => {
  it('marque les erreurs cloud comme non retryables', () => {
    expect(isNonRetryableCloudLlmCode('cloud_not_enrolled')).toBe(true);
    expect(isNonRetryableCloudLlmCode('quota_exceeded')).toBe(true);
    expect(isNonRetryableCloudLlmCode('invalid_user_jwt')).toBe(true);
    expect(isNonRetryableCloudLlmCode('turn_timeout')).toBe(false);
  });

  it('normalise invalid_user_jwt comme code chat connu', () => {
    expect(normalizeChatErrorCode('invalid_user_jwt')).toBe('invalid_user_jwt');
  });

  it('regroupe les codes mistral_*', () => {
    expect(isMistralOutageCode('mistral_timeout')).toBe(true);
    expect(isMistralOutageCode('not_subscribed')).toBe(false);
  });
});
