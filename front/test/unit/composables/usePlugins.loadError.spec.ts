import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listPlugins = vi.fn();

vi.mock('@composables/useDesktop', () => ({
  listPlugins: (...args: unknown[]) => listPlugins(...args),
  activatePlugin: vi.fn(),
  deactivatePlugin: vi.fn(),
  getPluginDataDir: vi.fn(),
  installLocalPlugin: vi.fn(),
  uninstallLocalPlugin: vi.fn(),
}));

describe('usePlugins loadError', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('expose loadError quand listPlugins échoue', async () => {
    listPlugins.mockRejectedValue(new Error('plugins_unreachable'));

    const { usePlugins } = await import('@composables/usePlugins');
    let api!: ReturnType<typeof usePlugins>;
    mount(
      defineComponent({
        setup() {
          api = usePlugins();
          return {};
        },
        template: '<div />',
      }),
    );

    await vi.waitFor(() => {
      expect(api.loadError.value).toBe('plugins_unreachable');
    });
    expect(api.plugins.value).toEqual([]);
  });
});
