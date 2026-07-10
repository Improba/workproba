import { computed, ref } from 'vue';
import {
  getAppSettings,
  saveAppSettings,
  type AppSettings,
  type LlmProviderEntry,
} from '@composables/useDesktop';
import type { DensityMode, SettingsMode, ToolCallViewMode } from '@composables/useDesktop.types';
import { getAiSidecarUrl, getDesktopSecret } from '@services/aiSidecar';
import { isLocalLlmProvider } from '@utils/isLocalLlmProvider';

/** Payload de config LLM attendu par le sidecar (snake_case, cf. app/schemas.py). */
export interface LlmConfigPayload {
  provider: string;
  model: string;
  base_url?: string | null;
  api_key?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  extra_headers?: Record<string, string>;
}

export interface LlmTestResult {
  ok: boolean;
  detail: string;
  modelCount?: number | null;
}

const ONBOARDING_DONE_KEY = 'workproba:onboardingDone';

const settings = ref<AppSettings>({ version: 1, providers: [], density: 'comfortable' });
const loaded = ref(false);

function readOnboardingDone(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(ONBOARDING_DONE_KEY) === 'true';
}

function persistOnboardingDone(done: boolean): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(ONBOARDING_DONE_KEY, String(done));
}

const providers = computed(() => settings.value.providers);

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

const density = computed<DensityMode>(
  () => settings.value.density ?? 'comfortable',
);

const isLocalChatProvider = computed(() =>
  isLocalLlmProvider(activeChatProvider.value),
);

export function toChatLlmConfig(entry: LlmProviderEntry | null): LlmConfigPayload | null {
  if (!entry) return null;
  return {
    provider: entry.provider,
    model: entry.model,
    base_url: entry.baseUrl ?? null,
    api_key: entry.apiKey ?? null,
    temperature: entry.temperature ?? null,
    max_tokens: entry.maxTokens ?? null,
    extra_headers: entry.extraHeaders ?? {},
  };
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

/** Construit les deux configs (chat + embeddings) à injecter dans un tour agent. */
export function buildActiveLlmConfigs(): {
  chat: LlmConfigPayload | null;
  embedding: LlmConfigPayload | null;
} {
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

export interface UseAppSettingsReturn {
  settings: typeof settings;
  loaded: typeof loaded;
  providers: typeof providers;
  activeChatProvider: typeof activeChatProvider;
  activeEmbeddingProvider: typeof activeEmbeddingProvider;
  toolCallView: typeof toolCallView;
  onboardingDone: typeof onboardingDone;
  settingsMode: typeof settingsMode;
  settingsLocked: typeof settingsLocked;
  density: typeof density;
  isLocalChatProvider: typeof isLocalChatProvider;
  load: () => Promise<AppSettings>;
  save: (next: AppSettings) => Promise<AppSettings>;
  setToolCallView: (view: ToolCallViewMode) => Promise<AppSettings>;
  setOnboardingDone: (done: boolean) => Promise<void>;
  setSettingsMode: (mode: SettingsMode) => Promise<AppSettings>;
  setDensity: (mode: DensityMode) => Promise<AppSettings>;
}

export function useAppSettings(): UseAppSettingsReturn {
  async function load(): Promise<AppSettings> {
    const value = await getAppSettings();
    settings.value = { ...value, onboardingDone: readOnboardingDone() };
    loaded.value = true;
    return settings.value;
  }

  async function save(next: AppSettings): Promise<AppSettings> {
    const persisted = await saveAppSettings(next);
    settings.value = persisted;
    return persisted;
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

  async function setOnboardingDone(done: boolean): Promise<void> {
    persistOnboardingDone(done);
    settings.value = { ...settings.value, onboardingDone: done };
  }

  return {
    settings,
    loaded,
    providers,
    activeChatProvider,
    activeEmbeddingProvider,
    toolCallView,
    onboardingDone,
    settingsMode,
    settingsLocked,
    density,
    isLocalChatProvider,
    load,
    save,
    setToolCallView,
    setOnboardingDone,
    setSettingsMode,
    setDensity,
  };
}

export { isLocalLlmProvider };
