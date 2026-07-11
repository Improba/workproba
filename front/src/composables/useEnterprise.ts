import { ref, type Ref } from 'vue';
import {
  getEnterprisePreset,
  isPresetActive,
  type EnterprisePreset,
} from '@composables/useDesktop';

const presetActive = ref(false);
const preset = ref<EnterprisePreset | null>(null);
const loading = ref(false);
const loadError = ref<string | null>(null);
let loadedOnce = false;

export interface UseEnterpriseReturn {
  presetActive: Ref<boolean>;
  preset: Ref<EnterprisePreset | null>;
  loading: Ref<boolean>;
  loadError: Ref<string | null>;
  refresh: () => Promise<void>;
}

export function useEnterprise(): UseEnterpriseReturn {
  async function refresh(): Promise<void> {
    loading.value = true;
    loadError.value = null;
    try {
      presetActive.value = await isPresetActive();
      preset.value = await getEnterprisePreset();
      loadedOnce = true;
    } catch (err) {
      presetActive.value = false;
      preset.value = null;
      loadError.value =
        err instanceof Error ? err.message : 'enterprise_load_failed';
    } finally {
      loading.value = false;
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (!loadedOnce && !loading.value) {
      await refresh();
    }
  }

  void ensureLoaded();

  return {
    presetActive,
    preset,
    loading,
    loadError,
    refresh,
  };
}
