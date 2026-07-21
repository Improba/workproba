import { computed, ref, type ComputedRef, type Ref } from 'vue';
import {
  configCloud,
  disconnectCloud,
  enrollCloud,
  fetchCloudLlmQuota,
  fetchCloudStatus,
  listManagedConnectors,
  setManagedConnectorEnabled,
  pullCloud,
  syncCloud,
  syncManagedRegards,
  type CloudLlmQuota,
  type CloudPullResult,
  type CloudStatus,
  type CloudSyncRegardsResult,
  type CloudSyncResult,
  type ManagedConnector,
  type SidecarResult,
} from '@services/aiSidecar';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import {
  type CloudProviderReadiness,
  cloudReadinessFromQuota,
} from '@utils/providerSetValidation';

const status = ref<CloudStatus | null>(null);
const loading = ref(false);
const syncing = ref(false);
const pulling = ref(false);
const syncingRegards = ref(false);
const loadError = ref<string | null>(null);
const connectors = ref<ManagedConnector[]>([]);
const connectorsLoading = ref(false);
const connectorsError = ref<string | null>(null);
const quota = ref<CloudLlmQuota | null>(null);
const quotaLoading = ref(false);
const quotaError = ref<string | null>(null);
const quotaReachable = ref(true);
let pluginDataDir: string | null = null;

export interface UseCloudReturn {
  status: Ref<CloudStatus | null>;
  loading: Ref<boolean>;
  syncing: Ref<boolean>;
  pulling: Ref<boolean>;
  syncingRegards: Ref<boolean>;
  loadError: Ref<string | null>;
  connectors: Ref<ManagedConnector[]>;
  connectorsLoading: Ref<boolean>;
  connectorsError: Ref<string | null>;
  quota: Ref<CloudLlmQuota | null>;
  quotaLoading: Ref<boolean>;
  quotaError: Ref<string | null>;
  providerReadiness: ComputedRef<CloudProviderReadiness | null>;
  /** Cloud enrolled — « projet partagé » product vocabulary (not mount-only). */
  isActive: ComputedRef<boolean>;
  /** Session cloud user établie (flag technique `enrolled` côté API). */
  isEnrolled: ComputedRef<boolean>;
  /** Technical sync available: mount folder and/or cloud enrolled. */
  canSync: ComputedRef<boolean>;
  init: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  refreshConnectors: () => Promise<void>;
  setManagedConnectorEnabled: (
    connectorId: string,
    enabled: boolean,
  ) => Promise<boolean>;
  refreshQuota: () => Promise<void>;
  configure: (mountPath: string) => Promise<boolean>;
  enroll: (opts: {
    baseUrl: string;
    bearerToken?: string;
    joinToken?: string;
  }) => Promise<boolean>;
  disconnect: () => Promise<boolean>;
  sync: (projectId: string) => Promise<SidecarResult<CloudSyncResult>>;
  pull: (projectId: string) => Promise<SidecarResult<CloudPullResult>>;
  syncRegards: () => Promise<SidecarResult<CloudSyncRegardsResult>>;
}

export function useCloud(): UseCloudReturn {
  const { getPluginDataDir } = usePlugins();

  const isEnrolled = computed(() => Boolean(status.value?.enrolled));
  const canSync = computed(() => Boolean(status.value?.configured || status.value?.enrolled));
  const isActive = computed(() => isEnrolled.value);
  const providerReadiness = computed<CloudProviderReadiness | null>(() => {
    if (!status.value) return null;
    if (!status.value.enrolled) {
      return { enrolled: false, reachable: true };
    }
    const err = (quotaError.value ?? '').trim();
    if (!quotaReachable.value) {
      return { enrolled: true, reachable: false };
    }
    // Erreurs machine du GET quota → readiness explicite (pas de fail-open).
    if (err === 'not_subscribed') {
      return { enrolled: true, reachable: true, subscribed: false };
    }
    if (err === 'quota_exceeded') {
      return {
        enrolled: true,
        reachable: true,
        subscribed: true,
        quotaExceeded: true,
      };
    }
    if (
      err === 'cloud_not_enrolled'
      || err === 'invalid_user_jwt'
      || err === 'invalid_device_token'
      || err === 'bearer_token_required'
      || err === 'device_organization_required'
      || err === 'org_id_required'
    ) {
      return { enrolled: false, reachable: true };
    }
    return cloudReadinessFromQuota(
      true,
      quota.value,
      true,
    );
  });

  async function refreshQuota(): Promise<void> {
    if (!pluginDataDir || !status.value?.enrolled) {
      quota.value = null;
      quotaError.value = null;
      quotaReachable.value = true;
      return;
    }
    quotaLoading.value = true;
    quotaError.value = null;
    try {
      const result = await fetchCloudLlmQuota(pluginDataDir);
      if (!result.ok) {
        quota.value = null;
        const err = (result.error ?? '').trim();
        quotaError.value = err;
        quotaReachable.value = !(
          err === 'cloud_unreachable'
          || err.startsWith('quota_unavailable')
          || (typeof result.status === 'number' && result.status >= 500)
          || result.status === 0
        );
        return;
      }
      quotaReachable.value = true;
      quotaError.value = null;
      quota.value = result.data.enrolled ? result.data : null;
    } catch (err) {
      quota.value = null;
      quotaError.value = err instanceof Error ? err.message : 'cloud_quota_failed';
      quotaReachable.value = false;
    } finally {
      quotaLoading.value = false;
    }
  }

  async function refreshConnectors(): Promise<void> {
    if (!pluginDataDir || !status.value?.enrolled) {
      connectors.value = [];
      connectorsError.value = null;
      return;
    }
    connectorsLoading.value = true;
    connectorsError.value = null;
    try {
      const result = await listManagedConnectors(pluginDataDir);
      if (!result.ok) {
        connectors.value = [];
        connectorsError.value = result.error;
        return;
      }
      if (!result.data.enrolled) {
        connectors.value = [];
        return;
      }
      connectors.value = result.data.connectors;
    } catch (err) {
      connectors.value = [];
      connectorsError.value = err instanceof Error ? err.message : 'cloud_connectors_failed';
    } finally {
      connectorsLoading.value = false;
    }
  }

  async function setManagedConnectorEnabledLocal(
    connectorId: string,
    enabled: boolean,
  ): Promise<boolean> {
    if (!pluginDataDir || !status.value?.enrolled) return false;
    const result = await setManagedConnectorEnabled(pluginDataDir, connectorId, enabled);
    if (!result.ok) {
      connectorsError.value = result.error;
      return false;
    }
    const next = result.data;
    connectors.value = connectors.value.map((c) =>
      c.id === next.id ? { ...c, ...next, enabled: next.enabled !== false } : c,
    );
    if (!connectors.value.some((c) => c.id === next.id)) {
      connectors.value = [...connectors.value, next];
    }
    return true;
  }

  async function init(): Promise<void> {
    pluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    await refreshStatus();
  }

  async function refreshStatus(): Promise<void> {
    if (!pluginDataDir) {
      status.value = null;
      connectors.value = [];
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchCloudStatus(pluginDataDir);
      if (!result.ok) {
        status.value = null;
        loadError.value = result.error;
        connectors.value = [];
        return;
      }
      status.value = result.data;
      if (result.data.enrolled) {
        await Promise.all([refreshConnectors(), refreshQuota()]);
      } else {
        connectors.value = [];
        connectorsError.value = null;
        quota.value = null;
        quotaError.value = null;
        quotaReachable.value = true;
      }
    } catch (err) {
      status.value = null;
      loadError.value = err instanceof Error ? err.message : 'cloud_status_failed';
      connectors.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function configure(mountPath: string): Promise<boolean> {
    if (!pluginDataDir || !mountPath.trim()) return false;
    loadError.value = null;
    const result = await configCloud(pluginDataDir, mountPath.trim());
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    return result.data;
  }

  async function enroll(opts: {
    baseUrl: string;
    bearerToken?: string;
    joinToken?: string;
  }): Promise<boolean> {
    if (!pluginDataDir || !opts.baseUrl.trim()) return false;
    const hasJoin = Boolean(opts.joinToken?.trim());
    const hasBearer = Boolean(opts.bearerToken?.trim());
    if (!hasJoin && !hasBearer) return false;
    loadError.value = null;
    const result = await enrollCloud({
      pluginDataDir,
      baseUrl: opts.baseUrl.trim(),
      bearerToken: opts.bearerToken?.trim(),
      joinToken: opts.joinToken?.trim(),
    });
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    return result.data.authenticated;
  }

  async function disconnect(): Promise<boolean> {
    if (!pluginDataDir) return false;
    loadError.value = null;
    const result = await disconnectCloud(pluginDataDir);
    if (!result.ok) {
      loadError.value = result.error;
      return false;
    }
    await refreshStatus();
    connectors.value = [];
    connectorsError.value = null;
    return result.data;
  }

  async function sync(projectId: string): Promise<SidecarResult<CloudSyncResult>> {
    if (!pluginDataDir || !projectId) {
      return { ok: false, error: 'cloud_sync_missing_context' };
    }
    if (!canSync.value) {
      return { ok: false, error: 'cloud_not_configured' };
    }
    syncing.value = true;
    loadError.value = null;
    try {
      const result = await syncCloud({
        pluginDataDir,
        projectId,
        mountPath: status.value?.mount_path ?? undefined,
      });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      await refreshStatus();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_sync_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      syncing.value = false;
    }
  }

  async function pull(projectId: string): Promise<SidecarResult<CloudPullResult>> {
    if (!pluginDataDir || !projectId) {
      return { ok: false, error: 'cloud_pull_missing_context' };
    }
    if (!status.value?.enrolled) {
      return { ok: false, error: 'cloud_not_enrolled' };
    }
    pulling.value = true;
    loadError.value = null;
    try {
      const result = await pullCloud({ pluginDataDir, projectId });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      await refreshStatus();
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_pull_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      pulling.value = false;
    }
  }

  async function syncRegards(): Promise<SidecarResult<CloudSyncRegardsResult>> {
    if (!pluginDataDir) {
      return { ok: false, error: 'cloud_sync_regards_missing_context' };
    }
    if (!status.value?.enrolled) {
      return { ok: false, error: 'cloud_not_enrolled' };
    }
    syncingRegards.value = true;
    loadError.value = null;
    try {
      const result = await syncManagedRegards({
        pluginDataDir,
        orgId: status.value.org_id ?? undefined,
      });
      if (!result.ok) {
        loadError.value = result.error;
        return result;
      }
      return result;
    } catch (err) {
      const error = err instanceof Error ? err.message : 'cloud_sync_regards_failed';
      loadError.value = error;
      return { ok: false, error };
    } finally {
      syncingRegards.value = false;
    }
  }

  return {
    status,
    loading,
    syncing,
    pulling,
    syncingRegards,
    loadError,
    connectors,
    connectorsLoading,
    connectorsError,
    quota,
    quotaLoading,
    quotaError,
    providerReadiness,
    isActive,
    isEnrolled,
    canSync,
    init,
    refreshStatus,
    refreshConnectors,
    setManagedConnectorEnabled: setManagedConnectorEnabledLocal,
    refreshQuota,
    configure,
    enroll,
    disconnect,
    sync,
    pull,
    syncRegards,
  };
}
