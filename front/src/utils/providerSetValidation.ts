import type { LlmProviderEntry, LlmProviderName, ProviderSet } from '@composables/useDesktop.types';
import type { ChatAttachmentKind } from '#types';
import { isLocalLlmProvider } from '@utils/isLocalLlmProvider';

export type ProviderSetReadinessIssue =
  | 'no_set'
  | 'missing_api_key'
  | 'missing_base_url'
  | 'cloud_not_enrolled'
  | 'not_subscribed'
  | 'quota_exceeded'
  | 'cloud_unreachable';

export interface CloudProviderReadiness {
  enrolled: boolean;
  subscribed?: boolean;
  quotaExceeded?: boolean;
  reachable: boolean;
}

export interface ProviderSetActivationContext {
  cloud?: CloudProviderReadiness | null;
}

export function usesDeviceBearerAuth(set: ProviderSet): boolean {
  return set.authMode === 'device_bearer';
}

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

function blockHasOpenAiCompatBaseUrl(
  provider: LlmProviderName,
  baseUrl: string | null | undefined,
): boolean {
  if (provider !== 'openai_compat') return true;
  return Boolean(baseUrl?.trim());
}

function validateCloudReadiness(
  cloud: CloudProviderReadiness,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!cloud.reachable) return { ok: false, reason: 'cloud_unreachable' };
  if (!cloud.enrolled) return { ok: false, reason: 'cloud_not_enrolled' };
  if (cloud.subscribed === false) return { ok: false, reason: 'not_subscribed' };
  if (cloud.quotaExceeded) return { ok: false, reason: 'quota_exceeded' };
  return { ok: true };
}

/** Vérifie qu'un set peut devenir le set actif effectif (enrollment cloud, clés, URL). */
export function getSetActivationReadiness(
  set: ProviderSet | null,
  ctx?: ProviderSetActivationContext | null,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!set) return { ok: false, reason: 'no_set' };
  if (usesDeviceBearerAuth(set)) {
    if (!ctx?.cloud) {
      return { ok: false, reason: 'cloud_not_enrolled' };
    }
    const cloudCheck = validateCloudReadiness(ctx.cloud);
    if (!cloudCheck.ok) return cloudCheck;
    return { ok: true };
  }
  if (
    !blockHasApiKey(
      set.chat.provider,
      set.chat.baseUrl,
      set.chat.apiKey,
    )
  ) {
    return { ok: false, reason: 'missing_api_key' };
  }
  if (!blockHasOpenAiCompatBaseUrl(set.chat.provider, set.chat.baseUrl)) {
    return { ok: false, reason: 'missing_base_url' };
  }
  return { ok: true };
}

export function canActivateProviderSet(
  set: ProviderSet | null,
  ctx?: ProviderSetActivationContext | null,
): boolean {
  return getSetActivationReadiness(set, ctx).ok;
}

export function setCanReadAttachmentKind(
  set: ProviderSet,
  kind: ChatAttachmentKind,
): boolean {
  const hasVision =
    Boolean(set.capabilities.vision) && set.vision.mode !== 'none';
  const hasOcr = Boolean(set.ocr && set.ocr.mode !== 'none');
  if (kind === 'image') return hasVision;
  return hasOcr || hasVision;
}

/** Choisit un set lisant les pièces jointes et activable avec le contexte courant. */
export function pickActivatableReadingSet(
  sets: ProviderSet[],
  kind: ChatAttachmentKind,
  ctx?: ProviderSetActivationContext | null,
): ProviderSet | null {
  const readingCapable = sets.filter((set) => setCanReadAttachmentKind(set, kind));
  const ready = readingCapable.filter((set) => canActivateProviderSet(set, ctx));
  if (!ready.length) return null;
  return ready.find((set) => set.isDefault) ?? ready[0];
}

/** Vérifie que le set actif peut appeler le chat (clé cloud si requise). */
export function validateProviderSetChatReady(
  set: ProviderSet | null,
  cloud?: CloudProviderReadiness | null,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!set) return { ok: false, reason: 'no_set' };
  if (usesDeviceBearerAuth(set)) {
    // Fail-closed : sans contexte cloud chargé, on refuse (évite d'envoyer
    // avant enrollment / quota). Les callers doivent appeler useCloud().init().
    if (!cloud) {
      return { ok: false, reason: 'cloud_not_enrolled' };
    }
    const cloudCheck = validateCloudReadiness(cloud);
    if (!cloudCheck.ok) return cloudCheck;
    return { ok: true };
  }
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
  cloud?: CloudProviderReadiness | null,
): { ok: true } | { ok: false; reason: ProviderSetReadinessIssue } {
  if (!set?.embeddings) return { ok: true };
  if (usesDeviceBearerAuth(set)) {
    if (!cloud) {
      return { ok: false, reason: 'cloud_not_enrolled' };
    }
    const cloudCheck = validateCloudReadiness(cloud);
    if (!cloudCheck.ok) return cloudCheck;
    return { ok: true };
  }
  const embed = set.embeddings;
  const apiKey = embed.apiKey ?? set.chat.apiKey ?? null;
  if (!blockHasApiKey(embed.provider, embed.baseUrl ?? set.chat.baseUrl, apiKey)) {
    return { ok: false, reason: 'missing_api_key' };
  }
  return { ok: true };
}

export function cloudReadinessFromQuota(
  enrolled: boolean,
  quota: {
    enabled: boolean;
    remainingTokens: number;
    remainingRequests: number;
  } | null,
  reachable: boolean,
): CloudProviderReadiness {
  if (!reachable) {
    return { enrolled, reachable: false };
  }
  if (!enrolled) {
    return { enrolled: false, reachable: true };
  }
  if (!quota) {
    return { enrolled: true, reachable: true };
  }
  if (!quota.enabled) {
    return { enrolled: true, reachable: true, subscribed: false };
  }
  const quotaExceeded = quota.remainingTokens <= 0 || quota.remainingRequests <= 0;
  return {
    enrolled: true,
    reachable: true,
    subscribed: true,
    quotaExceeded,
  };
}
