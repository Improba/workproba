import type { LlmProviderEntry, LlmProviderName, ProviderSet } from '@composables/useDesktop.types';
import { isLocalLlmProvider } from '@utils/isLocalLlmProvider';

export type ProviderSetReadinessIssue = 'no_set' | 'missing_api_key';

export function providerEntryFromSetChat(set: ProviderSet): LlmProviderEntry {
  return {
    id: set.id,
    label: set.name,
    provider: set.chat.provider,
    model: set.chat.model,
    baseUrl: set.chat.baseUrl ?? null,
    apiKey: set.chat.apiKey ?? null,
  };
}

/** True si ce provider cloud nécessite une clé API renseignée dans le set. */
export function providerRequiresApiKey(
  provider: LlmProviderName,
  baseUrl?: string | null,
): boolean {
  return !isLocalLlmProvider({
    id: 'check',
    label: 'check',
    provider,
    model: 'check',
    baseUrl: baseUrl ?? null,
  });
}

function blockHasApiKey(
  provider: LlmProviderName,
  baseUrl: string | null | undefined,
  apiKey: string | null | undefined,
): boolean {
  if (!providerRequiresApiKey(provider, baseUrl)) return true;
  return Boolean(apiKey?.trim());
}

/** Vérifie que le set actif peut appeler le chat (clé cloud si requise). */
export function validateProviderSetChatReady(
  set: ProviderSet | null,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!set) return { ok: false, reason: 'no_set' };
  if (
    !blockHasApiKey(
      set.chat.provider,
      set.chat.baseUrl,
      set.chat.apiKey,
    )
  ) {
    return { ok: false, reason: 'missing_api_key' };
  }
  return { ok: true };
}

/** Vérifie que les embeddings du set sont utilisables (clé cloud si requise). */
export function validateProviderSetEmbeddingsReady(
  set: ProviderSet | null,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!set?.embeddings) return { ok: true };
  const embed = set.embeddings;
  const apiKey = embed.apiKey ?? set.chat.apiKey ?? null;
  if (!blockHasApiKey(embed.provider, embed.baseUrl ?? set.chat.baseUrl, apiKey)) {
    return { ok: false, reason: 'missing_api_key' };
  }
  return { ok: true };
}
