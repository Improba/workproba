<template>
  <div class="cloud-panel">
    <div class="cloud-panel__badge">
      {{ t('cloud.experimental') }}
    </div>

    <p v-if="displayLoadError" class="cloud-panel__error" role="alert">
      {{ displayLoadError }}
    </p>

    <p v-if="displayProjectsLoadError" class="cloud-panel__error" role="alert">
      {{ displayProjectsLoadError }}
    </p>

    <!-- Visage final (guidé / verrouillé) -->
    <template v-if="isFinalFace">
      <section v-if="!status?.enrolled" class="cloud-panel__section">
        <h3 class="cloud-panel__section-title">{{ t('cloud.joinTitle') }}</h3>
        <p class="cloud-panel__hint">{{ t('cloud.joinHint') }}</p>
        <form class="cloud-panel__config-form" @submit.prevent="onJoin">
          <input
            v-model="joinTokenDraft"
            type="text"
            class="cloud-panel__input"
            :placeholder="t('cloud.invitationCode')"
            :disabled="loading || joining"
            autocomplete="off"
          />
          <input
            v-if="showCloudUrlField"
            v-model="baseUrlDraft"
            type="url"
            class="cloud-panel__input"
            :placeholder="t('cloud.baseUrl')"
            :disabled="loading || joining"
          />
          <button
            type="submit"
            class="cloud-panel__save-btn"
            :disabled="loading || joining || !joinTokenDraft.trim() || (showCloudUrlField && !baseUrlDraft.trim())"
          >
            {{ joining ? t('cloud.joining') : t('cloud.join') }}
          </button>
        </form>
        <button
          v-if="!isTechnicalFace"
          type="button"
          class="cloud-panel__link-btn"
          @click="showAdvancedOptions = true"
        >
          {{ t('cloud.advancedOptions') }}
        </button>
      </section>

      <section v-else class="cloud-panel__section">
        <h3 class="cloud-panel__section-title">
          {{ t('cloud.connectedTo', { org: connectedOrgLabel }) }}
        </h3>
        <dl class="cloud-panel__status">
          <div>
            <dt>{{ t('cloud.statusSyncedCount') }}</dt>
            <dd>{{ status?.synced_count ?? 0 }}</dd>
          </div>
          <div>
            <dt>{{ t('cloud.statusLastSync') }}</dt>
            <dd>{{ lastSyncLabel }}</dd>
          </div>
        </dl>
        <button
          type="button"
          class="cloud-panel__regards-btn"
          :disabled="loading || syncingRegards"
          @click="onSyncRegards"
        >
          {{ syncingRegards ? t('cloud.syncingRegards') : t('cloud.syncRegards') }}
        </button>
        <button
          type="button"
          class="cloud-panel__disconnect-btn"
          :disabled="loading || disconnecting"
          @click="onDisconnect"
        >
          {{ disconnecting ? t('cloud.disconnecting') : t('cloud.disconnect') }}
        </button>
        <button
          v-if="!isTechnicalFace"
          type="button"
          class="cloud-panel__link-btn"
          @click="showAdvancedOptions = true"
        >
          {{ t('cloud.cacheOptions') }}
        </button>
      </section>
    </template>

    <!-- Visage technique (admin / avancé) -->
    <section
      v-if="isTechnicalFace || showAdvancedOptions"
      class="cloud-panel__section cloud-panel__section--advanced"
    >
      <h3 class="cloud-panel__section-title">{{ t('cloud.advancedOptions') }}</h3>
      <h4 class="cloud-panel__subsection-title">{{ t('cloud.enrollTitle') }}</h4>
      <p class="cloud-panel__hint">{{ t('cloud.enrollHint') }}</p>
      <form class="cloud-panel__config-form" @submit.prevent="onSaveEnroll">
        <input
          v-model="baseUrlDraft"
          type="url"
          class="cloud-panel__input"
          :placeholder="t('cloud.baseUrl')"
          :disabled="loading || savingEnroll"
        />
        <input
          v-model="bearerTokenDraft"
          type="password"
          class="cloud-panel__input"
          :placeholder="t('cloud.bearerToken')"
          :disabled="loading || savingEnroll"
        />
        <button
          type="submit"
          class="cloud-panel__save-btn"
          :disabled="loading || savingEnroll || !baseUrlDraft.trim() || !bearerTokenDraft.trim()"
        >
          {{ t('cloud.enrollSave') }}
        </button>
      </form>

      <h4 class="cloud-panel__subsection-title">{{ t('cloud.mountPathTitle') }}</h4>
      <p class="cloud-panel__hint">{{ t('cloud.mountPathHint') }}</p>
      <form class="cloud-panel__config-form" @submit.prevent="onSaveMountPath">
        <input
          v-model="mountPathDraft"
          type="text"
          class="cloud-panel__input"
          :placeholder="t('cloud.mountPathPlaceholder')"
          :disabled="loading || savingConfig"
        />
        <button
          type="button"
          class="cloud-panel__pick-btn"
          :disabled="loading || savingConfig"
          @click="onPickFolder"
        >
          {{ t('cloud.browse') }}
        </button>
        <button
          type="submit"
          class="cloud-panel__save-btn"
          :disabled="loading || savingConfig || !mountPathDraft.trim()"
        >
          {{ t('cloud.saveMountPath') }}
        </button>
      </form>

      <h4 class="cloud-panel__subsection-title">{{ t('cloud.statusTitle') }}</h4>
      <dl class="cloud-panel__status">
        <div>
          <dt>{{ t('cloud.statusConfigured') }}</dt>
          <dd>{{ status?.configured ? t('common.yes') : t('common.no') }}</dd>
        </div>
        <div>
          <dt>{{ t('cloud.enrolled') }}</dt>
          <dd>{{ status?.enrolled ? t('common.yes') : t('common.no') }}</dd>
        </div>
        <div>
          <dt>{{ t('cloud.bearerToken') }}</dt>
          <dd>{{ status?.has_token ? t('cloud.tokenActive') : t('cloud.tokenMissing') }}</dd>
        </div>
        <div v-if="status?.base_url">
          <dt>{{ t('cloud.baseUrl') }}</dt>
          <dd>{{ status.base_url }}</dd>
        </div>
        <div>
          <dt>{{ t('cloud.statusLastSync') }}</dt>
          <dd>{{ lastSyncLabel }}</dd>
        </div>
        <div>
          <dt>{{ t('cloud.statusSyncedCount') }}</dt>
          <dd>{{ status?.synced_count ?? 0 }}</dd>
        </div>
      </dl>
    </section>

    <section class="cloud-panel__section">
      <div class="cloud-panel__section-head">
        <h3 class="cloud-panel__section-title">{{ t('cloud.projectsTitle') }}</h3>
        <button
          type="button"
          class="cloud-panel__refresh-btn"
          :disabled="loading || syncing || pulling"
          @click="refreshProjects"
        >
          {{ t('common.refresh') }}
        </button>
      </div>

      <p v-if="loading && !projects.length" class="cloud-panel__loading">
        {{ t('common.loading') }}
      </p>
      <p v-else-if="!projects.length && !projectsLoadError" class="cloud-panel__empty">
        {{ t('cloud.noProjects') }}
      </p>
      <ul v-else class="cloud-panel__projects" role="list">
        <li v-for="project in projects" :key="project.id" class="cloud-panel__project">
          <span class="cloud-panel__project-name">{{ project.name }}</span>
          <div v-if="showCacheOperations" class="cloud-panel__project-actions">
            <button
              type="button"
              class="cloud-panel__sync-btn"
              :disabled="syncing || pulling || !canSync"
              @click="onSync(project.id)"
            >
              {{ syncing ? t('cloud.syncing') : t('cloud.pushLocalCache') }}
            </button>
            <button
              type="button"
              class="cloud-panel__pull-btn"
              :disabled="syncing || pulling || !canSync"
              @click="onPull(project.id)"
            >
              {{ pulling ? t('cloud.syncing') : t('cloud.reloadCache') }}
            </button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Dialog, Notify } from 'quasar';
import { useCloud } from '@composables/useCloud';
import { useAppSettings } from '@composables/useAppSettings';
import { PROJET_PLUGIN_ID, PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { pickProjectFolder } from '@composables/useDesktop';
import { resolveUiMode, listProjetProjects, type ProjetProject } from '@services/aiSidecar';
import { usePersonas } from '@composables/usePersonas';

const { t } = useI18n();
const emit = defineEmits<{
  (e: 'artefactsChanged'): void;
  (e: 'regardsChanged'): void;
}>();
const { settings, settingsLocked, settingsMode } = useAppSettings();
const { isProjetPluginActive, getPluginDataDir } = usePlugins();
const { refresh: refreshPersonas } = usePersonas();
const {
  status,
  loading,
  syncing,
  pulling,
  syncingRegards,
  loadError,
  init,
  refreshStatus,
  configure,
  enroll,
  disconnect,
  sync,
  pull,
  syncRegards,
} = useCloud();

const mountPathDraft = ref('');
const baseUrlDraft = ref('');
const bearerTokenDraft = ref('');
const joinTokenDraft = ref('');
const savingConfig = ref(false);
const savingEnroll = ref(false);
const joining = ref(false);
const disconnecting = ref(false);
const showAdvancedOptions = ref(false);
const projects = ref<ProjetProject[]>([]);
const projectsLoadError = ref<string | null>(null);

const uiMode = computed(() => resolveUiMode(settingsLocked.value, settingsMode.value));
const isTechnicalFace = computed(() => uiMode.value === 'advanced');
const isFinalFace = computed(() => !isTechnicalFace.value);
const showCacheOperations = computed(
  () => !status.value?.enrolled && (isTechnicalFace.value || showAdvancedOptions.value),
);

const presetCloudUrl = computed(() => settings.value.cloudEndpoint?.trim() ?? '');
const showCloudUrlField = computed(
  () => !status.value?.base_url && !presetCloudUrl.value,
);

const connectedOrgLabel = computed(
  () => status.value?.org_label ?? status.value?.org_id ?? t('cloud.unknownOrg'),
);

const canSync = computed(() => Boolean(status.value?.configured || status.value?.enrolled));

const lastSyncLabel = computed(() => {
  const raw = status.value?.last_sync;
  if (!raw) return t('cloud.neverSynced');
  try {
    return new Date(raw).toLocaleString();
  } catch {
    return raw;
  }
});

function isTechnicalError(message: string): boolean {
  const trimmed = message.trim();
  if (!trimmed) return false;
  if (/^[a-z][a-z0-9_]*$/.test(trimmed)) return true;
  if (/^(get|post|put|delete|patch)\s/i.test(trimmed)) return true;
  if (/\b(4\d{2}|5\d{2})\b/.test(trimmed) && /http|fetch|request|status/i.test(trimmed)) {
    return true;
  }
  return /\b(bearer|token|enroll|blob|mount_path|stubbearer|api)\b/i.test(trimmed);
}

function humanizeError(raw: string | null, fallbackKey: string): string | null {
  if (!raw) return null;
  if (isTechnicalError(raw)) return t(fallbackKey);
  return raw;
}

const displayLoadError = computed(() => humanizeError(loadError.value, 'cloud.loadFailed'));
const displayProjectsLoadError = computed(() =>
  humanizeError(projectsLoadError.value, 'cloud.projectsLoadFailed'),
);

function notifyError(raw: string | null, fallbackKey: string): void {
  Notify.create({
    message: humanizeError(raw, fallbackKey) ?? t(fallbackKey),
    color: 'negative',
  });
}

async function confirmAction(opts: {
  title: string;
  message: string;
  okLabel: string;
  okColor?: string;
}): Promise<boolean> {
  return new Promise<boolean>((resolve) => {
    Dialog.create({
      title: opts.title,
      message: opts.message,
      cancel: { label: t('common.cancel'), flat: true },
      ok: { label: opts.okLabel, color: opts.okColor ?? 'primary' },
      persistent: true,
    })
      .onOk(() => resolve(true))
      .onCancel(() => resolve(false))
      .onDismiss(() => resolve(false));
  });
}

function resolveBaseUrl(): string {
  return (
    baseUrlDraft.value.trim()
    || status.value?.base_url?.trim()
    || presetCloudUrl.value
    || ''
  );
}

async function refreshProjects(): Promise<void> {
  projectsLoadError.value = null;
  if (!isProjetPluginActive.value) {
    projects.value = [];
    return;
  }
  const dataDir = await getPluginDataDir(PROJET_PLUGIN_ID);
  if (!dataDir) {
    projects.value = [];
    return;
  }
  const result = await listProjetProjects(dataDir);
  if (!result.ok) {
    projects.value = [];
    projectsLoadError.value = humanizeError(result.error, 'cloud.projectsLoadFailed')
      ?? t('cloud.projectsLoadFailed');
    return;
  }
  projects.value = result.data;
}

async function bootstrap(): Promise<void> {
  await init();
  mountPathDraft.value = status.value?.mount_path ?? '';
  baseUrlDraft.value = status.value?.base_url ?? presetCloudUrl.value;
  await refreshProjects();
}

async function onPickFolder(): Promise<void> {
  const folder = await pickProjectFolder();
  if (folder) {
    mountPathDraft.value = folder;
  }
}

async function onSaveMountPath(): Promise<void> {
  savingConfig.value = true;
  try {
    const ok = await configure(mountPathDraft.value);
    if (ok) {
      Notify.create({
        message: t('cloud.mountPathSaved'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      notifyError(loadError.value, 'cloud.mountPathSaveFailed');
    }
  } finally {
    savingConfig.value = false;
  }
}

async function onJoin(): Promise<void> {
  const baseUrl = resolveBaseUrl();
  if (!baseUrl) {
    Notify.create({
      message: t('cloud.baseUrlRequired'),
      color: 'negative',
    });
    return;
  }
  joining.value = true;
  try {
    const ok = await enroll({ baseUrl, joinToken: joinTokenDraft.value });
    if (ok) {
      joinTokenDraft.value = '';
      Notify.create({
        message: t('cloud.joinSuccess'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      notifyError(loadError.value, 'cloud.joinFailed');
    }
  } finally {
    joining.value = false;
  }
}

async function onSaveEnroll(): Promise<void> {
  savingEnroll.value = true;
  try {
    const ok = await enroll({
      baseUrl: baseUrlDraft.value,
      bearerToken: bearerTokenDraft.value,
    });
    if (ok) {
      bearerTokenDraft.value = '';
      Notify.create({
        message: t('cloud.enrolled'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      notifyError(loadError.value, 'cloud.syncFailed');
    }
  } finally {
    savingEnroll.value = false;
  }
}

async function onSyncRegards(): Promise<void> {
  const result = await syncRegards();
  if (!result.ok) {
    notifyError(loadError.value ?? result.error, 'cloud.syncRegardsFailed');
    return;
  }
  if (result.data.count > 0) {
    const personasDir = await getPluginDataDir(PERSONAS_PLUGIN_ID);
    if (personasDir) {
      await refreshPersonas(personasDir);
    }
    emit('regardsChanged');
    Notify.create({
      message: t('cloud.syncRegardsSuccess', { count: result.data.count }),
      color: 'positive',
      timeout: 2500,
    });
  } else {
    Notify.create({
      message: t('cloud.syncRegardsEmpty'),
      color: 'info',
      timeout: 2500,
    });
  }
}

async function onDisconnect(): Promise<void> {
  const confirmed = await confirmAction({
    title: t('cloud.disconnectConfirmTitle'),
    message: t('cloud.disconnectConfirmMessage', { org: connectedOrgLabel.value }),
    okLabel: t('cloud.disconnect'),
    okColor: 'negative',
  });
  if (!confirmed) return;

  disconnecting.value = true;
  try {
    const ok = await disconnect();
    if (ok) {
      Notify.create({
        message: t('cloud.disconnected'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      notifyError(loadError.value, 'cloud.disconnectFailed');
    }
  } finally {
    disconnecting.value = false;
  }
}

async function onSync(projectId: string): Promise<void> {
  const confirmed = await confirmAction({
    title: t('cloud.syncConfirmTitle'),
    message: t('cloud.syncConfirmMessage'),
    okLabel: t('cloud.syncNow'),
  });
  if (!confirmed) return;

  const result = await sync(projectId);
  if (!result.ok) {
    notifyError(loadError.value ?? result.error, 'cloud.syncFailed');
    return;
  }
  const syncedCount = result.data.synced.length;
  const blobsUploaded = result.data.blobs_uploaded?.length ?? 0;

  if (syncedCount > 0 || blobsUploaded > 0) {
    Notify.create({
      message:
        blobsUploaded > 0
          ? t('cloud.syncCloudSuccess', { count: syncedCount, blobs: blobsUploaded })
          : t('cloud.syncSuccess', { count: syncedCount }),
      color: 'positive',
      timeout: 2500,
    });
  } else {
    Notify.create({
      message: t('cloud.syncEmpty'),
      color: 'info',
      timeout: 2500,
    });
  }
}

async function onPull(projectId: string): Promise<void> {
  const confirmed = await confirmAction({
    title: t('cloud.pullConfirmTitle'),
    message: t('cloud.pullConfirmMessage'),
    okLabel: t('cloud.pullNow'),
  });
  if (!confirmed) return;

  const result = await pull(projectId);
  if (!result.ok) {
    notifyError(loadError.value ?? result.error, 'cloud.pullFailed');
    return;
  }

  const pullErrors = result.data.errors ?? [];
  const pullSkipped = result.data.skipped ?? [];
  if (pullErrors.length > 0) {
    const detail = pullErrors.slice(0, 3).join('; ');
    Notify.create({
      message: t('cloud.pullErrorsNotify', { count: pullErrors.length, detail }),
      color: 'negative',
      timeout: 4000,
    });
  }

  if (pullSkipped.length > 0) {
    const detail = pullSkipped.slice(0, 3).join('; ');
    Notify.create({
      message: t('cloud.pullSkippedNotify', { count: pullSkipped.length, detail }),
      color: 'info',
      timeout: 4000,
    });
  }

  if (result.data.pulled.length > 0) {
    emit('artefactsChanged');
    Notify.create({
      message: t('cloud.pullSuccess', { count: result.data.pulled.length }),
      color: 'positive',
      timeout: 2500,
    });
  } else if (pullErrors.length === 0 && pullSkipped.length === 0) {
    Notify.create({
      message: t('cloud.pullEmpty'),
      color: 'info',
      timeout: 2500,
    });
  }
}

watch(isProjetPluginActive, () => {
  void refreshProjects();
});

watch(status, (next) => {
  if (next?.mount_path) {
    mountPathDraft.value = next.mount_path;
  }
  if (next?.base_url) {
    baseUrlDraft.value = next.base_url;
  } else if (presetCloudUrl.value) {
    baseUrlDraft.value = presetCloudUrl.value;
  }
});

onMounted(() => {
  void bootstrap();
});

defineExpose({
  refresh: async () => {
    await refreshStatus();
    await refreshProjects();
  },
});
</script>

<style scoped lang="scss">
.cloud-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  min-height: 0;
  overflow-y: auto;
}

.cloud-panel__empty,
.cloud-panel__loading {
  padding: 24px 8px;
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__badge {
  align-self: flex-start;
  font-size: var(--wp-fs-xs);
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft, var(--wp-surface-3));
  color: var(--wp-gold, var(--wp-text-muted));
  font-weight: 600;
}

.cloud-panel__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid var(--wp-border);

  &:first-of-type {
    border-top: none;
    padding-top: 0;
  }
}

.cloud-panel__section--advanced {
  border-top: 1px dashed var(--wp-border);
}

.cloud-panel__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.cloud-panel__section-title {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.cloud-panel__subsection-title {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
}

.cloud-panel__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.cloud-panel__config-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cloud-panel__input {
  flex: 1 1 180px;
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__pick-btn,
.cloud-panel__save-btn,
.cloud-panel__refresh-btn,
.cloud-panel__sync-btn,
.cloud-panel__pull-btn,
.cloud-panel__regards-btn,
.cloud-panel__disconnect-btn {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.cloud-panel__save-btn {
  color: var(--wp-accent);
  border-color: var(--wp-accent);
}

.cloud-panel__disconnect-btn {
  align-self: flex-start;
  color: var(--wp-danger);
  border-color: var(--wp-danger);
}

.cloud-panel__link-btn {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
  text-decoration: underline;
}

.cloud-panel__status {
  margin: 0;
  display: grid;
  gap: 8px;
  font-size: var(--wp-fs-xs);

  dt {
    color: var(--wp-text-faint);
  }

  dd {
    margin: 0;
    color: var(--wp-text);
  }
}

.cloud-panel__projects {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cloud-panel__project {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
}

.cloud-panel__project-name {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.cloud-panel__project-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
