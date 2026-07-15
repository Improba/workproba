import { computed, ref } from 'vue';
import {
  getAppSettings,
  isDesktopApp,
  saveAppSettings,
  type AppSettings,
  type AppLocale,
  type LlmProviderEntry,
  type ProviderSet,
} from '@composables/useDesktop';
import type { DensityMode, LlmProviderName, SettingsMode, ToolCallViewMode } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import { getAiSidecarUrl, getDesktopSecret } from '@services/aiSidecar';
import { isLocalLlmProvider } from '@utils/isLocalLlmProvider';
import { clampReasoningEffort, supportsReasoning, defaultReasoningEffort } from '@utils/reasoningSupport';
import {
  clampReasoningEffortForSet,
  defaultReasoningEffortForSet,
  supportsReasoningForSet,
} from '@utils/providerSetModels';
import { normalizeLocale, resolveInitialLocale, setLang } from '@boot/i18n';
import { t } from '@utils/i18nT';
import type { UiThemeId } from '@utils/uiTheme';
import { isUiThemeId, resolveInitialUiTheme, writeCachedUiTheme } from '@utils/uiTheme';
import {
  applySessionOverridesToSet,
  migrateLegacyProvidersToSets,
  normalizeStoredSet,
  providerSetToSidecar,
  resolveActiveSet,
  resolveSets,
  toChatLlmConfigFromSet,
  toEmbeddingLlmConfigFromSet,
} from '@utils/providerSets';

/** Payload de config LLM attendu par le sidecar (snake_case, cf. app/schemas.py). */
export interface LlmConfigPayload {
  provider: string;
  model: string;
  base_url?: string | null;
  api_key?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  extra_headers?: Record<string, string>;
  reasoning_effort?: ReasoningEffort | null;
}

export interface LlmTestResult {
  ok: boolean;
  detail: string;
  modelCount?: number | null;
}

export interface ProviderSetTestResult {
  chat: { ok: boolean; detail?: string; models?: string[] | null };
  embeddings: { ok: boolean; detail?: string };
  ocr: { ok: boolean; supported: boolean; detail?: string };
  vision: { ok: boolean; supported: boolean; detail?: string };
}

const ONBOARDING_DONE_KEY = 'workproba:onboardingDone';

const settings = ref<AppSettings>({ version: 1, providers: [], density: 'comfortable' });
const loaded = ref(false);
/** Invalide un load() en cours si save() ou un load() plus récent a modifié les réglages. */
let loadGeneration = 0;

function readOnboardingDone(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(ONBOARDING_DONE_KEY) === 'true';
}

function persistOnboardingDone(done: boolean): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(ONBOARDING_DONE_KEY, String(done));
}

function ensureSetsLoaded(value: AppSettings): AppSettings {
  if (value.sets?.length) {
    const normalizedSets = value.sets.map((s) => normalizeStoredSet(s));
    return {
      ...value,
      sets: normalizedSets,
      activeSetId:
        value.activeSetId ??
        normalizedSets.find((s) => s.isDefault)?.id ??
        normalizedSets[0]?.id,
    };
  }
  const migrated = migrateLegacyProvidersToSets(
    value.providers ?? [],
    value.activeChatProviderId,
  );
  return {
    ...value,
    sets: migrated.sets,
    activeSetId: migrated.activeSetId,
  };
}

const providers = computed(() => settings.value.providers);

const sets = computed(() => resolveSets(settings.value.sets));

const activeSet = computed<ProviderSet | null>(() =>
  resolveActiveSet(sets.value, settings.value.activeSetId),
);

const activeChatProvider = computed<LlmProviderEntry | null>(() => {
  const id = settings.value.activeChatProviderId;
  return providers.value.find((p) => p.id === id) ?? null;
});

const activeEmbeddingProvider = computed<LlmProviderEntry | null>(() => {
  const id = settings.value.activeEmbeddingProviderId;
  return providers.value.find((p) => p.id === id) ?? null;
});

const toolCallView = computed<ToolCallViewMode>(
  () => settings.value.toolCallView ?? 'human',
);

const onboardingDone = computed<boolean>(
  () => settings.value.onboardingDone ?? false,
);

const settingsMode = computed<SettingsMode>(
  () => settings.value.settingsMode ?? 'guided',
);

const settingsLocked = computed<boolean>(
  () => settings.value.settingsLocked ?? false,
);

const permissionsNetwork = computed<boolean>(
  () => settings.value.permissionsNetwork !== false,
);

const density = computed<DensityMode>(
  () => settings.value.density ?? 'comfortable',
);

const uiTheme = computed<UiThemeId>(() =>
  resolveInitialUiTheme(settings.value.uiTheme ?? null),
);

const locale = computed<AppLocale>(
  () => settings.value.locale ?? resolveInitialLocale(),
);

const localeLocked = computed<boolean>(
  () => settings.value.localeLocked ?? false,
);

const isLocalChatProvider = computed(() => {
  const set = activeSet.value;
  if (set) return isLocalLlmProvider({ provider: set.chat.provider } as LlmProviderEntry);
  return isLocalLlmProvider(activeChatProvider.value);
});

export interface ActiveChatRouting {
  provider: LlmProviderName;
  model: string;
  label: string;
  defaultReasoning: ReasoningEffort;
}

function reasoningFromSetChat(
  reasoning: import('@composables/useDesktop.types').ProviderSetChatReasoning | undefined,
  set: ProviderSet,
  model: string,
): ReasoningEffort {
  if (!reasoning || reasoning === 'auto') {
    return defaultReasoningEffortForSet(set, model);
  }
  if (reasoning === 'none') return 'none';
  return clampReasoningEffortForSet(set, model, reasoning);
}

/** Provider/modèle chat effectifs (set actif ou legacy). */
const activeChatRouting = computed<ActiveChatRouting | null>(() => {
  const set = activeSet.value;
  if (set) {
    const chat = set.chat;
    return {
      provider: chat.provider,
      model: chat.model,
      label: set.name,
      defaultReasoning: reasoningFromSetChat(chat.reasoning, set, chat.model),
    };
  }
  const legacy = activeChatProvider.value;
  if (!legacy) return null;
  return {
    provider: legacy.provider,
    model: legacy.model,
    label: legacy.label,
    defaultReasoning:
      legacy.reasoningEffort ?? defaultReasoningEffort(legacy.provider, legacy.model),
  };
});

export function toChatLlmConfig(entry: LlmProviderEntry | null): LlmConfigPayload | null {
  if (!entry) return null;
  const payload: LlmConfigPayload = {
    provider: entry.provider,
    model: entry.model,
    base_url: entry.baseUrl ?? null,
    api_key: entry.apiKey ?? null,
    temperature: entry.temperature ?? null,
    max_tokens: entry.maxTokens ?? null,
    extra_headers: entry.extraHeaders ?? {},
  };
  if (
    entry.reasoningEffort &&
    entry.reasoningEffort !== 'none' &&
    supportsReasoning(entry.provider, entry.model)
  ) {
    const clamped = clampReasoningEffort(
      entry.provider,
      entry.model,
      entry.reasoningEffort,
    );
    if (clamped !== 'none') {
      payload.reasoning_effort = clamped;
    }
  }
  return payload;
}

export function toEmbeddingLlmConfig(
  entry: LlmProviderEntry | null,
): LlmConfigPayload | null {
  if (!entry || !entry.embeddingModel) return null;
  return {
    provider: entry.provider,
    model: entry.embeddingModel,
    base_url: entry.embeddingBaseUrl ?? entry.baseUrl ?? null,
    api_key: entry.apiKey ?? null,
  };
}

/** Set actif pour un tour agent (overrides session optionnels). */
export function buildActiveProviderSet(
  sessionModel?: string | null,
  sessionReasoning?: ReasoningEffort | null,
): ProviderSet | null {
  const base = activeSet.value;
  if (!base) return null;
  return applySessionOverridesToSet(base, sessionModel, sessionReasoning);
}

/** Construit les deux configs (chat + embeddings) depuis le set actif ou legacy. */
export function buildActiveLlmConfigs(): {
  chat: LlmConfigPayload | null;
  embedding: LlmConfigPayload | null;
} {
  const set = activeSet.value;
  if (set) {
    return {
      chat: toChatLlmConfigFromSet(set),
      embedding: toEmbeddingLlmConfigFromSet(set),
    };
  }
  return {
    chat: toChatLlmConfig(activeChatProvider.value),
    embedding: toEmbeddingLlmConfig(activeEmbeddingProvider.value),
  };
}

export async function testLlmConfig(
  config: LlmConfigPayload,
): Promise<LlmTestResult> {
  const response = await fetch(`${getAiSidecarUrl()}/llm/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    return {
      ok: false,
      detail: `HTTP ${response.status} ${body}`.trim(),
    };
  }

  const data = (await response.json()) as {
    ok: boolean;
    detail: string;
    model_count?: number | null;
  };
  return {
    ok: Boolean(data.ok),
    detail: String(data.detail ?? ''),
    modelCount: data.model_count ?? null,
  };
}

export async function testSet(set: ProviderSet): Promise<ProviderSetTestResult> {
  const response = await fetch(`${getAiSidecarUrl()}/llm/sets/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify(providerSetToSidecar(set)),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`HTTP ${response.status} ${body}`.trim());
  }

  const data = (await response.json()) as ProviderSetTestResult;
  return data;
}

export interface UseAppSettingsReturn {
  settings: typeof settings;
  loaded: typeof loaded;
  providers: typeof providers;
  sets: typeof sets;
  activeSet: typeof activeSet;
  activeChatRouting: typeof activeChatRouting;
  activeChatProvider: typeof activeChatProvider;
  activeEmbeddingProvider: typeof activeEmbeddingProvider;
  toolCallView: typeof toolCallView;
  onboardingDone: typeof onboardingDone;
  settingsMode: typeof settingsMode;
  settingsLocked: typeof settingsLocked;
  permissionsNetwork: typeof permissionsNetwork;
  density: typeof density;
  uiTheme: typeof uiTheme;
  locale: typeof locale;
  localeLocked: typeof localeLocked;
  isLocalChatProvider: typeof isLocalChatProvider;
  load: () => Promise<AppSettings>;
  save: (next: AppSettings) => Promise<AppSettings>;
  setActiveSet: (id: string) => Promise<AppSettings>;
  createSet: (set: ProviderSet) => Promise<AppSettings>;
  updateSet: (set: ProviderSet) => Promise<AppSettings>;
  deleteSet: (id: string) => Promise<AppSettings>;
  setToolCallView: (view: ToolCallViewMode) => Promise<AppSettings>;
  setOnboardingDone: (done: boolean) => Promise<void>;
  setSettingsMode: (mode: SettingsMode) => Promise<AppSettings>;
  setDensity: (mode: DensityMode) => Promise<AppSettings>;
  setUiTheme: (themeId: UiThemeId) => Promise<AppSettings>;
  setLocale: (nextLocale: AppLocale) => Promise<AppSettings>;
}

export function useAppSettings(): UseAppSettingsReturn {
  async function load(): Promise<AppSettings> {
    const gen = loadGeneration;
    const value = await getAppSettings();
    if (gen !== loadGeneration) {
      loaded.value = true;
      return settings.value;
    }
    const storedLocale = normalizeLocale(value.locale ?? undefined);
    const resolvedLocale = storedLocale ?? resolveInitialLocale();
    const resolvedUiTheme = resolveInitialUiTheme(
      value.uiTheme && isUiThemeId(value.uiTheme) ? value.uiTheme : null,
    );
    settings.value = ensureSetsLoaded({
      ...value,
      uiTheme: resolvedUiTheme,
      locale: resolvedLocale,
      onboardingDone: readOnboardingDone(),
    });
    writeCachedUiTheme(resolvedUiTheme);
    setLang(resolvedLocale);
    loaded.value = true;
    return settings.value;
  }

  async function save(next: AppSettings): Promise<AppSettings> {
    loadGeneration += 1;
    const previous = settings.value;
    const prepared = ensureSetsLoaded(next);
    settings.value = prepared;
    if (prepared.uiTheme && isUiThemeId(prepared.uiTheme)) {
      writeCachedUiTheme(prepared.uiTheme);
    }
    if (!isDesktopApp()) {
      return prepared;
    }
    try {
      const persisted = await saveAppSettings(prepared);
      settings.value = persisted;
      if (persisted.uiTheme && isUiThemeId(persisted.uiTheme)) {
        writeCachedUiTheme(persisted.uiTheme);
      }
      return persisted;
    } catch (error) {
      settings.value = previous;
      if (previous.uiTheme && isUiThemeId(previous.uiTheme)) {
        writeCachedUiTheme(previous.uiTheme);
      }
      throw error;
    }
  }

  async function setActiveSet(id: string): Promise<AppSettings> {
    const currentSets = resolveSets(settings.value.sets);
    if (!currentSets.some((s) => s.id === id)) {
      throw new Error(t('settings.advancedSetNotFound'));
    }
    return save({ ...settings.value, activeSetId: id });
  }

  async function createSet(set: ProviderSet): Promise<AppSettings> {
    const currentSets = resolveSets(settings.value.sets);
    return save({
      ...settings.value,
      sets: [...currentSets, set],
      activeSetId: settings.value.activeSetId ?? set.id,
    });
  }

  async function updateSet(set: ProviderSet): Promise<AppSettings> {
    const currentSets = resolveSets(settings.value.sets);
    const idx = currentSets.findIndex((s) => s.id === set.id);
    if (idx < 0) throw new Error(t('settings.advancedSetNotFound'));
    const nextSets = [...currentSets];
    nextSets[idx] = set;
    return save({ ...settings.value, sets: nextSets });
  }

  async function deleteSet(id: string): Promise<AppSettings> {
    const currentSets = resolveSets(settings.value.sets);
    const target = currentSets.find((s) => s.id === id);
    if (!target) throw new Error(t('settings.advancedSetNotFound'));
    if (target.isBuiltin) throw new Error(t('settings.advancedCannotDeleteBuiltin'));
    const nextSets = currentSets.filter((s) => s.id !== id);
    let activeSetId = settings.value.activeSetId ?? null;
    if (activeSetId === id) {
      activeSetId = nextSets.find((s) => s.isDefault)?.id ?? nextSets[0]?.id ?? null;
    }
    return save({ ...settings.value, sets: nextSets, activeSetId });
  }

  async function setToolCallView(view: ToolCallViewMode): Promise<AppSettings> {
    return save({ ...settings.value, toolCallView: view });
  }

  async function setSettingsMode(mode: SettingsMode): Promise<AppSettings> {
    return save({ ...settings.value, settingsMode: mode });
  }

  async function setDensity(mode: DensityMode): Promise<AppSettings> {
    return save({ ...settings.value, density: mode });
  }

  async function setUiTheme(themeId: UiThemeId): Promise<AppSettings> {
    return save({ ...settings.value, uiTheme: themeId });
  }

  async function setLocale(nextLocale: AppLocale): Promise<AppSettings> {
    if (localeLocked.value) {
      return settings.value;
    }
    setLang(nextLocale);
    return save({ ...settings.value, locale: nextLocale });
  }

  async function setOnboardingDone(done: boolean): Promise<void> {
    persistOnboardingDone(done);
    settings.value = { ...settings.value, onboardingDone: done };
  }

  return {
    settings,
    loaded,
    providers,
    sets,
    activeSet,
    activeChatRouting,
    activeChatProvider,
    activeEmbeddingProvider,
    toolCallView,
    onboardingDone,
    settingsMode,
    settingsLocked,
    permissionsNetwork,
    density,
    uiTheme,
    locale,
    localeLocked,
    isLocalChatProvider,
    load,
    save,
    setActiveSet,
    createSet,
    updateSet,
    deleteSet,
    setToolCallView,
    setOnboardingDone,
    setSettingsMode,
    setDensity,
    setUiTheme,
    setLocale,
  };
}

export { isLocalLlmProvider, activeChatProvider };
