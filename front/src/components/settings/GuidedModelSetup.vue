<template>
  <section class="guided-setup">
    <h2 class="guided-setup__section-title">{{ t('settings.engine.chooseEngine') }}</h2>

    <div class="guided-setup__cards" role="radiogroup" :aria-label="t('settings.engine.chooseEngine')">
      <article
        v-for="card in guidedCards"
        :key="card.set.id"
        class="guided-card"
        :class="{ 'guided-card--selected': activeSetId === card.set.id }"
      >
        <div class="guided-card__head">
          <span
            v-for="badge in card.displayBadges"
            :key="badge"
            class="guided-card__badge"
            :class="card.badgeToneClass"
          >
            {{ badge }}
          </span>
        </div>
        <h3 class="guided-card__title">{{ card.displayName }}</h3>
        <p class="guided-card__subtitle">{{ card.description }}</p>
        <ul v-if="card.capabilities.length" class="guided-card__caps" :aria-label="t('settings.advancedCapabilitiesAria')">
          <li v-for="cap in card.capabilities" :key="cap">{{ cap }}</li>
        </ul>
        <button
          type="button"
          class="guided-card__use"
          :class="{ 'guided-card__use--active': activeSetId === card.set.id }"
          @click="onUseEngine(card.set.id)"
        >
          {{
            activeSetId === card.set.id
              ? t('settings.engine.activeEngine')
              : t('settings.engine.useThisEngine')
          }}
        </button>
      </article>
    </div>

    <p v-if="cloudQuotaHint" class="guided-setup__cloud-hint">
      {{ cloudQuotaHint }}
    </p>
    <p
      v-if="cloudReadinessHint"
      class="guided-setup__cloud-hint guided-setup__cloud-hint--warn"
      role="status"
    >
      {{ cloudReadinessHint }}
    </p>

    <div v-if="selectedBuiltinId === 'mistral-default'" class="guided-setup__fields">
      <q-input
        v-model="accessKey"
        :label="t('settings.engine.accessKey')"
        outlined
        dense
        :type="showKey ? 'text' : 'password'"
        class="guided-setup__field"
        @update:model-value="onAccessKeyChange"
      >
        <template #append>
          <button type="button" class="reveal-btn" @click="showKey = !showKey">
            <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
          </button>
        </template>
      </q-input>
      <p class="guided-setup__hint">{{ t('settings.engine.accessKeyHint') }}</p>
    </div>

    <div v-else-if="selectedBuiltinId === 'ollama-local'" class="guided-setup__fields">
      <q-input
        v-model="ollamaUrl"
        :label="t('settings.engine.ollamaUrl')"
        outlined
        dense
        class="guided-setup__field"
        @update:model-value="onOllamaChange"
      />
      <div class="guided-setup__row">
        <q-select
          v-if="ollamaModels.length > 0"
          v-model="ollamaModel"
          :options="ollamaModels"
          :label="t('settings.ollamaModelDetected')"
          outlined
          dense
          class="guided-setup__field"
          @update:model-value="onOllamaChange"
        />
        <q-input
          v-else
          v-model="ollamaModel"
          :label="t('settings.engine.ollamaModel')"
          outlined
          dense
          :hint="t('settings.ollamaModelHint')"
          class="guided-setup__field"
          @update:model-value="onOllamaChange"
        />
        <button
          type="button"
          class="guided-setup__refresh"
          :disabled="refreshingOllama"
          @click="onRefreshOllama"
        >
          <Lucide name="refresh-cw" size="14" color="text" />
          {{ refreshingOllama ? t('settings.refreshing') : t('settings.refresh') }}
        </button>
      </div>
    </div>

    <div class="guided-setup__actions">
      <button
        type="button"
        class="guided-setup__test"
        :disabled="testing || !activeSetId"
        @click="onTest"
      >
        <Lucide name="plug-zap" size="14" color="wp-canard" />
        {{ testing ? t('settings.test.inProgress') : t('settings.engine.testEngine') }}
      </button>
      <ul v-if="testResults.length" class="guided-setup__test-results">
        <li
          v-for="item in testResults"
          :key="item.label"
          :class="{ 'guided-setup__test-results--ok': item.ok }"
        >
          <Lucide
            :name="item.ok ? 'check-circle-2' : 'alert-circle'"
            size="14"
            :color="item.ok ? 'success' : 'danger'"
          />
          {{ item.label }}
        </li>
      </ul>
    </div>

    <button type="button" class="guided-setup__advanced-link" @click="emit('switch-to-advanced')">
      {{ t('settings.advancedSettingsLink') }}
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings, testSet } from '@composables/useAppSettings';
import { useCloud } from '@composables/useCloud';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import type { ProviderSet } from '@composables/useDesktop.types';
import { fetchOllamaModels } from '@services/ollamaModels';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import { validateProviderSetChatReady } from '@utils/providerSetValidation';
import {
  applyAccessKeyToSet,
  applyOllamaOverrides,
  capabilityLabels,
  cloneProviderSet,
  localizedSetDescription,
  localizedSetName,
  WORKPROBA_CLOUD_BUILTIN_SET,
} from '@utils/providerSets';

const emit = defineEmits<{
  'switch-to-advanced': [];
}>();

const { sets, activeSet, load, setActiveSet, updateSet, settings } = useAppSettings();
const {
  quota,
  quotaLoading,
  providerReadiness,
  isEnrolled,
  init: initCloud,
  refreshQuota,
} = useCloud();
const { getPluginDataDir } = usePlugins();
const { t } = useI18n();

const accessKey = ref('');
const ollamaUrl = ref('http://127.0.0.1:11434');
const ollamaModel = ref('llama3.2');
const showKey = ref(false);
const testing = ref(false);
const refreshingOllama = ref(false);
const ollamaModels = ref<string[]>([]);
const testResults = ref<Array<{ ok: boolean; label: string }>>([]);

const activeSetId = computed(() => settings.value.activeSetId ?? activeSet.value?.id ?? null);

const guidedCards = computed(() => {
  const builtins = sets.value.filter((s) => s.isBuiltin);
  const cards = builtins.length ? builtins : sets.value;
  return cards.map((set) => {
    const description = localizedSetDescription(set, t);
    const displayBadges =
      set.id === 'workproba-cloud'
        ? [t('settings.badgeCloud'), t('settings.badgeRecommended')]
        : set.id === 'mistral-default'
          ? [t('settings.badgeRecommended')]
          : set.id === 'ollama-local'
            ? [t('settings.badgeLocal')]
            : set.badges;
    const badgeToneClass =
      set.id === 'workproba-cloud'
        ? 'guided-card__badge--cloud'
        : set.id === 'mistral-default'
          ? 'guided-card__badge--recommended'
          : set.id === 'ollama-local'
            ? 'guided-card__badge--local'
            : 'guided-card__badge--cloud';
    return {
      set,
      displayName: localizedSetName(set, t),
      description,
      displayBadges,
      badgeToneClass,
      capabilities: capabilityLabels(set, 'guided', t),
    };
  });
});

const selectedBuiltinId = computed(() => activeSet.value?.id ?? null);

const cloudQuotaHint = computed(() => {
  if (selectedBuiltinId.value !== WORKPROBA_CLOUD_BUILTIN_SET.id) return '';
  if (!isEnrolled.value) return '';
  if (quotaLoading.value) return t('cloud.quotaLoading');
  if (!quota.value) return '';
  if (!quota.value.enabled) return t('cloud.quotaDisabled');
  return t('cloud.quotaSummary', {
    tokens: quota.value.remainingTokens.toLocaleString(),
    requests: quota.value.remainingRequests.toLocaleString(),
  });
});

const cloudReadinessHint = computed(() => {
  if (selectedBuiltinId.value !== WORKPROBA_CLOUD_BUILTIN_SET.id) return '';
  const readiness = providerReadiness.value;
  if (!readiness) return '';
  const check = validateProviderSetChatReady(WORKPROBA_CLOUD_BUILTIN_SET, readiness);
  if (check.ok) return '';
  return chatErrorMessageForReadiness(check.reason);
});

function hydrateFromActiveSet(set: ProviderSet | null): void {
  if (!set) return;
  accessKey.value = set.chat.apiKey ?? '';
  ollamaUrl.value = set.chat.baseUrl?.replace(/\/v1\/?$/, '') ?? 'http://127.0.0.1:11434';
  ollamaModel.value = set.chat.model;
}

async function persistSet(next: ProviderSet): Promise<void> {
  await updateSet(next);
}

async function onUseEngine(id: string): Promise<void> {
  testResults.value = [];
  try {
    await setActiveSet(id);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
  }
}

async function onAccessKeyChange(): Promise<void> {
  testResults.value = [];
  const current = activeSet.value;
  if (!current || current.id !== 'mistral-default') return;
  try {
    await persistSet(applyAccessKeyToSet(current, accessKey.value));
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
  }
}

async function onOllamaChange(): Promise<void> {
  testResults.value = [];
  const current = activeSet.value;
  if (!current || current.id !== 'ollama-local') return;
  try {
    await persistSet(applyOllamaOverrides(current, ollamaUrl.value, ollamaModel.value));
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
  }
}

async function onTest(): Promise<void> {
  const set = activeSet.value;
  if (!set) return;
  testing.value = true;
  testResults.value = [];
  try {
    const cloudPluginDataDir =
      set.authMode === 'device_bearer'
        ? await getPluginDataDir(CLOUD_PLUGIN_ID)
        : null;
    const result = await testSet(cloneProviderSet(set), { cloudPluginDataDir });
    testResults.value = [
      {
        ok: result.chat.ok,
        label: result.chat.ok ? t('settings.test.chatOk') : t('settings.test.chatFailed'),
      },
      {
        ok: result.embeddings.ok,
        label: result.embeddings.ok
          ? t('settings.test.embeddingsOk')
          : t('settings.test.embeddingsFailed'),
      },
      {
        ok: result.ocr.ok,
        label: result.ocr.ok ? t('settings.test.ocrOk') : t('settings.test.ocrFailed'),
      },
      {
        ok: result.vision.ok,
        label: result.vision.ok ? t('settings.test.visionOk') : t('settings.test.visionFailed'),
      },
    ];
  } catch {
    testResults.value = [{ ok: false, label: t('settings.sidecarUnreachableShort') }];
  } finally {
    testing.value = false;
  }
}

async function onRefreshOllama(): Promise<void> {
  refreshingOllama.value = true;
  try {
    const models = await fetchOllamaModels(ollamaUrl.value);
    ollamaModels.value = models;
    if (models.length > 0 && !models.includes(ollamaModel.value)) {
      ollamaModel.value = models[0];
      await onOllamaChange();
    }
  } catch (err) {
    ollamaModels.value = [];
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.testOllamaUnreachable'),
      color: 'warning',
    });
  } finally {
    refreshingOllama.value = false;
  }
}

onMounted(async () => {
  await load();
  await initCloud();
  hydrateFromActiveSet(activeSet.value);
  if (activeSet.value?.id === 'ollama-local') {
    void onRefreshOllama();
  }
  if (activeSet.value?.id === WORKPROBA_CLOUD_BUILTIN_SET.id) {
    void refreshQuota();
  }
});

watch(activeSet, (set) => {
  hydrateFromActiveSet(set);
  if (set?.id === WORKPROBA_CLOUD_BUILTIN_SET.id) {
    void refreshQuota();
  }
});
</script>

<style scoped lang="scss">
.guided-setup {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guided-setup__section-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.guided-setup__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.guided-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 2px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.guided-card--selected {
  border-color: var(--wp-accent);
  box-shadow: 0 0 0 3px var(--wp-accent-soft);
}

.guided-card__head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.guided-card__badge {
  font-size: var(--wp-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
}

.guided-card__badge--recommended {
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
}

.guided-card__badge--local {
  background: var(--wp-success-soft, var(--wp-accent-soft));
  color: var(--wp-success);
}

.guided-card__badge--cloud {
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.guided-card__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.guided-card__subtitle {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.guided-card__caps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.guided-card__caps li {
  font-size: var(--wp-fs-xs);
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.guided-card__use {
  align-self: flex-start;
  margin-top: 4px;
  padding: 8px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
  cursor: pointer;

  &:hover {
    border-color: var(--wp-accent);
    background: var(--wp-accent-soft);
  }
}

.guided-card__use--active {
  border-color: var(--wp-accent);
  background: var(--wp-accent);
  color: var(--wp-canard);
}

.guided-setup__fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.guided-setup__row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.guided-setup__field {
  flex: 1;
  min-width: 200px;
}

.guided-setup__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.guided-setup__cloud-hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.guided-setup__cloud-hint--warn {
  color: var(--wp-danger);
}

.guided-setup__refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-top: 2px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.guided-setup__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guided-setup__test {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }
  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.guided-setup__test-results {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--wp-fs-sm);
  color: var(--wp-danger);

  li {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  &--ok,
  li.guided-setup__test-results--ok {
    color: var(--wp-success);
  }
}

.guided-setup__advanced-link {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-decoration: underline;
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
  }
}

.reveal-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  padding: 2px;
}
</style>
