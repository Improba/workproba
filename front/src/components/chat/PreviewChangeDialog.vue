<template>
  <q-dialog :model-value="open" @update:model-value="onOpenChange">
    <div class="preview-change-dialog" role="dialog" :aria-label="t('chat.previewChange.title')">
      <header class="preview-change-dialog__head">
        <h2 class="preview-change-dialog__title">{{ t('chat.previewChange.title') }}</h2>
        <button
          type="button"
          class="preview-change-dialog__close"
          :aria-label="t('common.close')"
          @click="close"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p v-if="filePath" class="preview-change-dialog__file">{{ fileName }}</p>

      <div v-if="loading" class="preview-change-dialog__state">
        {{ t('common.loading') }}
      </div>

      <div v-else-if="loadError" class="preview-change-dialog__state preview-change-dialog__state--error">
        <p>{{ t('chat.previewChange.loadFailed') }}</p>
        <button type="button" class="preview-change-dialog__retry" @click="load">
          {{ t('common.retry') }}
        </button>
      </div>

      <div v-else-if="result?.is_binary" class="preview-change-dialog__state">
        {{ result.message?.trim() || t('chat.previewChange.binaireNonSupporte') }}
      </div>

      <template v-else-if="result">
        <p v-if="result.is_new" class="preview-change-dialog__badge">
          {{ t('chat.previewChange.nouveauFichier') }}
        </p>
        <div
          v-if="sanitizedDiff"
          class="preview-change-dialog__diff"
          v-html="sanitizedDiff"
        />
        <p v-else class="preview-change-dialog__state">
          {{ t('chat.previewChange.emptyDiff') }}
        </p>
      </template>

      <footer class="preview-change-dialog__foot">
        <button type="button" class="preview-change-dialog__btn preview-change-dialog__btn--ghost" @click="close">
          {{ t('chat.previewChange.annuler') }}
        </button>
        <button
          type="button"
          class="preview-change-dialog__btn"
          :disabled="loading || !!loadError"
          @click="confirm"
        >
          {{ t('chat.previewChange.confirmer') }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import DOMPurify from 'dompurify';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { fetchPreviewChange, type PreviewChangeResult } from '@services/aiSidecar';

const props = defineProps<{
  open: boolean;
  workspaceDataDir?: string | null;
  projectPath?: string | null;
  filePath: string;
  proposedContent?: string;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
}>();

const emit = defineEmits<{
  'update:open': [value: boolean];
  confirm: [];
}>();

const { t } = useI18n();

const loading = ref(false);
const loadError = ref(false);
const result = ref<PreviewChangeResult | null>(null);

const fileName = computed(() => {
  const parts = props.filePath.split(/[/\\]/);
  return parts[parts.length - 1] || props.filePath;
});

const sanitizedDiff = computed(() => {
  const html = result.value?.diff_html?.trim();
  if (!html) return '';
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
});

function close(): void {
  emit('update:open', false);
}

function onOpenChange(value: boolean): void {
  emit('update:open', value);
}

function confirm(): void {
  emit('confirm');
  close();
}

async function load(): Promise<void> {
  if (!props.workspaceDataDir || !props.projectPath || !props.filePath) {
    loadError.value = true;
    return;
  }
  loading.value = true;
  loadError.value = false;
  result.value = null;
  try {
    const data = await fetchPreviewChange({
      workspaceDataDir: props.workspaceDataDir,
      projectPath: props.projectPath,
      filePath: props.filePath,
      proposedContent: props.proposedContent ?? '',
      toolName: props.toolName,
      toolArgs: props.toolArgs,
    });
    if (!data) {
      loadError.value = true;
      return;
    }
    result.value = data;
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

watch(
  () =>
    [
      props.open,
      props.filePath,
      props.proposedContent,
      props.toolName,
      props.toolArgs,
      props.workspaceDataDir,
      props.projectPath,
    ] as const,
  ([isOpen]) => {
    if (isOpen) void load();
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.preview-change-dialog {
  width: min(42rem, 92vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  padding: 1rem 1.1rem;
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
}

.preview-change-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.preview-change-dialog__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.preview-change-dialog__close {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.25rem;
}

.preview-change-dialog__file {
  margin: 0 0 0.75rem;
  font-size: var(--wp-fs-sm);
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  color: var(--wp-text-muted);
}

.preview-change-dialog__badge {
  margin: 0 0 0.5rem;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-accent-strong);
}

.preview-change-dialog__state {
  padding: 1rem 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-align: center;

  &--error {
    color: var(--wp-danger);
  }
}

.preview-change-dialog__retry {
  margin-top: 0.5rem;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  cursor: pointer;
}

.preview-change-dialog__diff {
  flex: 1;
  min-height: 0;
  max-height: 50vh;
  overflow: auto;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);

  :deep(.wp-diff-add) {
    background: color-mix(in srgb, var(--wp-success) 18%, transparent);
    color: var(--wp-text);
  }

  :deep(.wp-diff-del) {
    background: color-mix(in srgb, var(--wp-danger) 15%, transparent);
    color: var(--wp-text-muted);
    text-decoration: line-through;
  }

  :deep(.wp-diff-common) {
    color: var(--wp-text-muted);
  }
}

.preview-change-dialog__foot {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.85rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--wp-border);
}

.preview-change-dialog__btn {
  padding: 0.5rem 0.9rem;
  border-radius: var(--wp-r-md);
  border: 1px solid var(--wp-accent);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-weight: 600;
  cursor: pointer;

  &--ghost {
    border-color: var(--wp-border-strong);
    background: var(--wp-surface);
    color: var(--wp-text);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
