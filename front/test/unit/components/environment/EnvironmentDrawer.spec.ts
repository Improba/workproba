import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EnvironmentDrawer from '@components/environment/EnvironmentDrawer.vue';

const environmentOpen = ref(true);
const selectedBusinessAgentId = ref<string | null>(null);
const closeEnvironment = vi.fn();
const openCapabilities = vi.fn();
const selectBusinessAgent = vi.fn();
const clearBusinessAgentSelection = vi.fn();
const requestConsultation = vi.fn();

const organizationName = ref<string | null>('Improba');
const userEmail = ref<string | null>('user@example.com');
const cloudConnected = ref(true);
const businessAgents = ref([
  {
    id: 'org.rh',
    name: 'Camille RH',
    role: 'RH',
    description: 'Référente RH',
    avatar_color: '#e0a93a',
    is_business_agent: true,
    tools: { allowed: [{ connector_id: 'ihora', tool: 'employee.read' }] },
  },
]);
const connectors = ref([{ id: 'ihora', name: 'Ihora', enabled: true, tools: [] }]);
const loading = ref(false);
const loadError = ref<string | null>(null);
const refresh = vi.fn().mockResolvedValue(undefined);

const effectiveActiveSet = ref<Record<string, unknown> | null>({ id: 'workproba-cloud' });
const activeSet = ref<Record<string, unknown> | null>({ id: 'workproba-cloud' });
const settingsLocked = ref(true);
const sidecarState = ref<'connected' | 'idle' | 'working' | 'error'>('connected');

const activePath = ref<string | null>('/tmp/workspace');
const activeSpaceId = ref<string | null>('space-1');

const push = vi.fn();

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    environmentOpen,
    selectedBusinessAgentId,
    closeEnvironment,
    openCapabilities,
    selectBusinessAgent,
    clearBusinessAgentSelection,
  }),
}));

vi.mock('@composables/useBusinessAgentConsultation', () => ({
  useBusinessAgentConsultation: () => ({
    requestConsultation,
  }),
}));

vi.mock('@composables/useOrganizationEnvironment', () => ({
  useOrganizationEnvironment: () => ({
    organizationName,
    userEmail,
    cloudConnected,
    businessAgents,
    connectors,
    loading,
    loadError,
    refresh,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    effectiveActiveSet,
    activeSet,
    settingsLocked,
  }),
}));

vi.mock('@composables/useChatActivity', () => ({
  useChatActivity: () => ({
    sidecarState,
  }),
}));

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activePath,
    activeSpaceId,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (params?.error) return `${key}:${params.error}`;
      if (params?.name) return `${key}:${params.name}`;
      return key;
    },
  }),
}));

describe('EnvironmentDrawer', () => {
  beforeEach(() => {
    environmentOpen.value = true;
    selectedBusinessAgentId.value = null;
    loadError.value = null;
    loading.value = false;
    effectiveActiveSet.value = { id: 'workproba-cloud' };
    activePath.value = '/tmp/workspace';
    activeSpaceId.value = 'space-1';
    closeEnvironment.mockClear();
    openCapabilities.mockClear();
    requestConsultation.mockClear();
    refresh.mockClear();
    push.mockClear();
  });

  it('affiche une alerte et relance le chargement en cas d’erreur', async () => {
    loadError.value = 'network_failed';

    const wrapper = shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    expect(wrapper.find('.environment-drawer__alert').exists()).toBe(true);
    await wrapper.find('.environment-drawer__alert-retry').trigger('click');
    expect(refresh).toHaveBeenCalledWith(true);
  });

  it('ouvre les capacités depuis la section configuration', async () => {
    const wrapper = shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    const buttons = wrapper.findAll('.environment-drawer__secondary');
    await buttons[buttons.length - 1].trigger('click');
    expect(openCapabilities).toHaveBeenCalled();
  });

  it('ouvre les réglages moteur et ferme le drawer', async () => {
    const wrapper = shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    const buttons = wrapper.findAll('.environment-drawer__secondary');
    await buttons[0].trigger('click');
    expect(closeEnvironment).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: 'settings_models' });
  });

  it('signale un moteur absent dans la section technique', () => {
    effectiveActiveSet.value = null;

    const wrapper = shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    expect(wrapper.find('.environment-drawer__engine').attributes('data-state')).toBe('error');
    expect(wrapper.text()).toContain('environment.engineMissing');
  });

  it('rafraîchit les données à l’ouverture', async () => {
    environmentOpen.value = false;

    shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    refresh.mockClear();
    environmentOpen.value = true;
    await flushPromises();

    expect(refresh).toHaveBeenCalledWith(true);
  });

  it('désactive la consultation sans espace actif', async () => {
    selectedBusinessAgentId.value = 'org.rh';
    activePath.value = null;
    activeSpaceId.value = null;

    const wrapper = shallowMount(EnvironmentDrawer, {
      global: { stubs: { Lucide: true, PersonaAvatar: true, SpecialistToolsPanel: true } },
    });

    const consultButton = wrapper.find('.environment-drawer__primary');
    expect(consultButton.attributes('disabled')).toBeDefined();
    expect(wrapper.text()).toContain('environment.consultNeedsSpace');

    await consultButton.trigger('click');
    expect(requestConsultation).not.toHaveBeenCalled();
  });
});
