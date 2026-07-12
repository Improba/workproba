import { ref } from 'vue';
import { flushPromises, mount, shallowMount, type VueWrapper } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WorkprobaLayout from '../../../src/layouts/WorkprobaLayout.vue';
import DensityControl from '../../../src/components/settings/DensityControl.vue';
import { useAppSettings } from '../../../src/composables/useAppSettings';
import type { AppSettings, DensityMode } from '../../../src/composables/useDesktop.types';

const desktopMocks = vi.hoisted(() => ({
  getAppSettings: vi.fn<() => Promise<AppSettings>>(),
  saveAppSettings: vi.fn<(settings: AppSettings) => Promise<AppSettings>>(),
}));

vi.mock('@composables/useDesktop', () => ({
  getAppSettings: desktopMocks.getAppSettings,
  saveAppSettings: desktopMocks.saveAppSettings,
  isDesktopApp: () => true,
}));

vi.mock('@composables/useProject', () => ({
  useProject: () => ({
    activePath: ref<string | null>(null),
    activeDataDir: ref<string | null>(null),
    workspaceTitle: ref<string | null>('Projet test'),
  }),
}));

vi.mock('@composables/useSidecarHealth', () => ({
  useSidecarHealth: vi.fn(),
}));

const densityStubs = {
  Notify: { create: vi.fn() },
};

describe('densité interface', () => {
  let layoutWrapper: VueWrapper | null = null;

  beforeEach(() => {
    desktopMocks.getAppSettings.mockReset();
    desktopMocks.saveAppSettings.mockReset();
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      density: 'comfortable',
    });
    desktopMocks.saveAppSettings.mockImplementation(async (settings) => settings);
  });

  afterEach(() => {
    layoutWrapper?.unmount();
    layoutWrapper = null;
  });

  it('WorkprobaLayout reflète data-density depuis useAppSettings', async () => {
    const { load } = useAppSettings();
    await load();

    layoutWrapper = shallowMount(WorkprobaLayout, {
      slots: { default: '<div class="slot-stub" />' },
    });
    await flushPromises();

    expect(layoutWrapper.find('.wp-shell').attributes('data-density')).toBe('comfortable');

    const { setDensity } = useAppSettings();
    await setDensity('spacious');
    await flushPromises();

    expect(layoutWrapper.find('.wp-shell').attributes('data-density')).toBe('spacious');
    expect(desktopMocks.saveAppSettings).toHaveBeenCalledWith(
      expect.objectContaining({ density: 'spacious' }),
    );
  });

  it('DensityControl met à jour la densité au clic', async () => {
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      density: 'comfortable',
    });
    const { load } = useAppSettings();
    await load();

    const wrapper = mount(DensityControl, {
      global: { stubs: densityStubs },
    });
    await flushPromises();

    const compactBtn = wrapper
      .findAll('.density-pill')
      .find((btn) => btn.text() === 'Compact');
    expect(compactBtn).toBeDefined();

    await compactBtn!.trigger('click');
    await flushPromises();

    const { density } = useAppSettings();
    expect(density.value).toBe('compact');
    expect(desktopMocks.saveAppSettings).toHaveBeenCalledWith(
      expect.objectContaining({ density: 'compact' as DensityMode }),
    );

    wrapper.unmount();
  });

  it('DensityControl est en lecture seule quand settingsLocked', async () => {
    desktopMocks.getAppSettings.mockResolvedValue({
      version: 1,
      providers: [],
      density: 'comfortable',
      settingsLocked: true,
    });

    const { load } = useAppSettings();
    await load();

    const wrapper = mount(DensityControl, {
      global: { stubs: densityStubs },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Verrouillé par votre administrateur');
    wrapper.findAll('.density-pill').forEach((btn) => {
      expect((btn.element as HTMLButtonElement).disabled).toBe(true);
    });

    wrapper.unmount();
  });
});
