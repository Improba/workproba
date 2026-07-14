import { describe, expect, it, vi, beforeEach } from 'vitest';
import { nextTick } from 'vue';
import type { AppSettings } from '@composables/useDesktop.types';
import { UI_THEME_STORAGE_KEY } from '@utils/uiTheme';

const desktopMocks = vi.hoisted(() => ({
  getAppSettings: vi.fn(),
  saveAppSettings: vi.fn(),
  isDesktopApp: vi.fn(() => true),
}));

const quasarDarkSet = vi.hoisted(() => vi.fn());
vi.mock('quasar', () => ({
  useQuasar: () => ({
    dark: { isActive: false, set: quasarDarkSet },
  }),
  Notify: { create: vi.fn() },
}));

vi.mock('@composables/useDesktop', () => ({
  getAppSettings: desktopMocks.getAppSettings,
  saveAppSettings: desktopMocks.saveAppSettings,
  isDesktopApp: desktopMocks.isDesktopApp,
}));

describe('useUiTheme', () => {
  beforeEach(async () => {
    vi.resetModules();
    quasarDarkSet.mockClear();
    desktopMocks.getAppSettings.mockReset();
    desktopMocks.saveAppSettings.mockReset();
    desktopMocks.isDesktopApp.mockReturnValue(true);
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      uiTheme: 'charcoal',
    } satisfies AppSettings);
    desktopMocks.saveAppSettings.mockImplementation(async (s: AppSettings) => s);
    localStorage.removeItem(UI_THEME_STORAGE_KEY);
    document.documentElement.removeAttribute('data-ui-theme');
    document.documentElement.removeAttribute('data-theme');
  });

  it('applique le thème persisté après load et toggle vers paper', async () => {
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { useUiTheme } = await import('@composables/useUiTheme');

    const { load } = useAppSettings();
    await load();

    const { uiTheme, toggleUiTheme } = useUiTheme();
    await nextTick();

    expect(uiTheme.value).toBe('charcoal');
    expect(document.documentElement.getAttribute('data-ui-theme')).toBe('charcoal');
    expect(quasarDarkSet).toHaveBeenCalledWith(true);
    expect(localStorage.getItem(UI_THEME_STORAGE_KEY)).toBe('charcoal');

    await toggleUiTheme();
    expect(desktopMocks.saveAppSettings).toHaveBeenCalledWith(
      expect.objectContaining({ uiTheme: 'paper' }),
    );
    expect(uiTheme.value).toBe('paper');
    expect(localStorage.getItem(UI_THEME_STORAGE_KEY)).toBe('paper');
  });

  it('n applique pas le thème avant la fin du load', async () => {
    let resolveSettings!: (value: AppSettings) => void;
    desktopMocks.getAppSettings.mockReturnValue(
      new Promise<AppSettings>((resolve) => {
        resolveSettings = resolve;
      }),
    );

    const { useAppSettings } = await import('@composables/useAppSettings');
    const { useUiTheme } = await import('@composables/useUiTheme');

    const { load } = useAppSettings();
    const loadPromise = load();
    useUiTheme();
    await nextTick();

    expect(document.documentElement.getAttribute('data-ui-theme')).toBeNull();

    resolveSettings({ version: 1, providers: [], uiTheme: 'charcoal' });
    await loadPromise;
    await nextTick();

    expect(document.documentElement.getAttribute('data-ui-theme')).toBe('charcoal');
  });

  it('restaure le thème si la persistance Tauri échoue', async () => {
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      uiTheme: 'paper',
    } satisfies AppSettings);
    desktopMocks.saveAppSettings.mockRejectedValue(new Error('disk full'));

    const { useAppSettings } = await import('@composables/useAppSettings');
    const { useUiTheme } = await import('@composables/useUiTheme');

    await useAppSettings().load();
    const { toggleUiTheme, uiTheme } = useUiTheme();
    await nextTick();

    await expect(toggleUiTheme()).rejects.toThrow('disk full');
    expect(uiTheme.value).toBe('paper');
    expect(localStorage.getItem(UI_THEME_STORAGE_KEY)).toBe('paper');
  });
});
