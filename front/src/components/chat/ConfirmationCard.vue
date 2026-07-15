<template>
  <div
    class="confirmation-card"
    :class="{ 'confirmation-card--attached': attached }"
    data-testid="confirmation-card"
    role="region"
    :aria-label="t('chat.confirmationRegion')"
  >
    <header class="confirmation-card__header">
      <Lucide name="shield-check" size="16" color="accent" />
      <h3 class="confirmation-card__title">{{ t('chat.confirmationRegion') }}</h3>
    </header>

    <template v-if="hasEffectHeadline">
      <p v-if="headlineParts" class="confirmation-card__headline">
        <span class="confirmation-card__headline-lead">{{ headlineParts.lead }}</span><strong
          v-if="headlineParts.target"
          class="confirmation-card__headline-target"
        >{{ headlineParts.target }}</strong>
      </p>
      <ul
        v-if="confirmation.protectionLabels?.length"
        class="confirmation-card__protections"
        data-testid="confirmation-protections"
      >
        <li
          v-for="(label, index) in confirmation.protectionLabels"
          :key="`${index}-${label}`"
          class="confirmation-card__protection"
        >
          <Lucide name="check-circle-2" size="xs" color="wp-accent-strong" />
          <span>{{ label }}</span>
        </li>
      </ul>
    </template>
    <template v-else>
      <p
        v-if="customSummaryHtml"
        class="confirmation-card__summary"
        v-html="customSummaryHtml"
      />
      <i18n-t
        v-else
        keypath="chat.confirmationSummary"
        tag="p"
        class="confirmation-card__summary"
      >
        <template #verb>
          <strong>{{ confirmationVerb }}</strong>
        </template>
        <template #file>
          <strong class="confirmation-card__file">{{ confirmationFile }}</strong>
        </template>
      </i18n-t>
    </template>

    <div class="confirmation-card__actions">
      <button
        v-if="canPreview"
        type="button"
        class="confirmation-card__btn confirmation-card__btn--preview"
        :disabled="busy"
        @click="previewOpen = true"
      >
        {{ t('chat.previewChange.voirChangements') }}
      </button>
      <button
        type="button"
        class="confirmation-card__btn confirmation-card__btn--deny"
        :disabled="busy"
        :aria-label="t('chat.confirmationRefuse')"
        @click="emit('cancel')"
      >
        {{ busy ? t('common.inProgress') : t('chat.confirmationDeny') }}
      </button>
      <button
        type="button"
        class="confirmation-card__btn confirmation-card__btn--approve"
        :disabled="busy"
        :aria-label="t('chat.confirmationApprove')"
        @click="emit('approve')"
      >
        {{ busy ? t('common.inProgress') : t('chat.confirmationApproveShort') }}
      </button>
    </div>

    <PreviewChangeDialog
      v-if="canPreview"
      v-model:open="previewOpen"
      :workspace-data-dir="workspaceDataDir"
      :project-path="projectPath"
      :file-path="confirmation.proposedPath"
      :proposed-content="proposedContent"
      :tool-name="confirmation.toolName"
      :tool-args="toolArgs"
      @confirm="emit('approve')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ChatConfirmation } from '#types';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PreviewChangeDialog from '@components/chat/PreviewChangeDialog.vue';
import { canPreviewFileWrite, extractProposedContent } from '@utils/fileWriteTools';

const props = defineProps<{
  confirmation: ChatConfirmation;
  busy?: boolean;
  workspaceDataDir?: string | null;
  projectPath?: string | null;
  toolArgs?: Record<string, unknown>;
  /** Rattachée visuellement au ToolCallCard au-dessus (empilement unique). */
  attached?: boolean;
}>();

const { t } = useI18n();

const emit = defineEmits<{
  approve: [];
  cancel: [];
}>();

const previewOpen = ref(false);

const proposedContent = computed(() => extractProposedContent(props.toolArgs) ?? '');

const canPreview = computed(
  () =>
    Boolean(props.workspaceDataDir) &&
    Boolean(props.projectPath) &&
    Boolean(props.confirmation.proposedPath) &&
    canPreviewFileWrite(props.confirmation.toolName, props.toolArgs),
);

const hasEffectHeadline = computed(() =>
  Boolean(props.confirmation.headline?.trim()),
);

const headlineParts = computed(() => {
  const text = props.confirmation.headline?.trim();
  if (!text) return null;
  const colonIndex = text.indexOf(':');
  if (colonIndex === -1) {
    return { lead: text, target: '' };
  }
  const target = text.slice(colonIndex + 1).trim();
  const lead = target
    ? `${text.slice(0, colonIndex + 1).trim()} `
    : text.slice(0, colonIndex + 1).trim();
  return { lead, target };
});

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fileLabel(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

const confirmationVerb = computed(() =>
  props.confirmation.action === 'modify'
    ? t('chat.confirmationModify')
    : t('chat.confirmationCreate'),
);

const confirmationFile = computed(() => fileLabel(props.confirmation.proposedPath));

const customSummaryHtml = computed(() => {
  const summary = props.confirmation.humanSummary?.trim();
  if (!summary) {
    return null;
  }

  const name = fileLabel(props.confirmation.proposedPath);
  if (name && summary.includes(name)) {
    const escaped = escapeHtml(summary);
    const escapedName = escapeHtml(name);
    return escaped.replace(
      escapedName,
      `<strong class="confirmation-card__file">${escapedName}</strong>`,
    );
  }
  return escapeHtml(summary);
});
</script>

<style scoped lang="scss">
.confirmation-card {
  width: 100%;
  margin: var(--wp-space-2) 0 0;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
  box-shadow: var(--wp-shadow-1);
}

.confirmation-card__header {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: 0.65rem;
}

.confirmation-card__title {
  margin: 0;
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.confirmation-card__headline {
  margin: 0 0 0.75rem;
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
}

.confirmation-card__headline-lead {
  font-weight: 500;
}

.confirmation-card__headline-target {
  display: inline;
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  font-weight: 700;
  color: var(--wp-text);
}

.confirmation-card__summary {
  margin: 0 0 0.75rem;
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);

  :deep(strong) {
    font-weight: 700;
    color: var(--wp-text);
  }

  :deep(.confirmation-card__file) {
    font-family: var(--wp-font-mono, ui-monospace, monospace);
    font-weight: 600;
  }
}

.confirmation-card__protections {
  margin: 0 0 0.75rem;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: var(--wp-fs-sm, 0.875rem);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted, var(--wp-text));
}

.confirmation-card__protection {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
}

.confirmation-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.confirmation-card__btn {
  flex: 1 1 8rem;
  min-height: 2.5rem;
  padding: 0.55rem 1rem;
  border-radius: var(--wp-r-md);
  font-size: var(--wp-fs-base);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    opacity var(--wp-dur) var(--wp-ease);

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }
}

.confirmation-card__btn--preview {
  flex: 1 1 100%;
  border: 1px solid var(--wp-border-strong);
  background: var(--wp-surface);
  color: var(--wp-accent-strong);

  &:not(:disabled):hover {
    background: var(--wp-surface-2);
  }
}

.confirmation-card__btn--deny {
  border: 1px solid var(--wp-border-strong);
  background: var(--wp-surface);
  color: var(--wp-text);

  &:not(:disabled):hover {
    background: var(--wp-surface-2);
  }
}

.confirmation-card__btn--approve {
  border: 1px solid var(--wp-accent);
  background: var(--wp-accent);
  color: var(--wp-canard);

  &:not(:disabled):hover {
    background: var(--wp-accent-strong);
  }
}
</style>
