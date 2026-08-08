import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  resetOrganizationEnvironmentForTests,
  useOrganizationEnvironment,
} from '@composables/useOrganizationEnvironment';

const cloudStatus = ref<{ org_label?: string; current_user_email?: string; enrolled?: boolean } | null>({
  org_label: 'Improba',
  current_user_email: 'user@example.com',
  enrolled: true,
});
const cloudIsEnrolled = ref(true);
const cloudConnectors = ref([{ id: 'ihora', name: 'Ihora', enabled: true, tools: [] }]);
const cloudInit = vi.fn().mockResolvedValue(undefined);

const personaSets = ref([
  {
    personas: [
      {
        id: 'builtin.advisor',
        name: 'Conseiller',
        is_business_agent: false,
      },
      {
        id: 'org.rh',
        name: 'Camille RH',
        is_business_agent: true,
      },
    ],
  },
]);
const personasRefresh = vi.fn().mockResolvedValue(undefined);

const isCloudPluginActive = ref(true);
const isPersonasPluginActive = ref(true);
const pluginsRefresh = vi.fn().mockResolvedValue(undefined);
const getPluginDataDir = vi.fn().mockResolvedValue('/tmp/personas');

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: cloudStatus,
    isEnrolled: cloudIsEnrolled,
    connectors: cloudConnectors,
    init: cloudInit,
  }),
}));

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    sets: personaSets,
    refresh: personasRefresh,
  }),
}));

vi.mock('@composables/usePlugins', () => ({
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  usePlugins: () => ({
    isCloudPluginActive,
    isPersonasPluginActive,
    refresh: pluginsRefresh,
    getPluginDataDir,
  }),
}));

describe('useOrganizationEnvironment', () => {
  beforeEach(() => {
    resetOrganizationEnvironmentForTests();
    cloudStatus.value = {
      org_label: 'Improba',
      current_user_email: 'user@example.com',
      enrolled: true,
    };
    cloudIsEnrolled.value = true;
    isCloudPluginActive.value = true;
    isPersonasPluginActive.value = true;
    pluginsRefresh.mockClear();
    cloudInit.mockClear();
    personasRefresh.mockClear();
    getPluginDataDir.mockClear();
  });

  it('agrège le contexte cloud et filtre les agents métier', async () => {
    const env = useOrganizationEnvironment();

    await env.refresh();

    expect(env.organizationName.value).toBe('Improba');
    expect(env.userEmail.value).toBe('user@example.com');
    expect(env.cloudConnected.value).toBe(true);
    expect(env.businessAgents.value.map((agent) => agent.id)).toEqual(['org.rh']);
    expect(pluginsRefresh).toHaveBeenCalled();
    expect(cloudInit).toHaveBeenCalled();
    expect(personasRefresh).toHaveBeenCalledWith('/tmp/personas');
  });

  it('conserve loadError et laisse loaded à false en cas d’échec', async () => {
    pluginsRefresh.mockRejectedValueOnce(new Error('refresh_failed'));
    const env = useOrganizationEnvironment();

    await env.refresh();

    expect(env.loadError.value).toBe('refresh_failed');
    expect(env.loaded.value).toBe(false);
  });

  it('réinitialise loaded lors d’un refresh forcé', async () => {
    const env = useOrganizationEnvironment();
    await env.refresh();
    expect(env.loaded.value).toBe(true);

    pluginsRefresh.mockImplementationOnce(async () => {
      await new Promise((resolve) => { setTimeout(resolve, 10); });
    });
    const pending = env.refresh(true);
    expect(env.loaded.value).toBe(false);
    await pending;
    expect(env.loaded.value).toBe(true);
  });

  it('ignore le cloud quand le plugin est inactif', async () => {
    isCloudPluginActive.value = false;
    const env = useOrganizationEnvironment();

    await env.refresh();

    expect(env.organizationName.value).toBeNull();
    expect(env.cloudConnected.value).toBe(false);
    expect(cloudInit).not.toHaveBeenCalled();
  });

  it('exécute un refresh forcé après un soft refresh concurrent', async () => {
    let releaseSoft: () => void = () => {};
    const softGate = new Promise<void>((resolve) => {
      releaseSoft = resolve;
    });
    pluginsRefresh.mockImplementationOnce(async () => {
      await softGate;
    });

    const env = useOrganizationEnvironment();
    const softPromise = env.refresh();
    const forcePromise = env.refresh(true);

    expect(pluginsRefresh).toHaveBeenCalledTimes(1);

    releaseSoft();
    await softPromise;
    await forcePromise;

    expect(pluginsRefresh).toHaveBeenCalledTimes(2);
  });
});
