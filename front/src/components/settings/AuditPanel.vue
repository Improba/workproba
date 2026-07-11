<template>
  <section class="audit-panel">
    <header class="audit-panel__header">
      <h2 class="audit-panel__title">{{ t('audit.title') }}</h2>
      <p class="audit-panel__subtitle">{{ t('audit.subtitle') }}</p>
    </header>

    <div v-if="!workspaceDataDir" class="audit-panel__empty">
      {{ t('audit.noWorkspace') }}
    </div>

    <template v-else>
      <div class="audit-panel__filters">
        <label class="audit-panel__field">
          <span>{{ t('audit.filterEvent') }}</span>
          <input
            v-model="eventFilter"
            type="text"
            class="audit-panel__input"
            :placeholder="t('audit.filterEventPlaceholder')"
            :disabled="loading"
            @keyup.enter="applyFilters"
          />
        </label>
        <label class="audit-panel__field">
          <span>{{ t('audit.filterFrom') }}</span>
          <input
            v-model="fromFilter"
            type="date"
            class="audit-panel__input"
            :disabled="loading"
          />
        </label>
        <label class="audit-panel__field">
          <span>{{ t('audit.filterTo') }}</span>
          <input
            v-model="toFilter"
            type="date"
            class="audit-panel__input"
            :disabled="loading"
          />
        </label>
        <label class="audit-panel__field audit-panel__field--search">
          <span>{{ t('audit.filterSearch') }}</span>
          <input
            v-model="searchFilter"
            type="search"
            class="audit-panel__input"
            :placeholder="t('audit.filterSearchPlaceholder')"
            :disabled="loading"
            @keyup.enter="applyFilters"
          />
        </label>
        <button
          type="button"
          class="audit-panel__apply"
          :disabled="loading"
          @click="applyFilters"
        >
          {{ t('audit.applyFilters') }}
        </button>
        <button
          type="button"
          class="audit-panel__export"
          :disabled="loading || exporting || !workspaceDataDir"
          @click="onExportCsv"
        >
          {{ exporting ? t('audit.exporting') : t('audit.exportCsv') }}
        </button>
      </div>

      <p v-if="loadError" class="audit-panel__error" role="alert">
        {{ t('audit.loadFailed') }}
      </p>

      <div v-else-if="loading" class="audit-panel__empty">
        {{ t('common.loading') }}
      </div>

      <div v-else-if="entries.length === 0" class="audit-panel__empty">
        {{ t('audit.empty') }}
      </div>

      <div v-else class="audit-panel__table-wrap">
        <table class="audit-panel__table">
          <thead>
            <tr>
              <th scope="col">{{ t('audit.colTimestamp') }}</th>
              <th scope="col">{{ t('audit.colEvent') }}</th>
              <th scope="col">{{ t('audit.colActor') }}</th>
              <th scope="col">{{ t('audit.colDetails') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, index) in filteredEntries" :key="`${entry.timestamp}-${index}`">
              <td>{{ formatTimestamp(entry.timestamp) }}</td>
              <td>{{ entry.event }}</td>
              <td>{{ entry.actor }}</td>
              <td>{{ formatDetails(entry.details) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="audit-panel__count">
          {{ t('audit.totalCount', { shown: filteredEntries.length, total }) }}
        </p>
      </div>

      <section v-if="showRetentionConfig" class="audit-panel__retention">
        <h3 class="audit-panel__retention-title">{{ t('audit.retentionTitle') }}</h3>
        <p v-if="retentionLocked" class="audit-panel__retention-locked">
          {{ t('audit.retentionLocked', { days: config?.retention_days ?? presetRetentionDays }) }}
        </p>
        <form v-else class="audit-panel__retention-form" @submit.prevent="onSaveRetention">
          <label class="audit-panel__field">
            <span>{{ t('audit.retentionDays') }}</span>
            <input
              v-model.number="retentionDraft"
              type="number"
              min="1"
              max="3650"
              class="audit-panel__input audit-panel__input--narrow"
              :disabled="configLoading || savingRetention"
            />
          </label>
          <button
            type="submit"
            class="audit-panel__apply"
            :disabled="configLoading || savingRetention"
          >
            {{ t('audit.retentionSave') }}
          </button>
        </form>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import { useAudit } from '@composables/useAudit';
import { useEnterprise } from '@composables/useEnterprise';
import type { AuditEntry } from '@services/aiSidecar';
import { exportAuditCsv } from '@services/aiSidecar';

const props = defineProps<{
  workspaceDataDir?: string | null;
}>();

const { t } = useI18n();
const { settingsMode, settingsLocked } = useAppSettings();
const { preset } = useEnterprise();
const {
  entries,
  total,
  config,
  loading,
  configLoading,
  loadError,
  fetchAuditEntries,
  loadConfig,
  updateRetention,
} = useAudit();

const eventFilter = ref('');
const fromFilter = ref('');
const toFilter = ref('');
const searchFilter = ref('');
const retentionDraft = ref(90);
const savingRetention = ref(false);
const exporting = ref(false);

const showRetentionConfig = computed(
  () => settingsMode.value === 'advanced' || settingsLocked.value,
);

const retentionLocked = computed(
  () => settingsLocked.value || preset.value?.auditRetentionDays != null,
);

const presetRetentionDays = computed(
  () => preset.value?.auditRetentionDays ?? config.value?.retention_days ?? 90,
);

function formatDetails(details: AuditEntry['details']): string {
  if (details == null) return '';
  if (typeof details === 'string') return details;
  try {
    return JSON.stringify(details);
  } catch {
    return String(details);
  }
}

const filteredEntries = computed(() => {
  const query = searchFilter.value.trim().toLowerCase();
  if (!query) return entries.value;
  return entries.value.filter(
    (entry) =>
      entry.event.toLowerCase().includes(query)
      || entry.actor.toLowerCase().includes(query)
      || formatDetails(entry.details).toLowerCase().includes(query),
  );
});

function formatTimestamp(value: string): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

async function applyFilters(): Promise<void> {
  if (!props.workspaceDataDir) return;
  await fetchAuditEntries({
    workspaceDataDir: props.workspaceDataDir,
    event: eventFilter.value.trim() || null,
    from: fromFilter.value ? `${fromFilter.value}T00:00:00Z` : null,
    to: toFilter.value ? `${toFilter.value}T23:59:59Z` : null,
    limit: 200,
  });
}

async function loadAll(): Promise<void> {
  if (!props.workspaceDataDir) return;
  await Promise.all([
    applyFilters(),
    loadConfig(props.workspaceDataDir),
  ]);
  retentionDraft.value = config.value?.retention_days ?? presetRetentionDays.value;
}

async function onSaveRetention(): Promise<void> {
  if (!props.workspaceDataDir || retentionLocked.value) return;
  savingRetention.value = true;
  try {
    const ok = await updateRetention(props.workspaceDataDir, retentionDraft.value);
    if (ok) {
      Notify.create({
        message: t('audit.retentionSaved'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      Notify.create({
        message: t('audit.retentionSaveFailed'),
        color: 'negative',
      });
    }
  } finally {
    savingRetention.value = false;
  }
}

async function onExportCsv(): Promise<void> {
  if (!props.workspaceDataDir) return;
  exporting.value = true;
  try {
    const blob = await exportAuditCsv({
      workspaceDataDir: props.workspaceDataDir,
      event: eventFilter.value.trim() || null,
      from: fromFilter.value ? `${fromFilter.value}T00:00:00Z` : null,
      to: toFilter.value ? `${toFilter.value}T23:59:59Z` : null,
    });
    if (!blob) {
      Notify.create({
        message: t('audit.exportFailed'),
        color: 'negative',
      });
      return;
    }
    const stamp = new Date().toISOString().slice(0, 10);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `audit-${stamp}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

watch(
  () => props.workspaceDataDir,
  () => {
    void loadAll();
  },
);

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.audit-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.audit-panel__header {
  margin-bottom: 0.25rem;
}

.audit-panel__title {
  margin: 0 0 0.25rem;
  font-family: var(--wp-font-head);
  font-size: 1rem;
  font-weight: 700;
  color: var(--wp-text);
}

.audit-panel__subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.audit-panel__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
}

.audit-panel__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);

  &--search {
    flex: 1 1 180px;
  }
}

.audit-panel__input {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &--narrow {
    width: 96px;
  }
}

.audit-panel__apply {
  min-height: 34px;
  padding: 6px 12px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.audit-panel__export {
  min-height: 34px;
  padding: 6px 12px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.audit-panel__empty {
  padding: 16px 4px;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
}

.audit-panel__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.audit-panel__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
}

.audit-panel__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--wp-fs-xs);

  th,
  td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--wp-border);
    text-align: left;
    vertical-align: top;
  }

  th {
    background: var(--wp-surface-2);
    color: var(--wp-text-muted);
    font-weight: 600;
  }

  td {
    color: var(--wp-text);
  }
}

.audit-panel__count {
  margin: 0;
  padding: 8px 10px;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.audit-panel__retention {
  padding-top: 8px;
  border-top: 1px solid var(--wp-border);
}

.audit-panel__retention-title {
  margin: 0 0 8px;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.audit-panel__retention-locked {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.audit-panel__retention-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
}
</style>
