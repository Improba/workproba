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

    <template v-if="preparing">
      <p class="confirmation-card__summary">{{ t('chat.confirmationPreparing') }}</p>
    </template>
    <template v-else-if="showExternalManagedLayout">
      <p class="confirmation-card__headline">{{ externalPrimarySummary }}</p>
      <p v-if="externalSecondaryTarget" class="confirmation-card__secondary">
        {{ t('chat.confirmationTarget', { target: externalSecondaryTarget }) }}
      </p>
      <dl
        v-if="externalArgEntries.length"
        class="confirmation-card__args"
        data-testid="confirmation-args"
      >
        <div
          v-for="entry in externalArgEntries"
          :key="entry.key"
          class="confirmation-card__arg"
        >
          <dt>{{ entry.key }}</dt>
          <dd>{{ entry.value }}</dd>
        </div>
      </dl>
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
    <template v-else-if="hasEffectHeadline">
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

    <div v-if="!preparing" class="confirmation-card__actions">
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
      <button
        v-if="canApproveRemaining"
        type="button"
        class="confirmation-card__btn confirmation-card__btn--approve-remaining"
        :disabled="busy"
        :title="t('chat.confirmationApproveRemainingHint')"
        :aria-label="t('chat.confirmationApproveRemaining')"
        @click="emit('approve-remaining')"
      >
        {{ busy ? t('common.inProgress') : t('chat.confirmationApproveRemaining') }}
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
  /** Skeleton pendant la préparation (avant résumé riche). */
  preparing?: boolean;
}>();

const { t } = useI18n();

const emit = defineEmits<{
  approve: [];
  'approve-remaining': [];
  cancel: [];
}>();

const canApproveRemaining = computed(
  () => !props.preparing && Boolean(props.confirmation.trustKey?.trim()),
);

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

const isExternalOrManagedConfirmation = computed(() => {
  const { effect, toolName } = props.confirmation;
  return (
    effect === 'external_send' ||
    toolName === 'invoke_managed_connector' ||
    toolName.startsWith('managed_')
  );
});

const externalPrimarySummary = computed(
  () => props.confirmation.humanSummary?.trim() ?? '',
);

const showExternalManagedLayout = computed(
  () =>
    isExternalOrManagedConfirmation.value &&
    Boolean(externalPrimarySummary.value),
);

const externalSecondaryTarget = computed(() => {
  if (!showExternalManagedLayout.value) return null;
  const headline = props.confirmation.headline?.trim();
  if (!headline) return null;
  const colonIndex = headline.indexOf(':');
  if (colonIndex === -1) return null;
  const target = headline.slice(colonIndex + 1).trim();
  if (!target) return null;
  if (externalPrimarySummary.value.toLowerCase().includes(target.toLowerCase())) {
    return null;
  }
  return target;
});

const EXTERNAL_ARG_SKIP = new Set([
  'connector_id',
  'connectorId',
  'tool_name',
  'toolName',
]);

const RESOLVED_SUMMARY_RAW_USER_ARG_SKIP = new Set(['userId', 'email']);

function humanSummaryHasResolvedUser(summary: string): boolean {
  return summary.includes('userId') && summary.includes('@');
}

const USER_ARG_PRIORITY = [
  'resolvedDisplayName',
  'resolvedEmail',
  'resolvedUserId',
  'userId',
  'email',
  'firstname',
  'lastname',
  'firstName',
  'lastName',
];

function userArgSortIndex(key: string): number {
  const idx = USER_ARG_PRIORITY.indexOf(key);
  return idx === -1 ? USER_ARG_PRIORITY.length : idx;
}

function formatArgValue(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return null;
    return value
      .map((item) => formatArgValue(item))
      .filter((item): item is string => Boolean(item))
      .join(', ');
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return null;
    }
  }
  return null;
}

const externalArgEntries = computed(() => {
  if (!showExternalManagedLayout.value || !props.toolArgs) return [];
  const skipRawUserArgs = humanSummaryHasResolvedUser(externalPrimarySummary.value);
  const entries: { key: string; value: string }[] = [];
  for (const [key, raw] of Object.entries(props.toolArgs)) {
    if (EXTERNAL_ARG_SKIP.has(key)) continue;
    if (skipRawUserArgs && RESOLVED_SUMMARY_RAW_USER_ARG_SKIP.has(key)) continue;
    const value = formatArgValue(raw);
    if (!value) continue;
    entries.push({ key, value });
  }
  return entries.sort((left, right) => {
    const leftIdx = userArgSortIndex(left.key);
    const rightIdx = userArgSortIndex(right.key);
    if (leftIdx !== rightIdx) return leftIdx - rightIdx;
    return left.key.localeCompare(right.key);
  });
});

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

.confirmation-card__secondary {
  margin: -0.35rem 0 0.75rem;
  font-size: var(--wp-fs-sm, 0.875rem);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted, var(--wp-text));
}

.confirmation-card__args {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.65rem;
  border-radius: var(--wp-r-sm, 0.35rem);
  background: color-mix(in srgb, var(--wp-surface) 70%, transparent);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.confirmation-card__arg {
  display: grid;
  grid-template-columns: minmax(5rem, max-content) 1fr;
  gap: 0.5rem 0.75rem;
  font-size: var(--wp-fs-sm, 0.875rem);
  line-height: var(--wp-lh-normal);

  dt {
    margin: 0;
    font-weight: 600;
    color: var(--wp-text-muted, var(--wp-text));
  }

  dd {
    margin: 0;
    font-family: var(--wp-font-mono, ui-monospace, monospace);
    color: var(--wp-text);
    word-break: break-word;
  }
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

.confirmation-card__btn--approve-remaining {
  flex: 1 1 100%;
  border: 1px solid var(--wp-border-strong);
  background: var(--wp-surface);
  color: var(--wp-accent-strong);

  &:not(:disabled):hover {
    background: var(--wp-surface-2);
  }
}
</style>
