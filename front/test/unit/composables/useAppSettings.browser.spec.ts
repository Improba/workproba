import { beforeEach, describe, expect, it, vi } from 'vitest';

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
