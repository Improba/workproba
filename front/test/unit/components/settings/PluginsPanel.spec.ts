import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PluginsPanel from '@components/settings/PluginsPanel.vue';
import type { PluginInfo } from '@composables/useDesktop.types';
import {
  CLOUD_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
} from '@composables/usePlugins';

const plugins = ref<PluginInfo[]>([]);
const settingsMode = ref<'guided' | 'advanced'>('guided');
const settingsLocked = ref(false);
const openCapabilities = vi.fn();

function makePlugin(
  id: string,
  source: 'builtin' | 'local',
  enabledScoped = true,
): PluginInfo {
  return {
    manifest: {
      id,
      name: `plugin.${id}.name`,
      version: '1.0.0',
      description: `plugin.${id}.description`,
      permissions: [],
      defaultEnabled: true,
      uiSlots: [],
      hooks: [],
      isBuiltin: source === 'builtin',
    },
    enabled: enabledScoped,
    enabledScoped,
    source,
  };
}

vi.mock('@composables/usePlugins', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@composables/usePlugins')>();
  return {
    ...actual,
    usePlugins: () => ({
      plugins,
      loading: ref(false),
      loadError: ref(null),
      refresh: vi.fn(),
      activatePlugin: vi.fn(),
      deactivatePlugin: vi.fn(),
      installLocalPlugin: vi.fn(),
      uninstallLocalPlugin: vi.fn(),
    }),
    localPluginInstallAvailable: () => false,
  };
});

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settingsMode,
    settingsLocked,
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openCapabilities,
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  isDesktopApp: () => true,
  pickProjectFolder: vi.fn(),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    te: () => false,
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('PluginsPanel', () => {
  beforeEach(() => {
    settingsMode.value = 'guided';
    settingsLocked.value = false;
    openCapabilities.mockClear();
    plugins.value = [
      makePlugin(PERSONAS_PLUGIN_ID, 'builtin'),
      makePlugin(CLOUD_PLUGIN_ID, 'builtin'),
      makePlugin('custom.local', 'local'),
    ];
  });

  function mountPanel() {
    return mount(PluginsPanel, {
      global: {
        stubs: {
          Lucide: true,
          QToggle: {
            name: 'QToggle',
            template: '<input type="checkbox" class="q-toggle-stub" />',
            props: ['modelValue', 'disable', 'ariaLabel'],
          },
        },
      },
    });
  }

  it('masque le plugin cloud en mode guidé', async () => {
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.text()).not.toContain(`plugin.${CLOUD_PLUGIN_ID}.name`);
    expect(wrapper.text()).toContain(`plugin.${PERSONAS_PLUGIN_ID}.name`);
  });

  it('affiche le plugin cloud en mode avancé', async () => {
    settingsMode.value = 'advanced';
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.text()).toContain(`plugin.${CLOUD_PLUGIN_ID}.name`);
  });

  it('n\'affiche pas de toggle pour les builtins', async () => {
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.findAll('.q-toggle-stub')).toHaveLength(1);
  });

  it('propose d\'ouvrir les builtins dans Capacités', async () => {
    const wrapper = mountPanel();
    await flushPromises();
    expect(wrapper.text()).toContain('settings.plugins.managedByCapability');
    const openButton = wrapper
      .findAll('button')
      .find((btn) => btn.text() === 'settings.plugins.openInCapabilities');
    expect(openButton).toBeTruthy();
    await openButton!.trigger('click');
    expect(openCapabilities).toHaveBeenCalledWith('regards');
  });

  it('affiche le lien Capacités pour cloud en mode avancé', async () => {
    settingsMode.value = 'advanced';
    const wrapper = mountPanel();
    await flushPromises();
    const cloudCard = wrapper
      .findAll('.plugins-panel__card')
      .find((card) => card.text().includes(`plugin.${CLOUD_PLUGIN_ID}.name`));
    expect(cloudCard?.text()).toContain('settings.plugins.openInCapabilities');
    const openButton = cloudCard!
      .findAll('button')
      .find((btn) => btn.text() === 'settings.plugins.openInCapabilities');
    await openButton!.trigger('click');
    expect(openCapabilities).toHaveBeenCalledWith('project_sync');
  });
});
