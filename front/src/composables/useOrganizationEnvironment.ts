import { computed, ref, type ComputedRef, type Ref } from 'vue';
import type { ManagedConnector, PersonaInfo } from '@services/aiSidecar';
import { isBusinessAgent } from '@utils/specialistTools';
import { useCloud } from './useCloud';
import { usePersonas } from './usePersonas';
import {
  PERSONAS_PLUGIN_ID,
  usePlugins,
} from './usePlugins';

const loading = ref(false);
const loaded = ref(false);
const loadError = ref<string | null>(null);
let refreshPromise: Promise<void> | null = null;
let pendingForce = false;

function uniqueBusinessAgents(
  sets: ReturnType<typeof usePersonas>['sets']['value'],
): PersonaInfo[] {
  const byId = new Map<string, PersonaInfo>();
  for (const set of sets) {
    for (const persona of set.personas) {
      if (isBusinessAgent(persona)) byId.set(persona.id, persona);
    }
  }
  return [...byId.values()];
}

export interface UseOrganizationEnvironmentReturn {
  organizationName: ComputedRef<string | null>;
  userEmail: ComputedRef<string | null>;
  cloudConnected: ComputedRef<boolean>;
  businessAgents: ComputedRef<PersonaInfo[]>;
  connectors: Ref<ManagedConnector[]>;
  loading: Ref<boolean>;
  loaded: Ref<boolean>;
  loadError: Ref<string | null>;
  refresh: (force?: boolean) => Promise<void>;
}

/**
 * Agrège le contexte organisationnel affichable par le shell.
 * Les outils restent rattachés aux agents métier qui les portent.
 */
export function useOrganizationEnvironment(): UseOrganizationEnvironmentReturn {
  const cloud = useCloud();
  const personas = usePersonas();
  const plugins = usePlugins();

  const organizationName = computed(() => (
    plugins.isCloudPluginActive.value
      ? cloud.status.value?.org_label?.trim() || null
      : null
  ));
  const userEmail = computed(() => (
    plugins.isCloudPluginActive.value
      ? cloud.status.value?.current_user_email?.trim() || null
      : null
  ));
  const cloudConnected = computed(
    () => plugins.isCloudPluginActive.value && cloud.isEnrolled.value,
  );
  const businessAgents = computed(() => (
    plugins.isPersonasPluginActive.value
      ? uniqueBusinessAgents(personas.sets.value)
      : []
  ));

  async function refresh(force = false): Promise<void> {
    if (force) pendingForce = true;

    if (refreshPromise) return refreshPromise;
    if (loaded.value && !pendingForce) return;

    refreshPromise = (async () => {
      try {
        do {
          const mustForce = pendingForce;
          pendingForce = false;
          if (mustForce) loaded.value = false;
          loading.value = true;
          loadError.value = null;
          try {
            await plugins.refresh();

            const tasks: Promise<unknown>[] = [];
            if (plugins.isCloudPluginActive.value) {
              tasks.push(cloud.init());
            }
            if (plugins.isPersonasPluginActive.value) {
              tasks.push(
                plugins.getPluginDataDir(PERSONAS_PLUGIN_ID).then((dir) => (
                  dir ? personas.refresh(dir) : undefined
                )),
              );
            }
            await Promise.all(tasks);
            loaded.value = true;
          } catch (error) {
            loadError.value = error instanceof Error ? error.message : 'environment_load_failed';
          } finally {
            loading.value = false;
          }
        } while (pendingForce);
      } finally {
        refreshPromise = null;
      }
    })();

    return refreshPromise;
  }

  return {
    organizationName,
    userEmail,
    cloudConnected,
    businessAgents,
    connectors: cloud.connectors,
    loading,
    loaded,
    loadError,
    refresh,
  };
}

export function resetOrganizationEnvironmentForTests(): void {
  loading.value = false;
  loaded.value = false;
  loadError.value = null;
  refreshPromise = null;
  pendingForce = false;
}
