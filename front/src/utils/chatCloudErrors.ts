/** Codes cloud LLM non éligibles au retry automatique. */
export const NON_RETRYABLE_CLOUD_LLM_CODES = new Set([
  'cloud_not_enrolled',
  'not_subscribed',
  'quota_exceeded',
  'cloud_unreachable',
  'mistral_unavailable',
  'mistral_timeout',
  'mistral_upstream_error',
  'unsupported_model',
  'bad_request',
  'bearer_token_required',
  'invalid_user_jwt',
  'invalid_device_token',
  'device_organization_required',
  'org_id_required',
]);

export function isNonRetryableCloudLlmCode(code: string): boolean {
  return NON_RETRYABLE_CLOUD_LLM_CODES.has(code);
}

export function isMistralOutageCode(code: string): boolean {
  return (
    code === 'mistral_unavailable'
    || code === 'mistral_timeout'
    || code === 'mistral_upstream_error'
  );
}

export function chatErrorReconnectCta(code: string): 'login' | 'enroll' | null {
  if (code === 'invalid_user_jwt') return 'login';
  if (
    code === 'invalid_device_token' ||
    code === 'bearer_token_required' ||
    code === 'cloud_not_enrolled'
  ) {
    return 'enroll';
  }
  return null;
}

/** Efface les erreurs inline reconnectables sur les messages assistant. */
export function clearReconnectableChatErrors(
  messages: Array<{ role: string; error?: { code?: string } | null }>,
): void {
  for (const message of messages) {
    if (message.role !== 'assistant') continue;
    const code = message.error?.code;
    if (!code || !chatErrorReconnectCta(code)) continue;
    message.error = null;
  }
}
