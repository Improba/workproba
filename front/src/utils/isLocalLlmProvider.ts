import type { LlmProviderEntry } from '@composables/useDesktop.types';

const LOCAL_HOST_RE =
  /^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i;

/** True si le provider chat cible un endpoint local (Ollama, vLLM, API locale). */
export function isLocalLlmProvider(
  entry: LlmProviderEntry | null | undefined,
): boolean {
  if (!entry) return true;
  if (entry.provider === 'ollama' || entry.provider === 'vllm') return true;
  const baseUrl = entry.baseUrl?.trim();
  if (baseUrl && LOCAL_HOST_RE.test(baseUrl)) return true;
  return false;
}
