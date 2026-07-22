import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';
import {
  CAPABILITY_CATALOG,
  getCapabilityDefinition,
  isManagedCapabilityId,
  type CapabilityId,
} from '@capabilities/capabilityCatalog';
import { usePlugins, CLOUD_PLUGIN_ID } from './usePlugins';
import { useSpace } from './useSpace';
import {
  fetchWorkspaceCapabilities,
  updateWorkspaceCapabilitiesWanted,
  type SpaceCapabilitiesProfile,
  type SpaceCapabilityItem,
} from '@services/aiSidecar';

export interface UseSpaceCapabilitiesReturn {
  loading: Ref<boolean>;
  error: Ref<string | null>;
  profile: Ref<SpaceCapabilitiesProfile | null>;
  activeItems: ComputedRef<SpaceCapabilityItem[]>;
  availableItems: ComputedRef<SpaceCapabilityItem[]>;
  unavailableItems: ComputedRef<SpaceCapabilityItem[]>;
  refresh: () => Promise<void>;
  setWanted: (id: CapabilityId, wanted: boolean) => Promise<{
    ok: boolean;
    autoWantedCloud: boolean;
    error?: string;
  }>;
}

function managedFirstThenLocal(items: SpaceCapabilityItem[]): SpaceCapabilityItem[] {
  const managed: SpaceCapabilityItem[] = [];
  const local: SpaceCapabilityItem[] = [];
  for (const item of items) {
    if (isManagedCapabilityId(item.id as CapabilityId)) {
      managed.push(item);
    } else {
      local.push(item);
    }
  }
  // Locals keep catalog order; managed keep API order.
  const localOrder = new Map(
    CAPABILITY_CATALOG.map((cap, index) => [cap.id, index]),
  );
  local.sort(
    (a, b) => (localOrder.get(a.id as CapabilityId) ?? 99)
      - (localOrder.get(b.id as CapabilityId) ?? 99),
  );
  return [...managed, ...local];
}

export interface UseSpaceCapabilitiesOptions {
  workspaceDataDir?: Ref<string | null | undefined>;
}

export function useSpaceCapabilities(
  opts?: UseSpaceCapabilitiesOptions,
): UseSpaceCapabilitiesReturn {
  const { activeDataDir } = useSpace();
  const { activePluginIds, getPluginDataDir } = usePlugins();
  const dataDirRef = opts?.workspaceDataDir ?? activeDataDir;

  const loading = ref(false);
  const error = ref<string | null>(null);
  const profile = ref<SpaceCapabilitiesProfile | null>(null);
  let requestSeq = 0;

  async function resolvePluginDataDir(): Promise<string | null> {
    try {
      return await getPluginDataDir(CLOUD_PLUGIN_ID);
    } catch {
      return null;
    }
  }

  async function refresh(): Promise<void> {
    const dataDir = dataDirRef.value;
    if (!dataDir?.trim()) {
      profile.value = null;
      error.value = null;
      return;
    }
    const seq = ++requestSeq;
    loading.value = true;
    error.value = null;
    const pluginDataDir = await resolvePluginDataDir();
    const result = await fetchWorkspaceCapabilities({
      workspaceDataDir: dataDir,
      pluginDataDir,
      activePlugins: activePluginIds.value,
    });
    if (seq !== requestSeq) return;
    loading.value = false;
    if (!result.ok) {
      error.value = result.error;
      return;
    }
    profile.value = result.data;
  }

  async function setWanted(
    id: CapabilityId,
    wanted: boolean,
  ): Promise<{ ok: boolean; autoWantedCloud: boolean; error?: string }> {
    const dataDir = dataDirRef.value;
    if (!dataDir?.trim()) {
      return { ok: false, autoWantedCloud: false, error: 'no_workspace' };
    }
    const seq = ++requestSeq;

    const cloudWasWanted = profile.value?.wanted?.workproba_cloud === true;
    const nestedNeedsParent =
      wanted
      && !cloudWasWanted
      && (
        getCapabilityDefinition(id)?.parentId === 'workproba_cloud'
        || isManagedCapabilityId(id)
      );

    const pluginDataDir = await resolvePluginDataDir();
    const result = await updateWorkspaceCapabilitiesWanted({
      workspaceDataDir: dataDir,
      wanted: { [id]: wanted },
      pluginDataDir,
      activePlugins: activePluginIds.value,
    });
    if (seq !== requestSeq) {
      return { ok: false, autoWantedCloud: false };
    }
    if (!result.ok) {
      return { ok: false, autoWantedCloud: false, error: result.error };
    }
    profile.value = result.data;
    const autoWantedCloud =
      nestedNeedsParent && result.data.wanted.workproba_cloud === true;
    return { ok: true, autoWantedCloud };
  }

  const activeItems = computed(() =>
    managedFirstThenLocal(
      (profile.value?.items ?? []).filter((item) => item.status === 'active'),
    ),
  );
  const availableItems = computed(() =>
    managedFirstThenLocal(
      (profile.value?.items ?? []).filter((item) => item.status === 'available'),
    ),
  );
  const unavailableItems = computed(() =>
    managedFirstThenLocal(
      (profile.value?.items ?? []).filter((item) => item.status === 'unavailable'),
    ),
  );

  watch(
    dataDirRef,
    () => {
      void refresh();
    },
    { immediate: true },
  );

  return {
    loading,
    error,
    profile,
    activeItems,
    availableItems,
    unavailableItems,
    refresh,
    setWanted,
  };
}
