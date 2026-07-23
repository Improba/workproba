import { describe, expect, it } from 'vitest';
import { normalizeChatErrorCode } from '#types';
import {
  chatErrorReconnectCta,
  clearReconnectableChatErrors,
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

  it('dérive le CTA reconnect depuis le code erreur', () => {
    expect(chatErrorReconnectCta('invalid_user_jwt')).toBe('login');
    expect(chatErrorReconnectCta('cloud_not_enrolled')).toBe('enroll');
    expect(chatErrorReconnectCta('invalid_device_token')).toBe('enroll');
    expect(chatErrorReconnectCta('bearer_token_required')).toBe('enroll');
    expect(chatErrorReconnectCta('quota_exceeded')).toBeNull();
  });

  it('efface uniquement les erreurs inline reconnectables', () => {
    const messages = [
      {
        id: 'u1',
        role: 'user',
        error: { code: 'invalid_user_jwt', message: 'x' },
      },
      {
        id: 'a1',
        role: 'assistant',
        error: { code: 'invalid_user_jwt', message: 'Session expirée' },
      },
      {
        id: 'a2',
        role: 'assistant',
        error: { code: 'cloud_not_enrolled', message: 'Non inscrit' },
      },
      {
        id: 'a3',
        role: 'assistant',
        error: { code: 'sidecar_unreachable', message: 'Sidecar down' },
      },
      {
        id: 'a4',
        role: 'assistant',
        error: { code: 'unknown', message: 'Erreur' },
      },
      {
        id: 'a5',
        role: 'assistant',
        error: null,
      },
    ];

    clearReconnectableChatErrors(messages);

    expect(messages[0].error).toEqual({ code: 'invalid_user_jwt', message: 'x' });
    expect(messages[1].error).toBeNull();
    expect(messages[2].error).toBeNull();
    expect(messages[3].error).toEqual({
      code: 'sidecar_unreachable',
      message: 'Sidecar down',
    });
    expect(messages[4].error).toEqual({ code: 'unknown', message: 'Erreur' });
    expect(messages[5].error).toBeNull();
  });
});
