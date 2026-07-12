import type { ReasoningEffort } from '#types';
import type { LlmConfigPayload } from '@composables/useAppSettings';
import {
  activeChatProvider,
  buildActiveLlmConfigs,
  buildActiveProviderSet,
} from '@composables/useAppSettings';
import type { LlmProviderName } from '@composables/useDesktop.types';
import {
  toChatLlmConfigFromSet,
  toEmbeddingLlmConfigFromSet,
  toUtilityLlmConfigFromSet,
} from '@utils/providerSets';
import {
  clampReasoningEffort,
  defaultReasoningEffort,
  supportsReasoning,
} from '@utils/reasoningSupport';

/** Applique overrides de session sur des configs LLM plates (mode legacy). */
export function mergeLlmConfigsWithSessionReasoning(
  configs: ReturnType<typeof buildActiveLlmConfigs> | null | undefined,
  sessionReasoningEffort?: ReasoningEffort | null,
  sessionModel?: string | null,
): { chat: LlmConfigPayload | null; embedding: LlmConfigPayload | null } {
  if (!configs) {
    return { chat: null, embedding: null };
  }
  if (!configs.chat) return configs;

  const chat: LlmConfigPayload = { ...configs.chat };
  const sessionModelTrimmed = sessionModel?.trim();
  if (sessionModelTrimmed) {
    chat.model = sessionModelTrimmed;
  }

  const provider = chat.provider as LlmProviderName;
  if (!supportsReasoning(provider, chat.model)) {
    delete chat.reasoning_effort;
    return { ...configs, chat };
  }

  const effectiveEffort =
    sessionReasoningEffort ?? chat.reasoning_effort ?? null;
  if (effectiveEffort != null) {
    if (effectiveEffort === 'none') {
      delete chat.reasoning_effort;
    } else {
      const clamped = clampReasoningEffort(
        provider,
        chat.model,
        effectiveEffort,
      );
      if (clamped === 'none') {
        delete chat.reasoning_effort;
      } else {
        chat.reasoning_effort = clamped;
      }
    }
  }

  return { ...configs, chat };
}

/** Configs chat/embedding avec overrides de session (sets ou legacy). */
export function buildSessionAwareLlmConfigs(
  sessionModel?: string | null,
  sessionReasoning?: ReasoningEffort | null,
): { chat: LlmConfigPayload | null; embedding: LlmConfigPayload | null } {
  const providerSet = buildActiveProviderSet(sessionModel, sessionReasoning);
  if (providerSet) {
    return {
      chat: toChatLlmConfigFromSet(providerSet),
      embedding: toEmbeddingLlmConfigFromSet(providerSet),
    };
  }
  return mergeLlmConfigsWithSessionReasoning(
    buildActiveLlmConfigs(),
    sessionReasoning,
    sessionModel,
  );
}

/** Provider set routé pour un appel sidecar (overrides session optionnels). */
export function buildRoutedProviderSet(
  sessionModel?: string | null,
  sessionReasoning?: ReasoningEffort | null,
) {
  return buildActiveProviderSet(sessionModel, sessionReasoning);
}

/** Config LLM utilitaire : petit modèle du preset actif, sans override de session. */
export function buildUtilityLlmConfig(): LlmConfigPayload | null {
  const providerSet = buildActiveProviderSet();
  if (providerSet) {
    return toUtilityLlmConfigFromSet(providerSet);
  }

  const configs = buildActiveLlmConfigs();
  if (!configs.chat) return null;

  const legacy = activeChatProvider.value;
  const utilityModel = legacy?.utilityModel?.trim();
  const chat = { ...configs.chat };
  if (utilityModel) {
    chat.model = utilityModel;
  }
  delete chat.reasoning_effort;
  return chat;
}

/** Effort de raisonnement effectif pour l'UI (set ou legacy + override session). */
export function resolveEffectiveReasoningEffort(
  provider: LlmProviderName,
  model: string,
  sessionReasoning: ReasoningEffort | null | undefined,
  setReasoning: ReasoningEffort | null | undefined,
  legacyReasoning: ReasoningEffort | null | undefined,
): ReasoningEffort {
  if (sessionReasoning != null) {
    return sessionReasoning;
  }
  const fromSet = setReasoning;
  if (fromSet != null) {
    return fromSet;
  }
  if (legacyReasoning != null) {
    return legacyReasoning;
  }
  return defaultReasoningEffort(provider, model);
}
