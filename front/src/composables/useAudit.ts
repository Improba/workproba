import { ref, type Ref } from 'vue';
import {
  fetchAudit,
  fetchAuditConfig,
  updateAuditConfig,
  type AuditConfig,
  type AuditEntry,
  type AuditFilters,
} from '@services/aiSidecar';
import { useAppSettings } from '@composables/useAppSettings';
import { useEnterprise } from '@composables/useEnterprise';

const entries = ref<AuditEntry[]>([]);
const total = ref(0);
const config = ref<AuditConfig | null>(null);
const loading = ref(false);
const configLoading = ref(false);
const loadError = ref<string | null>(null);

export interface UseAuditReturn {
  entries: Ref<AuditEntry[]>;
  total: Ref<number>;
  config: Ref<AuditConfig | null>;
  loading: Ref<boolean>;
  configLoading: Ref<boolean>;
  loadError: Ref<string | null>;
  fetchAuditEntries: (filters: AuditFilters) => Promise<void>;
  loadConfig: (workspaceDataDir: string) => Promise<void>;
  updateRetention: (workspaceDataDir: string, days: number) => Promise<boolean>;
}

export function useAudit(): UseAuditReturn {
  const { settingsLocked } = useAppSettings();
  const { preset } = useEnterprise();

  async function fetchAuditEntries(filters: AuditFilters): Promise<void> {
    if (!filters.workspaceDataDir) {
      entries.value = [];
      total.value = 0;
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchAudit(filters);
      entries.value = result.entries;
      total.value = result.total;
    } catch (err) {
      entries.value = [];
      total.value = 0;
      loadError.value = err instanceof Error ? err.message : 'audit_load_failed';
    } finally {
      loading.value = false;
    }
  }

  async function loadConfig(workspaceDataDir: string): Promise<void> {
    if (!workspaceDataDir) {
      config.value = null;
      return;
    }
    configLoading.value = true;
    try {
      config.value = await fetchAuditConfig(workspaceDataDir, {
        retentionDays: preset.value?.auditRetentionDays,
        enabled: preset.value?.auditEnabled,
      });
    } catch {
      config.value = null;
    } finally {
      configLoading.value = false;
    }
  }

  async function updateRetention(
    workspaceDataDir: string,
    days: number,
  ): Promise<boolean> {
    const ok = await updateAuditConfig(
      workspaceDataDir,
      days,
      settingsLocked.value,
    );
    if (ok) {
      await loadConfig(workspaceDataDir);
    }
    return ok;
  }

  return {
    entries,
    total,
    config,
    loading,
    configLoading,
    loadError,
    fetchAuditEntries,
    loadConfig,
    updateRetention,
  };
}
