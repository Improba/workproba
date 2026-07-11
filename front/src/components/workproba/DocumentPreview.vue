<template>
  <div class="doc-preview">
    <div v-if="!relativePath" class="doc-preview__empty">
      <Lucide name="file-search" size="26" color="text-faint" />
      <p>{{ t('shell.previewEmpty') }}</p>
    </div>

    <div v-else-if="loading" class="doc-preview__empty">
      <span class="doc-preview__spinner" aria-hidden="true" />
      <p>{{ t('shell.previewLoading') }}</p>
    </div>

    <div v-else-if="error" class="doc-preview__empty doc-preview__empty--error">
      <Lucide name="alert-triangle" size="22" color="danger" />
      <p>{{ error }}</p>
      <button type="button" class="doc-preview__retry" @click="reload">
        {{ t('common.retry') }}
      </button>
    </div>

    <template v-else-if="preview">
      <header class="doc-preview__header">
        <h2 class="doc-preview__title">{{ preview.title }}</h2>
        <div class="doc-preview__actions">
          <button
            v-if="showPublish && relativePath"
            type="button"
            class="doc-preview__publish"
            @click="emit('publish', relativePath)"
          >
            <Lucide name="upload" size="15" color="text" />
            <span>{{ t('plugin.workproba.projet.publishAction') }}</span>
          </button>
          <button
            type="button"
            class="doc-preview__open-os"
            @click="openInOs"
          >
            <Lucide name="external-link" size="15" color="text" />
            <span>{{ t('chat.attachment.openInOs') }}</span>
          </button>
        </div>
      </header>

      <div v-if="preview.type === 'unsupported'" class="doc-preview__unsupported">
        <Lucide name="file-x" size="24" color="text-faint" />
        <p>{{ t('shell.previewUnsupported') }}</p>
      </div>

      <div
        v-else-if="preview.type === 'image' && imageSrc"
        class="doc-preview__image-wrap"
      >
        <img
          :src="imageSrc"
          :alt="preview.title"
          class="doc-preview__image"
          @error="onImageError"
        />
      </div>

      <div
        v-else-if="preview.type === 'image' && !imageSrc"
        class="doc-preview__unsupported"
      >
        <Lucide name="image" size="24" color="text-faint" />
        <p>{{ t('shell.previewUnsupported') }}</p>
      </div>

      <div
        v-else-if="sanitizedHtml"
        class="doc-preview__html"
        v-html="sanitizedHtml"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import DOMPurify from 'dompurify';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { isDesktopApp, openLocalFile } from '@composables/useDesktop';
import {
  fetchDocumentPreview,
  isSafeRelativePath,
  type DocumentPreviewResult,
} from '@services/aiSidecar';

const props = defineProps<{
  relativePath: string | null;
  projectPath: string | null;
  workspaceDataDir?: string | null;
  showPublish?: boolean;
}>();

const emit = defineEmits<{
  (e: 'publish', relativePath: string): void;
}>();

const { t } = useI18n();

const loading = ref(false);
const error = ref<string | null>(null);
const preview = ref<DocumentPreviewResult | null>(null);
const imageSrc = ref<string | null>(null);

const sanitizedHtml = computed(() => {
  const html = preview.value?.html?.trim();
  if (!html) return '';
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
});

async function resolveImageSrc(relativePath: string): Promise<string | null> {
  if (!props.projectPath || !isDesktopApp()) return null;
  const root = props.projectPath.replace(/\\/g, '/').replace(/\/$/, '');
  const fullPath = `${root}/${relativePath.replace(/\\/g, '/')}`;
  try {
    const { convertFileSrc } = await import('@tauri-apps/api/core');
    return convertFileSrc(fullPath);
  } catch {
    return null;
  }
}

async function loadPreview(): Promise<void> {
  const path = props.relativePath;
  if (!path || !props.projectPath || !isSafeRelativePath(path)) {
    preview.value = null;
    imageSrc.value = null;
    error.value = null;
    loading.value = false;
    return;
  }

  loading.value = true;
  error.value = null;
  preview.value = null;
  imageSrc.value = null;

  try {
    const result = await fetchDocumentPreview({
      relativePath: path,
      projectPath: props.projectPath,
      workspaceDataDir: props.workspaceDataDir,
    });
    preview.value = result;
    if (result.type === 'image') {
      imageSrc.value = await resolveImageSrc(path);
    }
  } catch (err) {
    error.value =
      err instanceof Error ? err.message : t('shell.previewUnsupported');
  } finally {
    loading.value = false;
  }
}

function reload(): void {
  void loadPreview();
}

function onImageError(): void {
  imageSrc.value = null;
}

async function openInOs(): Promise<void> {
  if (!props.relativePath || !props.projectPath) return;
  await openLocalFile(props.relativePath, props.projectPath);
}

watch(
  () => [props.relativePath, props.projectPath, props.workspaceDataDir] as const,
  () => {
    void loadPreview();
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.doc-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.doc-preview__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-6);
  text-align: center;
  color: var(--wp-text-faint);

  p {
    margin: 0;
    font-size: var(--wp-fs-sm);
    line-height: var(--wp-lh-normal);
  }
}

.doc-preview__empty--error {
  color: var(--wp-danger);
}

.doc-preview__spinner {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: var(--wp-r-pill);
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: doc-preview-spin 0.7s linear infinite;
}

.doc-preview__retry {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
}

.doc-preview__header {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--wp-space-3);
  padding: var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
}

.doc-preview__title {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: var(--wp-lh-tight);
  color: var(--wp-text);
  word-break: break-word;
}

.doc-preview__actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
}

.doc-preview__publish,
.doc-preview__open-os {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:hover {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
  }
}

.doc-preview__unsupported {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-6);
  text-align: center;
  color: var(--wp-text-faint);

  p {
    margin: 0;
    font-size: var(--wp-fs-sm);
  }
}

.doc-preview__image-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--wp-space-3);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.doc-preview__image {
  max-width: 100%;
  height: auto;
  border-radius: var(--wp-r-sm);
  border: 1px solid var(--wp-border);
}

.doc-preview__html {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--wp-space-4);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text);

  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 0 0 var(--wp-space-2);
    font-weight: 600;
  }

  :deep(p) {
    margin: 0 0 var(--wp-space-2);
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: var(--wp-space-3);
    font-size: var(--wp-fs-xs);
  }

  :deep(th),
  :deep(td) {
    border: 1px solid var(--wp-border);
    padding: var(--wp-space-1) var(--wp-space-2);
    text-align: left;
  }

  :deep(pre) {
    margin: 0;
    padding: var(--wp-space-3);
    border-radius: var(--wp-r-sm);
    background: var(--wp-surface-2);
    font-family: var(--wp-font-mono, ui-monospace, monospace);
    font-size: var(--wp-fs-xs);
    white-space: pre-wrap;
    word-break: break-word;
  }
}

@keyframes doc-preview-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
