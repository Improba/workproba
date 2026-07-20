import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const desktopMocks = vi.hoisted(() => ({
  getAppSettings: vi.fn(),
  saveAppSettings: vi.fn(),
  isDesktopApp: vi.fn(() => false),
}));

vi.mock('@composables/useDesktop', () => ({
  getAppSettings: desktopMocks.getAppSettings,
  saveAppSettings: desktopMocks.saveAppSettings,
  isDesktopApp: desktopMocks.isDesktopApp,
}));

const cloudMocks = vi.hoisted(() => ({
  providerReadiness: { value: null as { enrolled: boolean; reachable: boolean } | null },
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    providerReadiness: cloudMocks.providerReadiness,
  }),
}));

vi.mock('@utils/i18nT', () => ({
  t: (key: string) => key,
}));

const builtinSets = [
  {
    id: 'mistral-default',
    name: 'Mistral',
    isBuiltin: true,
    isDefault: true,
    chat: { provider: 'mistral', model: 'mistral-medium-latest' },
    embeddings: { provider: 'mistral', model: 'mistral-embed' },
    capabilities: { vision: true, ocr: true },
    vision: { mode: 'native', model: 'pixtral-large-latest' },
    ocr: { mode: 'native' },
  },
  {
    id: 'ollama-local',
    name: 'Ollama',
    isBuiltin: true,
    isDefault: false,
    chat: { provider: 'ollama', model: 'llama3.2', baseUrl: 'http://127.0.0.1:11434/v1' },
    embeddings: { provider: 'ollama', model: 'nomic-embed-text', baseUrl: 'http://127.0.0.1:11434/v1' },
    capabilities: { vision: false, ocr: false },
    vision: { mode: 'none' },
    ocr: { mode: 'none' },
  },
  {
    id: 'workproba-cloud',
    name: 'Improba Cloud',
    isBuiltin: true,
    isDefault: false,
    authMode: 'device_bearer',
    chat: { provider: 'mistral', model: 'mistral-small-latest' },
    embeddings: { provider: 'openai_compat', model: 'mistral-embed' },
    capabilities: { vision: true, ocr: true },
    vision: { mode: 'chat' },
    ocr: { mode: 'auto' },
  },
];

describe('useAppSettings hors Tauri', () => {
  beforeEach(() => {
    vi.resetModules();
    desktopMocks.isDesktopApp.mockReturnValue(false);
    cloudMocks.providerReadiness.value = null;
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: builtinSets,
      activeSetId: 'mistral-default',
    });
    desktopMocks.saveAppSettings.mockClear();
  });

  it('setActiveSet met à jour l\'état local sans appeler saveAppSettings', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setActiveSet, activeSet } = useAppSettings();
    await load();

    await setActiveSet('ollama-local');

    expect(activeSet.value?.id).toBe('ollama-local');
    expect(desktopMocks.saveAppSettings).not.toHaveBeenCalled();
  });

  it('setActiveSet refuse workproba-cloud sans enrollment', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setActiveSet } = useAppSettings();
    await load();

    await expect(setActiveSet('workproba-cloud')).rejects.toMatchObject({
      name: 'ProviderSetNotReadyError',
      reason: 'cloud_not_enrolled',
    });
  });

  it('setActiveSet accepte workproba-cloud enrollé', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setActiveSet, activeSet } = useAppSettings();
    await load();

    await setActiveSet('workproba-cloud', {
      cloud: { enrolled: true, reachable: true, subscribed: true },
    });

    expect(activeSet.value?.id).toBe('workproba-cloud');
  });

  it('setActiveSet refuse Mistral sans clé API', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setActiveSet } = useAppSettings();
    await load();

    await expect(setActiveSet('mistral-default')).rejects.toMatchObject({
      name: 'ProviderSetNotReadyError',
      reason: 'missing_api_key',
    });
  });

  it('effectiveActiveSet est null si le set persisté n\'est pas ready', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, activeSet, effectiveActiveSet } = useAppSettings();
    await load();

    expect(activeSet.value?.id).toBe('mistral-default');
    expect(effectiveActiveSet.value).toBeNull();
  });

  it('ne force pas activeSetId depuis isDefault au premier chargement', async () => {
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: builtinSets,
    });
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, activeSet, effectiveActiveSet, settings } = useAppSettings();
    await load();

    expect(settings.value.activeSetId).toBeNull();
    expect(activeSet.value).toBeNull();
    expect(effectiveActiveSet.value).toBeNull();
  });

  it('conserve l\'intention cloud sans moteur effectif si non enrollé', async () => {
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: builtinSets,
      activeSetId: 'workproba-cloud',
    });
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, activeSet, effectiveActiveSet } = useAppSettings();
    await load();

    expect(activeSet.value?.id).toBe('workproba-cloud');
    expect(effectiveActiveSet.value).toBeNull();
  });

  it('deleteSet bascule vers un set ready ou null, pas cloud non enrollé', async () => {
    const customSet = {
      id: 'custom-openai',
      name: 'Custom',
      isBuiltin: false,
      isDefault: false,
      chat: {
        provider: 'openai_compat',
        model: 'gpt-4o',
        baseUrl: 'https://api.example.com/v1',
        apiKey: 'sk-custom',
      },
      embeddings: { provider: 'openai_compat', model: 'text-embedding-3-small' },
      capabilities: { vision: true, ocr: true },
      vision: { mode: 'chat' },
      ocr: { mode: 'auto' },
    };
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: [...builtinSets, customSet],
      activeSetId: 'custom-openai',
    });
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, deleteSet, activeSet, effectiveActiveSet } = useAppSettings();
    await load();

    await deleteSet('custom-openai');

    expect(activeSet.value?.id).toBe('ollama-local');
    expect(effectiveActiveSet.value?.id).toBe('ollama-local');
  });

  it('deleteSet met activeSetId à null si aucun set ready', async () => {
    const customSet = {
      id: 'custom-openai',
      name: 'Custom',
      isBuiltin: false,
      isDefault: false,
      chat: {
        provider: 'openai_compat',
        model: 'gpt-4o',
        baseUrl: 'https://api.example.com/v1',
        apiKey: 'sk-custom',
      },
      embeddings: { provider: 'openai_compat', model: 'text-embedding-3-small' },
      capabilities: { vision: true, ocr: true },
      vision: { mode: 'chat' },
      ocr: { mode: 'auto' },
    };
    const setsWithoutOllama = builtinSets.filter((set) => set.id !== 'ollama-local');
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: [...setsWithoutOllama, customSet],
      activeSetId: 'custom-openai',
    });
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, deleteSet, activeSet, effectiveActiveSet } = useAppSettings();
    await load();

    await deleteSet('custom-openai');

    expect(activeSet.value).toBeNull();
    expect(effectiveActiveSet.value).toBeNull();
  });
});

describe('setThinkingDetailView', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    desktopMocks.isDesktopApp.mockReturnValue(true);
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: builtinSets,
      activeSetId: 'mistral-default',
      thinkingDetailView: 'summary',
    });
    desktopMocks.saveAppSettings.mockImplementation(async (settings) => settings);
    desktopMocks.saveAppSettings.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('met à jour thinkingDetailView immédiatement et debounce save (400 ms)', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setThinkingDetailView, thinkingDetailView } = useAppSettings();
    await load();

    const savePromise = setThinkingDetailView('raw');

    expect(thinkingDetailView.value).toBe('raw');
    expect(desktopMocks.saveAppSettings).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(400);
    await savePromise;

    expect(desktopMocks.saveAppSettings).toHaveBeenCalledTimes(1);
    expect(desktopMocks.saveAppSettings).toHaveBeenCalledWith(
      expect.objectContaining({ thinkingDetailView: 'raw' }),
    );
  });

  it('ne laisse pas un load concurrent écraser thinkingDetailView pendant le debounce', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { load, setThinkingDetailView, thinkingDetailView } = useAppSettings();

    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      sets: builtinSets,
      activeSetId: 'mistral-default',
      thinkingDetailView: 'summary',
    });
    await load();

    let resolveGet: ((value: unknown) => void) | null = null;
    desktopMocks.getAppSettings.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGet = resolve;
        }),
    );
    const loadPromise = load();
    void setThinkingDetailView('raw');
    expect(thinkingDetailView.value).toBe('raw');

    resolveGet?.({
      version: 1,
      providers: [],
      sets: builtinSets,
      activeSetId: 'mistral-default',
      thinkingDetailView: 'summary',
    });
    await loadPromise;

    expect(thinkingDetailView.value).toBe('raw');
  });
});
