<template>
  <q-dialog :model-value="modelValue" @update:model-value="onDialogUpdate">
    <div
      v-if="workspace"
      :key="workspace.id"
      class="wp-space-settings-dialog"
    >
      <header class="wp-space-settings-dialog__head">
        <span class="wp-space-settings-dialog__title">{{ t('shell.spaceSettingsTitle') }}</span>
        <button
          type="button"
          class="wp-space-settings-dialog__close"
          :aria-label="t('common.close')"
          @click="close"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p class="wp-space-settings-dialog__hint">
        {{ t('shell.spacePathHint', { path: workspace.folderPath }) }}
      </p>

      <div class="wp-space-settings-dialog__field">
        <label for="wp-space-settings-title">{{ t('shell.renameSpaceTitle') }}</label>
        <input
          id="wp-space-settings-title"
          v-model="titleDraft"
          type="text"
          :placeholder="t('shell.renameSpacePlaceholder')"
          @keydown.enter.prevent="onSave"
        />
      </div>

      <SpaceCapabilitiesPanel
        :key="workspace.id"
        :workspace-data-dir="workspace.dataDir"
        embedded
        @open-setup="onOpenSetup"
      />

      <footer class="wp-space-settings-dialog__foot">
        <button type="button" class="wp-space-settings-dialog__btn" @click="close">
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="wp-space-settings-dialog__btn wp-space-settings-dialog__btn--primary"
          :disabled="!titleDraft.trim() || saving"
          @click="onSave"
        >
          {{ t('common.save') }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import SpaceCapabilitiesPanel from '@components/capabilities/SpaceCapabilitiesPanel.vue';
import { useSpace } from '@composables/useSpace';
import { useShellSurfaces } from '@composables/useShellSurfaces';
import type { WorkspaceInfo } from '@composables/useDesktop.types';
import type { SpaceCapabilityItem } from '@services/aiSidecar';

const props = defineProps<{
  modelValue: boolean;
  workspace: WorkspaceInfo | null;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'saved', workspace: WorkspaceInfo): void;
}>();

const { t } = useI18n();
const { renameSpace } = useSpace();
const { openCapabilities } = useShellSurfaces();

const titleDraft = ref('');
const saving = ref(false);

function basename(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

watch(
  () => [props.modelValue, props.workspace] as const,
  ([open, workspace]) => {
    if (!open || !workspace) return;
    titleDraft.value = workspace.title || basename(workspace.folderPath);
  },
);

function onDialogUpdate(value: boolean): void {
  emit('update:modelValue', value);
}

function close(): void {
  emit('update:modelValue', false);
}

async function onOpenSetup(_item: SpaceCapabilityItem): Promise<void> {
  close();
  await nextTick();
  openCapabilities('workproba_cloud');
}

async function onSave(): Promise<void> {
  const workspace = props.workspace;
  const title = titleDraft.value.trim();
  if (!workspace || !title) return;

  saving.value = true;
  try {
    const updated = await renameSpace(workspace.id, title);
    emit('saved', updated);
    close();
    Notify.create({ message: t('shell.renameSpaceSaved'), color: 'dark', timeout: 1500 });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('shell.renameSpaceFailed'),
      classes: 'bg-danger text-white',
    });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.wp-space-settings-dialog {
  width: min(34rem, 92vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  padding: var(--wp-space-4);
  overflow: hidden;
}

.wp-space-settings-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wp-space-settings-dialog__title {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-base);
  color: var(--wp-text);
}

.wp-space-settings-dialog__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-space-settings-dialog__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  word-break: break-all;
}

.wp-space-settings-dialog__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);

  label {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  input {
    padding: var(--wp-space-2) var(--wp-space-3);
    border: 1px solid var(--wp-border);
    border-radius: var(--wp-r-sm);
    background: var(--wp-surface-2);
    font-size: var(--wp-fs-sm);
    color: var(--wp-text);
    font-family: var(--wp-font-ui);

    &:focus {
      outline: none;
      border-color: var(--wp-accent);
    }
  }
}

.wp-space-settings-dialog :deep(.wp-space-caps--embedded) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.wp-space-settings-dialog__foot {
  flex: none;
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.wp-space-settings-dialog__btn {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);

  &:hover {
    background: var(--wp-surface-2);
  }

  &--primary {
    background: var(--wp-accent);
    color: var(--wp-canard);
    border-color: var(--wp-accent);

    &:hover {
      background: var(--wp-accent-strong);
    }
  }
}
</style>
