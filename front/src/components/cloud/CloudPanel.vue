<template>
  <div class="cloud-panel" :aria-label="t('cloud.tabLabel')">
    <p v-if="displayLoadError" class="cloud-panel__error" role="alert">
      {{ displayLoadError }}
    </p>

    <p v-if="displayProjectsLoadError" class="cloud-panel__error" role="alert">
      {{ displayProjectsLoadError }}
    </p>

    <p v-if="loading && status === null" class="cloud-panel__loading">
      {{ t('common.loading') }}
    </p>

    <template v-else>
      <!-- Connexion principale (guidé / verrouillé, non connecté) -->
      <section
        v-if="isFinalFace && !status?.enrolled"
        class="cloud-panel__section"
      >
        <h3 class="cloud-panel__section-title">{{ t('cloud.loginTitle') }}</h3>
        <p class="cloud-panel__hint">{{ t('cloud.loginHint') }}</p>
        <button
          type="button"
          class="cloud-panel__save-btn"
          :disabled="loading"
          @click="cloudLoginModalOpen = true"
        >
          {{ t('cloud.loginSubmit') }}
        </button>
        <button
          type="button"
          class="cloud-panel__link-btn"
          @click="showJoinSection = !showJoinSection"
        >
          {{ t('cloud.haveInvitationCode') }}
        </button>
      </section>

      <!-- Invitation org (secondaire) -->
      <section
        v-if="isFinalFace && !status?.enrolled && showJoinSection"
        class="cloud-panel__section cloud-panel__section--secondary"
      >
        <h3 class="cloud-panel__section-title">{{ t('cloud.joinTitle') }}</h3>
        <p class="cloud-panel__hint">{{ t('cloud.joinHint') }}</p>
        <EnrollCloudJoinForm
          v-model:join-token="joinTokenDraft"
          v-model:base-url="baseUrlDraft"
          :show-url-field="showCloudUrlField"
          :disabled="loading"
          :submitting="joining"
          :submit-label="t('cloud.joinSubmit')"
          @submit="onJoin"
        />
      </section>

      <!-- Connecté -->
      <section v-if="status?.enrolled" class="cloud-panel__section">
        <h3 class="cloud-panel__section-title">
          {{ t('cloud.connectedTo', { org: connectedOrgLabel }) }}
        </h3>
        <p class="cloud-panel__sync-meta">
          {{ t('cloud.syncMeta', { count: status?.synced_count ?? 0, lastSync: lastSyncLabel }) }}
        </p>
        <p v-if="deviceInfoLabel" class="cloud-panel__device-meta">
          {{ deviceInfoLabel }}
        </p>
        <p v-if="cloudQuotaLabel" class="cloud-panel__quota-meta">
          {{ cloudQuotaLabel }}
        </p>
        <button
          type="button"
          class="cloud-panel__save-btn"
          :disabled="loading || syncingRegards"
          @click="onSyncRegards"
        >
          {{ syncingRegards ? t('cloud.syncingRegards') : t('cloud.syncRegards') }}
        </button>
        <div class="cloud-panel__action-links">
          <button
            v-if="isFinalFace && !showLocalOptions"
            type="button"
            class="cloud-panel__link-btn"
            @click="showLocalOptions = true"
          >
            {{ t('cloud.localOptions') }}
          </button>
          <button
            type="button"
            class="cloud-panel__link-btn cloud-panel__link-btn--danger"
            :disabled="loading || disconnecting"
            @click="onDisconnect"
          >
            {{ disconnecting ? t('cloud.disconnecting') : t('cloud.disconnect') }}
          </button>
        </div>
      </section>

      <section
        v-if="showLocalOptions && isFinalFace && status?.enrolled"
        class="cloud-panel__section cloud-panel__section--local"
      >
        <h4 class="cloud-panel__subsection-title">{{ t('cloud.mountPathTitle') }}</h4>
        <p class="cloud-panel__hint">{{ t('cloud.mountPathHint') }}</p>
        <form class="cloud-panel__config-form" @submit.prevent="onSaveMountPath">
          <div class="cloud-panel__field">
            <label for="cloud-mount-path-guided">{{ t('cloud.mountPathTitle') }}</label>
            <input
              id="cloud-mount-path-guided"
              v-model="mountPathDraft"
              type="text"
              class="cloud-panel__input"
              :placeholder="t('cloud.mountPathPlaceholder')"
              :disabled="loading || savingConfig"
            />
          </div>
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
        <button
          type="button"
          class="cloud-panel__link-btn"
          @click="showLocalOptions = false"
        >
          {{ t('cloud.hideLocalOptions') }}
        </button>
      </section>

      <ManagedConnectorsSection
        v-if="status?.enrolled"
        :connectors="connectors"
        :loading="connectorsLoading"
        :error="displayConnectorsError"
        :show-ids="isTechnicalFace"
        :show-advanced-tools="isTechnicalFace"
      />

      <!-- Visage technique (admin / avancé) -->
      <section
        v-if="isTechnicalFace"
        class="cloud-panel__section cloud-panel__section--technical"
      >
        <h3 class="cloud-panel__section-title">{{ t('cloud.technicalSettings') }}</h3>

        <h4 class="cloud-panel__subsection-title">{{ t('cloud.enrollTitle') }}</h4>
        <p class="cloud-panel__hint">{{ t('cloud.enrollHint') }}</p>
        <form class="cloud-panel__config-form" @submit.prevent="onSaveEnroll">
          <div class="cloud-panel__field">
            <label for="cloud-base-url">{{ t('cloud.baseUrl') }}</label>
            <input
              id="cloud-base-url"
              v-model="baseUrlDraft"
              type="url"
              class="cloud-panel__input"
              :placeholder="t('cloud.baseUrl')"
              :disabled="loading || savingEnroll"
            />
          </div>
          <div class="cloud-panel__field">
            <label for="cloud-bearer-token">{{ t('cloud.bearerToken') }}</label>
            <input
              id="cloud-bearer-token"
              v-model="bearerTokenDraft"
              type="password"
              class="cloud-panel__input"
              :placeholder="t('cloud.bearerToken')"
              :disabled="loading || savingEnroll"
            />
          </div>
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
          <div class="cloud-panel__field">
            <label for="cloud-mount-path-technical">{{ t('cloud.mountPathTitle') }}</label>
            <input
              id="cloud-mount-path-technical"
              v-model="mountPathDraft"
              type="text"
              class="cloud-panel__input"
              :placeholder="t('cloud.mountPathPlaceholder')"
              :disabled="loading || savingConfig"
            />
          </div>
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
        <dl class="cloud-panel__status cloud-panel__status--compact">
          <div>
            <dt>{{ t('cloud.statusEnrolled') }}</dt>
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
          <div v-if="!status?.enrolled">
            <dt>{{ t('cloud.statusLastSync') }}</dt>
            <dd>{{ lastSyncLabel }}</dd>
          </div>
          <div>
            <dt>{{ t('cloud.statusConfigured') }}</dt>
            <dd>{{ status?.configured ? t('common.yes') : t('common.no') }}</dd>
          </div>
        </dl>
      </section>

      <section
        v-if="status?.enrolled || isTechnicalFace"
        class="cloud-panel__section"
      >
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
          {{ status?.enrolled ? t('cloud.noProjectsEnrolled') : t('cloud.noProjects') }}
        </p>
        <ul v-else class="cloud-panel__projects" role="list">
          <li v-for="project in projects" :key="project.id" class="cloud-panel__project">
            <span class="cloud-panel__project-name">{{ project.name }}</span>
            <div v-if="showProjectCacheActions" class="cloud-panel__project-actions">
              <button
                v-if="showSyncButton"
                type="button"
                class="cloud-panel__sync-btn"
                :disabled="syncing || pulling || !canSync"
                @click="onSync(project.id)"
              >
                {{ syncing ? t('cloud.syncing') : t('cloud.pushLocalCache') }}
              </button>
              <button
                v-if="canPull"
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
    </template>

    <CloudLoginModal
      v-model="cloudLoginModalOpen"
      @enrolled="onCloudLoggedIn"
      @open-invitation="onOpenCloudInvitation"
    />
    <EnrollCloudModal v-model="enrollCloudModalOpen" @enrolled="onCloudLoggedIn" />
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
import ManagedConnectorsSection from '@components/cloud/ManagedConnectorsSection.vue';
import EnrollCloudJoinForm from '@components/cloud/EnrollCloudJoinForm.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';

const { t } = useI18n();
const emit = defineEmits<{
  (e: 'artefactsChanged'): void;
  (e: 'regardsChanged'): void;
}>();
const { settings, settingsLocked } = useAppSettings();
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
  connectors,
  connectorsLoading,
  connectorsError,
  quota,
  quotaLoading,
} = useCloud();

const mountPathDraft = ref('');
const baseUrlDraft = ref('');
const bearerTokenDraft = ref('');
const joinTokenDraft = ref('');
const savingConfig = ref(false);
const savingEnroll = ref(false);
const joining = ref(false);
const disconnecting = ref(false);
const showLocalOptions = ref(false);
const showJoinSection = ref(false);
const cloudLoginModalOpen = ref(false);
const enrollCloudModalOpen = ref(false);
const projects = ref<ProjetProject[]>([]);
const projectsLoadError = ref<string | null>(null);

const uiMode = computed(() => resolveUiMode(settingsLocked.value));
const isTechnicalFace = computed(() => uiMode.value === 'agent');
const isFinalFace = computed(() => !isTechnicalFace.value);
const showProjectCacheActions = computed(
  () => isTechnicalFace.value || showLocalOptions.value,
);
const showSyncButton = computed(
  () => showProjectCacheActions.value && !status.value?.enrolled,
);

const presetCloudUrl = computed(() => settings.value.cloudEndpoint?.trim() ?? '');
const showCloudUrlField = computed(
  () => !status.value?.base_url && !presetCloudUrl.value,
);

const connectedOrgLabel = computed(
  () => status.value?.org_label ?? status.value?.org_id ?? t('cloud.unknownOrg'),
);

const deviceInfoLabel = computed(() => {
  const id = status.value?.device_id?.trim();
  if (!id || !status.value?.enrolled) return '';
  return t('cloud.deviceInfo', { id });
});

function onOpenCloudInvitation(): void {
  cloudLoginModalOpen.value = false;
  showJoinSection.value = true;
  enrollCloudModalOpen.value = true;
}

async function onCloudLoggedIn(): Promise<void> {
  showJoinSection.value = false;
  joinTokenDraft.value = '';
  await refreshStatus();
  await refreshProjects();
}

const cloudQuotaLabel = computed(() => {
  if (!status.value?.enrolled) return '';
  if (quotaLoading.value) return t('cloud.quotaLoading');
  if (!quota.value) return '';
  if (!quota.value.enabled) return t('cloud.quotaDisabled');
  if (quota.value.tokensLimit == null && quota.value.requestsLimit == null) {
    return t('cloud.quotaUnlimited', {
      tokens: quota.value.tokensUsed.toLocaleString(),
      requests: quota.value.requestsCount.toLocaleString(),
    });
  }
  return t('cloud.quotaSummary', {
    tokens: quota.value.remainingTokens?.toLocaleString() ?? '0',
    requests: quota.value.remainingRequests?.toLocaleString() ?? '0',
  });
});

const canSync = computed(() => Boolean(status.value?.configured || status.value?.enrolled));
const canPull = computed(() => Boolean(status.value?.enrolled));

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

function mapConnectorError(raw: string): string | null {
  const trimmed = raw.trim();
  if (trimmed === 'invalid_user_jwt' || trimmed === 'invalid_device_token') {
    return t('cloud.connectors.authFailed');
  }
  if (trimmed.startsWith('connectors_unavailable:')) return t('cloud.connectors.loadFailed');
  return null;
}

function humanizeError(raw: string | null, fallbackKey: string): string | null {
  if (!raw) return null;
  if (fallbackKey === 'cloud.connectors.loadFailed') {
    const mapped = mapConnectorError(raw);
    if (mapped) return mapped;
  }
  if (isTechnicalError(raw)) return t(fallbackKey);
  return raw;
}

const displayLoadError = computed(() => humanizeError(loadError.value, 'cloud.loadFailed'));
const displayProjectsLoadError = computed(() =>
  humanizeError(projectsLoadError.value, 'cloud.projectsLoadFailed'),
);
const displayConnectorsError = computed(() => {
  const raw = connectorsError.value;
  if (!raw) return null;
  const trimmed = raw.trim();
  if (trimmed === 'invalid_user_jwt' || trimmed === 'invalid_device_token') {
    return t('cloud.connectors.authFailed');
  }
  if (
    trimmed.includes('code d\'invitation')
    || trimmed.toLowerCase().includes('invitation code')
  ) {
    return trimmed;
  }
  return humanizeError(raw, 'cloud.connectors.loadFailed');
});

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
      showLocalOptions.value = false;
      await refreshProjects();
      Notify.create({
        message: t('cloud.joinSuccess'),
        color: 'positive',
        timeout: 2000,
      });
      if (connectorsError.value) {
        Notify.create({
          message: displayConnectorsError.value ?? t('cloud.connectors.loadFailed'),
          color: 'warning',
          timeout: 4000,
        });
      }
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
      showLocalOptions.value = false;
      await refreshProjects();
      Notify.create({
        message: t('cloud.enrolled'),
        color: 'positive',
        timeout: 2000,
      });
      if (connectorsError.value) {
        Notify.create({
          message: displayConnectorsError.value ?? t('cloud.connectors.requireDevice'),
          color: 'warning',
          timeout: 4000,
        });
      }
    } else {
      notifyError(loadError.value, 'cloud.enrollFailed');
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
      showLocalOptions.value = false;
      joinTokenDraft.value = '';
      bearerTokenDraft.value = '';
      await refreshProjects();
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

watch(
  () => isProjetPluginActive.value,
  () => {
    void refreshProjects();
  },
);

watch(
  () => status.value?.enrolled === true,
  (enrolled) => {
    if (!enrolled) {
      showLocalOptions.value = false;
    }
  },
);

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
  gap: var(--wp-space-3);
  padding: var(--wp-space-3);
  min-height: 0;
  overflow-y: auto;
}

.cloud-panel__empty,
.cloud-panel__loading {
  padding: var(--wp-space-6) var(--wp-space-2);
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__section {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) 0;
  border-top: 1px solid var(--wp-border);

  &:first-of-type {
    border-top: none;
    padding-top: 0;
  }
}

.cloud-panel__section--technical,
.cloud-panel__section--local {
  border-top: 1px dashed var(--wp-border);
}

.cloud-panel__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
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

.cloud-panel__sync-meta {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.cloud-panel__device-meta {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.cloud-panel__quota-meta {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.cloud-panel__action-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--wp-space-3);
}

.cloud-panel__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  flex: 1 1 180px;

  label {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-muted);
    font-weight: 500;
  }
}

.cloud-panel__config-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
}

.cloud-panel__input {
  flex: 1 1 180px;
  min-height: 34px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__pick-btn,
.cloud-panel__save-btn,
.cloud-panel__refresh-btn,
.cloud-panel__sync-btn,
.cloud-panel__pull-btn {
  min-height: 34px;
  padding: var(--wp-space-2) var(--wp-space-3);
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

.cloud-panel__link-btn {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
  text-decoration: underline;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.cloud-panel__link-btn--danger {
  color: var(--wp-danger);
}

.cloud-panel__status {
  margin: 0;
  display: grid;
  gap: var(--wp-space-2);
  font-size: var(--wp-fs-xs);

  dt {
    color: var(--wp-text-faint);
  }

  dd {
    margin: 0;
    color: var(--wp-text);
  }
}

.cloud-panel__status--compact {
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
}

.cloud-panel__projects {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.cloud-panel__project {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) 0;
  border-bottom: 1px solid var(--wp-border);

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  &:first-child {
    padding-top: 0;
  }
}

.cloud-panel__project-name {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.cloud-panel__project-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
}
</style>
