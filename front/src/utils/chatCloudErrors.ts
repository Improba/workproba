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
