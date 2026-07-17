import type {
  LlmProviderEntry,
  LlmProviderName,
  ProviderSet,
  ProviderSetCapabilities,
  ProviderSetChatModel,
  ProviderSetChatReasoning,
} from '@composables/useDesktop.types';
import type { LlmConfigPayload } from '@composables/useAppSettings';
import type { ReasoningEffort } from '#types';
import {
  clampReasoningEffortForSet,
  defaultReasoningEffortForSet,
  supportsReasoningForSet,
} from '@utils/providerSetModels';

const MISTRAL_BASE_URL = 'https://api.mistral.ai/v1';
const OLLAMA_BASE_URL = 'http://127.0.0.1:11434/v1';

const MISTRAL_CHAT_MODELS: ProviderSetChatModel[] = [
  {
    model: 'mistral-small-latest',
    label: 'Mistral Small',
    hint: 'Hybride : chat, code et raisonnement à la demande. Rapide et économique.',
    contextWindow: 256000,
    reasoningEfforts: ['none', 'high'],
  },
  {
    model: 'mistral-medium-latest',
    label: 'Mistral Medium',
    hint: 'Modèle frontier pour agents, code long et workflows multi-étapes.',
    contextWindow: 256000,
    reasoningEfforts: ['none', 'high'],
  },
  {
    model: 'mistral-large-latest',
    label: 'Mistral Large',
    hint: 'Flagship multilingue et multimodal. Qualité maximale.',
    contextWindow: 256000,
    reasoningEfforts: ['none'],
  },
];

export const MISTRAL_BUILTIN_SET: ProviderSet = {
  id: 'mistral-default',
  name: 'Mistral',
  description: 'API Mistral directe. Chat, vision, OCR, embeddings.',
  badges: ['Clé API'],
  authMode: 'api_key',
  chat: {
    provider: 'mistral',
    model: 'mistral-small-latest',
    baseUrl: MISTRAL_BASE_URL,
    apiKeyRef: 'secrets/mistral',
    reasoning: 'auto',
    models: MISTRAL_CHAT_MODELS,
  },
  embeddings: {
    provider: 'mistral',
    model: 'mistral-embed',
    baseUrl: MISTRAL_BASE_URL,
    apiKeyRef: 'secrets/mistral',
  },
  ocr: { provider: 'mistral', mode: 'auto' },
  vision: { mode: 'chat' },
  capabilities: { reasoning: 'medium', vision: true, tools: true, webSearch: true },
  isDefault: false,
  isBuiltin: true,
};

export const WORKPROBA_CLOUD_BUILTIN_SET: ProviderSet = {
  id: 'workproba-cloud',
  name: 'Improba Cloud',
  description: 'Cloud Improba géré. Chat, vision, OCR et embeddings via votre compte.',
  badges: ['Cloud Improba', 'Recommandé'],
  authMode: 'device_bearer',
  chat: {
    // mistral : thinking/reasoning Mistral via le proxy cloud OpenAI-compat.
    provider: 'mistral',
    model: 'mistral-small-latest',
    reasoning: 'auto',
    models: MISTRAL_CHAT_MODELS,
  },
  embeddings: {
    // openai_compat : LiteLLM + api_base vers {cloud}/llm/v1.
    provider: 'openai_compat',
    model: 'mistral-embed',
  },
  ocr: { provider: 'mistral', mode: 'auto' },
  vision: { mode: 'chat' },
  capabilities: {
    reasoning: 'medium',
    vision: true,
    tools: true,
    // Proxy cloud V1 : pas d'API Agents / web search Mistral.
    webSearch: false,
  },
  isDefault: true,
  isBuiltin: true,
  uiModeLocked: true,
};

export const OLLAMA_BUILTIN_SET: ProviderSet = {
  id: 'ollama-local',
  name: 'Ollama local',
  description: '100 % local sur votre machine.',
  badges: ['100 % local'],
  chat: {
    provider: 'ollama',
    model: 'llama3.2',
    baseUrl: OLLAMA_BASE_URL,
    reasoning: 'auto',
  },
  embeddings: {
    provider: 'ollama',
    model: 'nomic-embed-text',
    baseUrl: OLLAMA_BASE_URL,
  },
  ocr: null,
  vision: { mode: 'chat' },
  capabilities: { reasoning: 'low', vision: false, tools: true, webSearch: true },
  isDefault: false,
  isBuiltin: true,
};

export const BUILTIN_PROVIDER_SETS: ProviderSet[] = [
  WORKPROBA_CLOUD_BUILTIN_SET,
  MISTRAL_BUILTIN_SET,
  OLLAMA_BUILTIN_SET,
];

export function cloneProviderSet(set: ProviderSet): ProviderSet {
  return JSON.parse(JSON.stringify(set)) as ProviderSet;
}

export function getBuiltinSets(): ProviderSet[] {
  return BUILTIN_PROVIDER_SETS.map(cloneProviderSet);
}

export function resolveSets(stored: ProviderSet[] | null | undefined): ProviderSet[] {
  if (stored?.length) {
    return stored.map((set) => enrichSetFromBuiltin(cloneProviderSet(set)));
  }
  return getBuiltinSets();
}

/** Complète un set stocké avec le catalogue modèles du builtin homologue (migration douce). */
export function enrichSetFromBuiltin(set: ProviderSet): ProviderSet {
  const template = BUILTIN_PROVIDER_SETS.find((b) => b.id === set.id);

  let enriched = set;
  if (template?.chat.models?.length) {
    if (!set.chat.models?.length) {
      enriched = {
        ...set,
        chat: { ...set.chat, models: template.chat.models },
      };
    } else {
      const templateByModel = new Map(template.chat.models.map((m) => [m.model, m]));
      const mergedModels = set.chat.models.map((stored) => {
        const fresh = templateByModel.get(stored.model);
        return fresh ? { ...stored, ...fresh } : stored;
      });
      for (const fresh of template.chat.models) {
        if (!mergedModels.some((m) => m.model === fresh.model)) {
          mergedModels.push(fresh);
        }
      }
      enriched = {
        ...set,
        chat: { ...set.chat, models: mergedModels },
      };
    }
  }

  if (template) {
    enriched = {
      ...enriched,
      capabilities: {
        ...enriched.capabilities,
        webSearch:
          template.id === 'workproba-cloud'
            ? template.capabilities.webSearch
            : enriched.capabilities.webSearch || template.capabilities.webSearch,
      },
      // Les builtins managés doivent conserver leur mode d'auth (ex. device_bearer),
      // même si un settings.json ancien ne sérialisait pas encore authMode.
      authMode: template.authMode ?? enriched.authMode,
      uiModeLocked: template.uiModeLocked ?? enriched.uiModeLocked,
    };
    if (template.id === 'workproba-cloud') {
      enriched = {
        ...enriched,
        chat: {
          ...enriched.chat,
          provider: template.chat.provider,
        },
        embeddings: enriched.embeddings && template.embeddings
          ? {
              ...enriched.embeddings,
              provider: template.embeddings.provider,
            }
          : enriched.embeddings,
      };
    }
  }

  return enriched;
}

export function resolveActiveSet(
  sets: ProviderSet[],
  activeSetId: string | null | undefined,
): ProviderSet | null {
  if (!sets.length) return null;
  const match = activeSetId ? sets.find((s) => s.id === activeSetId) : null;
  if (match) return cloneProviderSet(match);
  const defaultSet = sets.find((s) => s.isDefault) ?? sets[0];
  return defaultSet ? cloneProviderSet(defaultSet) : null;
}

function chatReasoningToEffort(
  reasoning: ProviderSetChatReasoning | undefined,
): ReasoningEffort | null {
  if (!reasoning || reasoning === 'auto') return null;
  if (reasoning === 'none') return 'none';
  return reasoning;
}

export function toChatLlmConfigFromSet(set: ProviderSet | null): LlmConfigPayload | null {
  if (!set) return null;
  const chat = set.chat;
  const payload: LlmConfigPayload = {
    provider: chat.provider,
    model: chat.model,
    base_url: chat.baseUrl ?? null,
    api_key: chat.apiKey ?? null,
    extra_headers: {},
  };
  const effort = chatReasoningToEffort(chat.reasoning);
  if (effort && effort !== 'none' && supportsReasoningForSet(set, chat.model)) {
    const clamped = clampReasoningEffortForSet(set, chat.model, effort);
    if (clamped !== 'none') {
      payload.reasoning_effort = clamped;
    }
  }
  return payload;
}

export function toEmbeddingLlmConfigFromSet(set: ProviderSet | null): LlmConfigPayload | null {
  if (!set?.embeddings) return null;
  const embed = set.embeddings;
  return {
    provider: embed.provider,
    model: embed.model,
    base_url: embed.baseUrl ?? null,
    api_key: embed.apiKey ?? set.chat.apiKey ?? null,
    extra_headers: {},
  };
}

/** Config LLM utilitaire (titre, résumé) : preset sans override session ni raisonnement.
 *  Pour ``device_bearer`` (Improba Cloud), retourne null : le sidecar doit recevoir
 *  le provider_set + cloud_plugin_data_dir pour injecter le DeviceBearer.
 */
export function toUtilityLlmConfigFromSet(set: ProviderSet | null): LlmConfigPayload | null {
  if (!set) return null;
  if (set.authMode === 'device_bearer') return null;
  const chat = set.chat;
  return {
    provider: chat.provider,
    model: chat.model,
    base_url: chat.baseUrl ?? null,
    api_key: chat.apiKey ?? null,
    extra_headers: {},
  };
}

/** Applique clé API saisie aux blocs chat/embeddings d'un set (mode guidé). */
export function applyAccessKeyToSet(set: ProviderSet, apiKey: string | null): ProviderSet {
  const next = cloneProviderSet(set);
  const trimmed = apiKey?.trim() || null;
  next.chat = { ...next.chat, apiKey: trimmed };
  if (next.embeddings) {
    next.embeddings = { ...next.embeddings, apiKey: trimmed };
  }
  return next;
}

export function applyOllamaOverrides(
  set: ProviderSet,
  baseUrl: string,
  model: string,
): ProviderSet {
  const next = cloneProviderSet(set);
  const normalizedBase = baseUrl.trim() || 'http://127.0.0.1:11434/v1';
  next.chat = {
    ...next.chat,
    baseUrl: normalizedBase.endsWith('/v1')
      ? normalizedBase
      : `${normalizedBase.replace(/\/$/, '')}/v1`,
    model: model.trim() || next.chat.model,
  };
  if (next.embeddings) {
    next.embeddings = {
      ...next.embeddings,
      baseUrl: next.chat.baseUrl,
    };
  }
  return next;
}

export function applySessionOverridesToSet(
  set: ProviderSet,
  sessionModel?: string | null,
  sessionReasoning?: ReasoningEffort | null,
): ProviderSet {
  const next = cloneProviderSet(set);
  const modelTrimmed = sessionModel?.trim();
  if (modelTrimmed) {
    next.chat = { ...next.chat, model: modelTrimmed };
  }
  const effectiveModel = next.chat.model;

  if (sessionReasoning != null) {
    if (supportsReasoningForSet(next, effectiveModel)) {
      const clamped = clampReasoningEffortForSet(
        next,
        effectiveModel,
        sessionReasoning,
      );
      next.chat = {
        ...next.chat,
        reasoning: clamped,
      };
    } else {
      next.chat = { ...next.chat, reasoning: 'none' };
    }
  } else if (!supportsReasoningForSet(next, effectiveModel)) {
    next.chat = { ...next.chat, reasoning: 'none' };
  } else if (
    next.chat.reasoning &&
    next.chat.reasoning !== 'auto' &&
    next.chat.reasoning !== 'none'
  ) {
    const clamped = clampReasoningEffortForSet(
      next,
      effectiveModel,
      next.chat.reasoning,
    );
    next.chat = { ...next.chat, reasoning: clamped };
  }
  return next;
}

/** Effort effectif pour l'UI après overrides session (modèle + raisonnement). */
export function effectiveReasoningEffortFromSet(
  set: ProviderSet,
  sessionModel?: string | null,
  sessionReasoning?: ReasoningEffort | null,
): ReasoningEffort {
  const routed = applySessionOverridesToSet(set, sessionModel, sessionReasoning);
  const model = routed.chat.model;
  const reasoning = routed.chat.reasoning;
  if (!reasoning || reasoning === 'auto') {
    return defaultReasoningEffortForSet(routed, model);
  }
  if (reasoning === 'none') return 'none';
  return clampReasoningEffortForSet(routed, model, reasoning);
}

export function inferBuiltinSetIdFromProvider(entry: LlmProviderEntry | null): string {
  if (!entry) return MISTRAL_BUILTIN_SET.id;
  if (entry.provider === 'ollama') return OLLAMA_BUILTIN_SET.id;
  return MISTRAL_BUILTIN_SET.id;
}

/** Migre les providers plats V1 vers des sets (clés API copiées). */
export function migrateLegacyProvidersToSets(
  providers: LlmProviderEntry[],
  activeChatProviderId: string | null | undefined,
): { sets: ProviderSet[]; activeSetId: string } {
  const sets = getBuiltinSets();
  const activeEntry =
    providers.find((p) => p.id === activeChatProviderId) ?? providers[0] ?? null;
  const activeSetId = inferBuiltinSetIdFromProvider(activeEntry);
  const apiKey = activeEntry?.apiKey ?? null;
  const baseUrl = activeEntry?.baseUrl ?? null;
  const model = activeEntry?.model ?? null;

  const migrated = sets.map((set) => {
    if (set.id !== activeSetId) return set;
    let next = applyAccessKeyToSet(set, apiKey);
    if (set.id === OLLAMA_BUILTIN_SET.id && (baseUrl || model)) {
      next = applyOllamaOverrides(
        next,
        baseUrl ?? 'http://127.0.0.1:11434',
        model ?? next.chat.model,
      );
    } else if (model) {
      next = { ...next, chat: { ...next.chat, model } };
    }
    return next;
  });

  return { sets: migrated, activeSetId };
}

export function newCustomSetId(): string {
  return `set_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

export function emptyCustomSet(): ProviderSet {
  return {
    id: newCustomSetId(),
    name: '',
    description: '',
    badges: [],
    chat: {
      provider: 'mistral',
      model: 'mistral-small-latest',
      baseUrl: MISTRAL_BASE_URL,
      reasoning: 'auto',
    },
    embeddings: {
      provider: 'mistral',
      model: 'mistral-embed',
      baseUrl: MISTRAL_BASE_URL,
    },
    ocr: { provider: 'mistral', mode: 'auto' },
    vision: { mode: 'chat' },
    capabilities: { reasoning: 'medium', vision: true, tools: true, webSearch: true },
    isDefault: false,
    isBuiltin: false,
  };
}

export type CapabilityLabelMode = 'guided' | 'advanced';

/** Nom affiché d'un set intégré (i18n) ou nom stocké pour les sets custom. */
export function localizedSetName(
  set: ProviderSet,
  t: (key: string) => string,
): string {
  if (set.id === 'workproba-cloud') return t('settings.engine.cloudName');
  if (set.id === 'mistral-default') return t('settings.engine.mistralName');
  if (set.id === 'ollama-local') return t('settings.engine.ollamaName');
  return set.name;
}

/** Libellé preset en mode guidé (titlebar) : Improba Cloud, Mistral, Ollama local, etc. */
export function guidedPresetLabel(
  set: ProviderSet,
  t: (key: string) => string,
): string {
  if (set.id === 'workproba-cloud') {
    return t('settings.engine.cloudName');
  }
  if (set.id === 'mistral-default' || set.chat.provider === 'mistral') {
    return t('settings.engine.mistralName');
  }
  if (set.id === 'ollama-local' || set.chat.provider === 'ollama') {
    return t('settings.engine.ollamaName');
  }
  return localizedSetName(set, t);
}

/** Description affichée d'un set intégré (i18n) ou description stockée. */
export function localizedSetDescription(
  set: ProviderSet,
  t: (key: string) => string,
): string {
  if (set.id === 'workproba-cloud') return t('settings.engine.cloudDescription');
  if (set.id === 'mistral-default') return t('settings.engine.mistralDescription');
  if (set.id === 'ollama-local') return t('settings.engine.ollamaDescription');
  return set.description;
}

export function capabilityLabels(
  set: ProviderSet,
  mode: CapabilityLabelMode,
  t: (key: string) => string,
): string[] {
  const caps = set.capabilities;
  const labels: string[] = [];
  if (mode === 'guided') {
    if (caps.vision && set.vision.mode === 'chat') {
      labels.push(t('settings.engine.capabilityVision'));
    }
    if (set.ocr && set.ocr.mode !== 'none') {
      labels.push(t('settings.engine.capabilityPdfScanned'));
    }
    if (set.embeddings) {
      labels.push(t('settings.engine.capabilityMemory'));
    }
    if (caps.reasoning === 'high' || caps.reasoning === 'medium') {
      labels.push(t('settings.engine.capabilityReasoning'));
    }
    if (caps.tools) {
      labels.push(t('settings.engine.capabilityTools'));
    }
    if (caps.webSearch) {
      labels.push(t('settings.engine.capabilityWebSearch'));
    }
    return labels;
  }

  if (caps.vision) labels.push('vision');
  if (set.ocr && set.ocr.mode !== 'none') labels.push('OCR');
  if (set.embeddings) labels.push('embeddings');
  if (caps.reasoning) labels.push(`reasoning:${caps.reasoning}`);
  if (caps.tools) labels.push('tools');
  if (caps.webSearch) labels.push('web_search');
  return labels;
}

export function providerSetToSidecar(set: ProviderSet): Record<string, unknown> {
  const chat: Record<string, unknown> = {
    provider: set.chat.provider,
    model: set.chat.model,
    reasoning: set.chat.reasoning ?? 'auto',
  };
  if (set.chat.apiKeyRef) chat.api_key_ref = set.chat.apiKeyRef;
  if (set.chat.apiKey) chat.api_key = set.chat.apiKey;
  if (set.chat.baseUrl) chat.base_url = set.chat.baseUrl;
  if (set.chat.models?.length) {
    chat.models = set.chat.models.map((m) => {
      const entry: Record<string, unknown> = {
        model: m.model,
        label: m.label,
      };
      if (m.hint) entry.hint = m.hint;
      if (m.contextWindow != null) entry.context_window = m.contextWindow;
      if (m.reasoningEfforts?.length) entry.reasoning_efforts = m.reasoningEfforts;
      return entry;
    });
  }

  const payload: Record<string, unknown> = {
    id: set.id,
    name: set.name,
    description: set.description,
    badges: set.badges,
    chat,
    vision: { mode: set.vision.mode },
    capabilities: {
      reasoning: set.capabilities.reasoning,
      vision: set.capabilities.vision,
      tools: set.capabilities.tools,
      web_search: set.capabilities.webSearch,
    },
    is_default: set.isDefault,
    is_builtin: set.isBuiltin,
  };

  if (set.authMode) payload.auth_mode = set.authMode;
  if (set.uiModeLocked) payload.ui_mode_locked = set.uiModeLocked;

  if (set.embeddings) {
    const embed: Record<string, unknown> = {
      provider: set.embeddings.provider,
      model: set.embeddings.model,
    };
    if (set.embeddings.apiKeyRef) embed.api_key_ref = set.embeddings.apiKeyRef;
    if (set.embeddings.apiKey) embed.api_key = set.embeddings.apiKey;
    if (set.embeddings.baseUrl) embed.base_url = set.embeddings.baseUrl;
    payload.embeddings = embed;
  } else {
    payload.embeddings = null;
  }

  if (set.ocr) {
    payload.ocr = { provider: set.ocr.provider, mode: set.ocr.mode };
  } else {
    payload.ocr = null;
  }

  return payload;
}

function isSidecarProviderSetShape(raw: Record<string, unknown>): boolean {
  return (
    'is_default' in raw ||
    'is_builtin' in raw ||
    (typeof raw.chat === 'object' &&
      raw.chat !== null &&
      ('api_key_ref' in (raw.chat as object) ||
        'base_url' in (raw.chat as object) ||
        (Array.isArray((raw.chat as Record<string, unknown>).models) &&
          (raw.chat as Record<string, unknown>).models?.[0] != null &&
          typeof (raw.chat as Record<string, unknown>).models?.[0] === 'object' &&
          'context_window' in ((raw.chat as Record<string, unknown>).models as object[])[0])))
  );
}

/** Normalise un set stocké (Tauri camelCase ou sidecar snake_case). */
export function normalizeStoredSet(raw: ProviderSet | Record<string, unknown>): ProviderSet {
  if (isSidecarProviderSetShape(raw as Record<string, unknown>)) {
    return enrichSetFromBuiltin(sidecarSetToProviderSet(raw as Record<string, unknown>));
  }
  if ('chat' in raw && raw.chat && typeof raw.chat === 'object' && 'provider' in (raw.chat as object)) {
    const set = raw as ProviderSet;
    return enrichSetFromBuiltin({
      ...cloneProviderSet(set),
      vision: set.vision ?? { mode: 'none' },
      capabilities: set.capabilities ?? { reasoning: 'medium', vision: false, tools: true, webSearch: false },
    });
  }
  return enrichSetFromBuiltin(sidecarSetToProviderSet(raw as Record<string, unknown>));
}

export function sidecarSetToProviderSet(raw: Record<string, unknown>): ProviderSet {
  const chatRaw = (raw.chat ?? {}) as Record<string, unknown>;
  const capsRaw = (raw.capabilities ?? {}) as Record<string, unknown>;
  const visionRaw = (raw.vision ?? {}) as Record<string, unknown>;
  const embedRaw = raw.embeddings as Record<string, unknown> | null | undefined;
  const ocrRaw = raw.ocr as Record<string, unknown> | null | undefined;

  const modelsRaw = chatRaw.models;
  const models: ProviderSetChatModel[] | undefined = Array.isArray(modelsRaw)
    ? modelsRaw.map((item) => {
        const m = item as Record<string, unknown>;
        const effortsRaw = m.reasoning_efforts ?? m.reasoningEfforts;
        const reasoningEfforts = Array.isArray(effortsRaw)
          ? effortsRaw.map(String).filter((e): e is ReasoningEffort =>
              ['none', 'low', 'medium', 'high'].includes(e),
            )
          : undefined;
        return {
          model: String(m.model ?? ''),
          label: String(m.label ?? m.model ?? ''),
          hint: m.hint ? String(m.hint) : undefined,
          contextWindow:
            m.context_window != null || m.contextWindow != null
              ? Number(m.context_window ?? m.contextWindow)
              : undefined,
          reasoningEfforts,
        };
      })
    : undefined;

  return {
    id: String(raw.id ?? ''),
    name: String(raw.name ?? ''),
    description: String(raw.description ?? ''),
    badges: Array.isArray(raw.badges) ? raw.badges.map(String) : [],
    chat: {
      provider: String(chatRaw.provider ?? 'mistral') as LlmProviderName,
      model: String(chatRaw.model ?? ''),
      apiKeyRef: chatRaw.api_key_ref ?? chatRaw.apiKeyRef ? String(chatRaw.api_key_ref ?? chatRaw.apiKeyRef) : null,
      apiKey: chatRaw.api_key ?? chatRaw.apiKey ? String(chatRaw.api_key ?? chatRaw.apiKey) : null,
      baseUrl: chatRaw.base_url ?? chatRaw.baseUrl ? String(chatRaw.base_url ?? chatRaw.baseUrl) : null,
      reasoning: (chatRaw.reasoning as ProviderSetChatReasoning | undefined) ?? 'auto',
      models,
    },
    embeddings: embedRaw
      ? {
          provider: String(embedRaw.provider ?? 'mistral') as LlmProviderName,
          model: String(embedRaw.model ?? ''),
          apiKeyRef: embedRaw.api_key_ref ?? embedRaw.apiKeyRef ? String(embedRaw.api_key_ref ?? embedRaw.apiKeyRef) : null,
          apiKey: embedRaw.api_key ?? embedRaw.apiKey ? String(embedRaw.api_key ?? embedRaw.apiKey) : null,
          baseUrl: embedRaw.base_url ?? embedRaw.baseUrl ? String(embedRaw.base_url ?? embedRaw.baseUrl) : null,
        }
      : null,
    ocr: ocrRaw
      ? {
          provider: (ocrRaw.provider === 'docling' ? 'docling' : 'mistral') as 'mistral' | 'docling',
          mode: (ocrRaw.mode === 'none' ? 'none' : 'auto') as 'auto' | 'none',
        }
      : null,
    vision: {
      mode: (visionRaw.mode === 'chat' ? 'chat' : 'none') as 'chat' | 'none',
    },
    capabilities: {
      reasoning: (['low', 'medium', 'high'].includes(String(capsRaw.reasoning))
        ? capsRaw.reasoning
        : 'medium') as ProviderSetCapabilities['reasoning'],
      vision: Boolean(capsRaw.vision),
      tools: capsRaw.tools !== false,
      webSearch: Boolean(capsRaw.web_search ?? capsRaw.webSearch),
    },
    isDefault: Boolean(raw.is_default ?? raw.isDefault),
    isBuiltin: Boolean(raw.is_builtin ?? raw.isBuiltin),
    authMode:
      raw.auth_mode === 'device_bearer' || raw.authMode === 'device_bearer'
        ? 'device_bearer'
        : 'api_key',
    uiModeLocked: Boolean(raw.ui_mode_locked ?? raw.uiModeLocked),
  };
}
