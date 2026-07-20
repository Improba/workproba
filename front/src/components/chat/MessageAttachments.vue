<template>
  <div v-if="attachments.length" class="msg-attachments">
    <div
      v-for="att in attachments"
      :key="att.id"
      class="msg-attachments__item"
    >
      <span class="msg-attachments__chip" :title="att.fileName">
        <span class="msg-attachments__icon">
          <Lucide :name="iconFor(att)" size="14" color="wp-text-muted" />
        </span>
        <span class="msg-attachments__label">{{ att.fileName }}</span>
      </span>
      <span
        v-if="statusFor(att)"
        class="msg-attachments__badge"
        :class="`msg-attachments__badge--${badgeVariant(statusFor(att)!.status_key)}`"
      >
        {{ statusFor(att)!.label_locale }}
      </span>
      <button
        v-if="showActivateButton(att)"
        type="button"
        class="msg-attachments__activate"
        @click="onActivateReading(att)"
      >
        {{ t('chat.attachment.activateReading') }}
      </button>
      <button
        v-if="showRereadButton(att)"
        type="button"
        class="msg-attachments__reread"
        :disabled="rereadingId === att.id"
        @click="onRereadWithCurrent(att)"
      >
        {{ t('chat.attachment.rereadWithCurrent') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useLlmSessionContext } from '@composables/useLlmSessionContext';
import { useSpace } from '@composables/useSpace';
import {
  applyAttachmentStatusEvent,
  type AttachmentStatusEntry,
} from '@composables/useChatStream';
import type { ChatAttachmentKind, ChatAttachmentSnapshot } from '#types';
import type { ProviderSet } from '@composables/useDesktop.types';
import {
  chatAttachmentRelativePath,
  reprocessAttachment,
} from '@services/aiSidecar';
import {
  chatErrorMessageForReadiness,
  ensureProviderSetChatReady,
} from '@utils/providerSetNotify';
import { ProviderSetNotReadyError } from '@utils/providerSetErrors';
import {
  getSetActivationReadiness,
  pickActivatableReadingSet,
  setCanReadAttachmentKind,
  usesDeviceBearerAuth,
} from '@utils/providerSetValidation';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useCloud } from '@composables/useCloud';

const props = defineProps<{
  attachments: ChatAttachmentSnapshot[];
  attachmentStatuses?: Record<string, AttachmentStatusEntry>;
  settingsLocked?: boolean;
}>();

const { t, locale } = useI18n();
const route = useRoute();
const { activePath, activeDataDir } = useSpace();
const { sets, effectiveActiveSet, setActiveSet } = useAppSettings();
const { buildContextProviderSet } = useLlmSessionContext();
const { getPluginDataDir } = usePlugins();
const { providerReadiness, init: initCloud } = useCloud();

const statuses = computed(() => props.attachmentStatuses ?? {});
const rereadingId = ref<string | null>(null);
const sessionId = computed(() => String(route.params.id ?? ''));

function iconFor(att: ChatAttachmentSnapshot): string {
  if (att.kind === 'image') return 'image';
  const ext = att.fileName.split('.').pop()?.toLowerCase();
  if (ext === 'pdf' || ext === 'docx' || ext === 'doc') return 'file-text';
  if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') return 'table';
  if (ext === 'pptx') return 'presentation';
  return 'file';
}

function statusFor(att: ChatAttachmentSnapshot): AttachmentStatusEntry | null {
  return statuses.value[att.id] ?? null;
}

function badgeVariant(statusKey: string): 'success' | 'warning' {
  return isUnavailableStatus(statusKey) ? 'warning' : 'success';
}

function isUnavailableStatus(statusKey: string): boolean {
  return statusKey === 'unavailable' || statusKey.endsWith('.unavailable');
}

function showActivateButton(att: ChatAttachmentSnapshot): boolean {
  if (props.settingsLocked) return false;
  const status = statusFor(att);
  if (!status || !isUnavailableStatus(status.status_key)) return false;
  const current = effectiveActiveSet.value;
  if (current && setCanReadAttachments(current, att.kind)) return false;
  return true;
}

function showRereadButton(att: ChatAttachmentSnapshot): boolean {
  const status = statusFor(att);
  if (!status || !isUnavailableStatus(status.status_key)) return false;
  const current = effectiveActiveSet.value;
  if (!current || !setCanReadAttachments(current, att.kind)) return false;
  return true;
}

function setCanReadAttachments(set: ProviderSet, kind: ChatAttachmentKind): boolean {
  return setCanReadAttachmentKind(set, kind);
}

function readinessMessageForReadingActivation(
  kind: ChatAttachmentKind,
): string | null {
  const ctx = { cloud: providerReadiness.value };
  const readingCapable = sets.value.filter((set) => setCanReadAttachments(set, kind));
  if (!readingCapable.length) return null;

  const cloudCandidate = readingCapable.find((set) => usesDeviceBearerAuth(set));
  if (cloudCandidate) {
    const cloudCheck = getSetActivationReadiness(cloudCandidate, ctx);
    if (!cloudCheck.ok) {
      return chatErrorMessageForReadiness(cloudCheck.reason);
    }
  }

  for (const set of readingCapable) {
    const check = getSetActivationReadiness(set, ctx);
    if (!check.ok) {
      return chatErrorMessageForReadiness(check.reason);
    }
  }
  return null;
}

async function onActivateReading(att: ChatAttachmentSnapshot): Promise<void> {
  if (!providerReadiness.value) {
    await initCloud();
  }
  const ctx = { cloud: providerReadiness.value };
  const target = pickActivatableReadingSet(sets.value, att.kind, ctx);
  if (!target) {
    const message =
      readinessMessageForReadingActivation(att.kind) ?? t('common.switchFailed');
    Notify.create({
      message,
      color: 'warning',
      timeout: 6000,
    });
    return;
  }
  if (target.id === effectiveActiveSet.value?.id) return;
  try {
    await setActiveSet(target.id, ctx);
  } catch (err) {
    const message =
      err instanceof ProviderSetNotReadyError
        ? err.message
        : t('common.switchFailed');
    Notify.create({
      message,
      color: 'negative',
      timeout: 6000,
    });
  }
}

async function onRereadWithCurrent(att: ChatAttachmentSnapshot): Promise<void> {
  const projectPath = activePath.value;
  const workspaceDataDir = activeDataDir.value;
  if (!projectPath || !workspaceDataDir) {
    Notify.create({
      message: t('errors.noSpaceOpen'),
      color: 'warning',
      timeout: 4000,
    });
    return;
  }

  const providerSet = buildContextProviderSet();
  if (!providerSet || !setCanReadAttachments(providerSet, att.kind)) return;
  if (usesDeviceBearerAuth(providerSet) && !providerReadiness.value) {
    await initCloud();
  }
  const cloudCtx = usesDeviceBearerAuth(providerSet)
    ? providerReadiness.value
    : null;
  if (!ensureProviderSetChatReady(providerSet, cloudCtx)) return;

  rereadingId.value = att.id;
  try {
    const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    const result = await reprocessAttachment({
      workspaceDataDir,
      projectPath,
      attachmentId: att.id,
      filePath: chatAttachmentRelativePath(sessionId.value, att.id, att.fileName),
      mimeType: att.mimeType,
      providerSet,
      locale: locale.value,
      cloudPluginDataDir,
    });
    if (props.attachmentStatuses) {
      applyAttachmentStatusEvent(props.attachmentStatuses, {
        attachment_id: att.id,
        status_key: result.status_key,
        label_locale: result.label_locale,
      });
    }
  } catch {
    Notify.create({
      message: t('common.switchFailed'),
      color: 'negative',
      timeout: 4000,
    });
  } finally {
    rereadingId.value = null;
  }
}
</script>

<style scoped lang="scss">
.msg-attachments {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.2rem;
}

.msg-attachments__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.msg-attachments__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 100%;
}

.msg-attachments__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  flex: 0 0 auto;
}

.msg-attachments__label {
  font-size: 0.75rem;
  color: var(--wp-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.msg-attachments__badge {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.45rem;
  border-radius: var(--wp-r-pill);
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1.3;
}

.msg-attachments__badge--success {
  color: var(--wp-success);
  background: color-mix(in srgb, var(--wp-success) 14%, transparent);
}

.msg-attachments__badge--warning {
  color: var(--wp-text-muted);
  background: var(--wp-surface-3);
}

.msg-attachments__activate {
  padding: 0.1rem 0.45rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-accent);
  font-size: 0.68rem;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
  }
}

.msg-attachments__reread {
  padding: 0.1rem 0.45rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text);
  font-size: 0.68rem;
  font-weight: 600;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-3);
    border-color: var(--wp-accent);
  }

  &:disabled {
    opacity: 0.6;
    cursor: wait;
  }
}
</style>
