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
];

describe('useAppSettings hors Tauri', () => {
  beforeEach(() => {
    vi.resetModules();
    desktopMocks.isDesktopApp.mockReturnValue(false);
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
