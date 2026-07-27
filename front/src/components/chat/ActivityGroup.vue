<template>
  <section class="activity-group" :aria-label="summaryAria">
    <button
      type="button"
      class="activity-group__toggle"
      :aria-expanded="effectiveExpanded"
      :aria-controls="effectiveExpanded ? panelId : undefined"
      @click="onToggle"
    >
      <span
        v-if="hasToolCall"
        class="activity-group__icon"
        aria-hidden="true"
      >
        <Lucide name="wrench" size="12" color="wp-text-muted" />
      </span>
      <span
        v-else-if="isThinkingOnlyRunning"
        class="activity-group__spinner"
        aria-hidden="true"
      />
      <q-icon
        v-else
        name="psychology"
        size="12px"
        class="activity-group__icon"
        aria-hidden="true"
      />
      <span class="activity-group__toggle-label">{{ summaryText }}</span>
      <Lucide
        name="chevron-down"
        size="12"
        color="wp-text-muted"
        :class="
          effectiveExpanded
            ? 'activity-group__chevron activity-group__chevron--up'
            : 'activity-group__chevron'
        "
      />
    </button>

    <div v-if="effectiveExpanded" :id="panelId" class="activity-group__panel">
      <template v-for="part in group.parts" :key="part.id">
        <ThinkingCard
          v-if="part.type === 'thinking'"
          :thinking="part"
          :streaming="streaming"
          :embedded="true"
        />
        <div
          v-else-if="part.type === 'tool_call' && toolCallById(part.toolCallId)"
          :class="{
            'activity-group__confirmation-group':
              pendingConfirmation?.toolCallId === part.toolCallId ||
              preparingConfirmation?.toolCallId === part.toolCallId,
          }"
        >
          <ToolCallCard
            :tool-call="toolCallById(part.toolCallId)!"
            :project-path="projectPath"
            :session-id="sessionId"
            :confirmation-active="
              pendingConfirmation?.toolCallId === part.toolCallId ||
              preparingConfirmation?.toolCallId === part.toolCallId
            "
            @open-file="(path) => emit('open-file', path)"
            @restored="(path) => emit('restored', path)"
          />
          <ConfirmationCard
            v-if="
              preparingConfirmation?.toolCallId === part.toolCallId &&
              !pendingConfirmation
            "
            :confirmation="preparingConfirmationStub(part.toolCallId)"
            preparing
            attached
          />
          <ConfirmationCard
            v-if="pendingConfirmation?.toolCallId === part.toolCallId"
            :confirmation="pendingConfirmation"
            :busy="confirming"
            :workspace-data-dir="workspaceDataDir"
            :project-path="projectPath"
            :tool-args="toolCallById(part.toolCallId)?.args"
            attached
            @approve="emit('confirm-approve')"
            @approve-remaining="emit('confirm-approve-remaining')"
            @cancel="emit('confirm-deny')"
          />
        </div>
        <p
          v-else-if="part.type === 'tool_call'"
          class="activity-group__unknown-tool"
        >
          {{ t('chat.unknownTool') }}
        </p>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';
import ToolCallCard from '@components/chat/ToolCallCard.vue';
import ConfirmationCard from '@components/chat/ConfirmationCard.vue';
import { useActivityGroupExpansion } from '@composables/useToolCallExpansion';
import {
  computeActivityGroupStats,
  deriveConnectorSuffix,
  type ActivityGroupData,
} from '@utils/activityGroup';
import { t as tCount } from '@utils/i18nT';
import type { ChatConfirmation, ChatThinkingPart, ChatToolCall } from '#types';

const props = defineProps<{
  group: ActivityGroupData;
  toolCalls?: ChatToolCall[];
  streaming?: boolean;
  pendingConfirmation?: ChatConfirmation | null;
  preparingConfirmation?: { toolCallId: string; toolName?: string } | null;
  confirming?: boolean;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-approve-remaining': [];
  'confirm-deny': [];
}>();

const { t } = useI18n();

const panelId = computed(() => `activity-group-${props.group.id.replace(/\|/g, '-')}`);

const toolCallsById = computed(() => {
  const map = new Map<string, ChatToolCall>();
  for (const tc of props.toolCalls ?? []) {
    map.set(tc.id, tc);
  }
  return map;
});

const toolCallParts = computed(() =>
  props.group.parts.filter(
    (part): part is { type: 'tool_call'; id: string; toolCallId: string } =>
      part.type === 'tool_call',
  ),
);

const hasToolCall = computed(() => toolCallParts.value.length > 0);

const thinkingParts = computed(() =>
  props.group.parts.filter(
    (part): part is ChatThinkingPart => part.type === 'thinking',
  ),
);

const firstThinkingPart = computed(() => thinkingParts.value[0] ?? null);

const isThinkingOnlyRunning = computed(() => {
  if (hasToolCall.value) return false;
  const part = firstThinkingPart.value;
  return Boolean(props.streaming && part && !part.done);
});

const thinkingOnlySummary = computed(() => {
  const subject = firstThinkingPart.value?.subject?.trim();
  if (subject) return subject;
  if (isThinkingOnlyRunning.value) return t('chat.thinking');
  return t('chat.reasoning');
});

const stats = computed(() =>
  computeActivityGroupStats(toolCallParts.value, toolCallsById.value),
);

const connectorSuffix = computed(() => {
  const calls = toolCallParts.value
    .map((part) => toolCallsById.value.get(part.toolCallId))
    .filter((tc): tc is ChatToolCall => tc != null);
  return deriveConnectorSuffix(calls);
});

const hasPendingConfirmation = computed(() => {
  const pendingId = props.pendingConfirmation?.toolCallId;
  const preparingId = props.preparingConfirmation?.toolCallId;
  if (!pendingId && !preparingId) return false;
  return props.group.toolCallIds.some(
    (id) => id === pendingId || id === preparingId,
  );
});

const { expanded, toggle } = useActivityGroupExpansion(
  () => props.group.id,
  () => hasPendingConfirmation.value,
);

const effectiveExpanded = computed(() =>
  hasPendingConfirmation.value ? true : expanded.value,
);

const summaryText = computed(() => {
  if (!hasToolCall.value) {
    return thinkingOnlySummary.value;
  }

  const segments: string[] = [
    tCount('chat.activityUsedTools', stats.value.toolCount, {
      count: stats.value.toolCount,
    }),
  ];
  if (stats.value.errorCount > 0) {
    segments.push(
      tCount('chat.activityErrors', stats.value.errorCount, {
        count: stats.value.errorCount,
      }),
    );
  }
  if (stats.value.hasRunning) {
    segments.push(t('chat.activityRunning'));
  }
  const connector = connectorSuffix.value;
  if (connector) {
    segments.push(connector);
  }
  return segments.join(' · ');
});

const summaryAria = computed(() =>
  t('chat.activitySummaryAria', {
    summary: summaryText.value,
  }),
);

function onToggle(): void {
  if (hasPendingConfirmation.value) return;
  toggle();
}

function toolCallById(id: string): ChatToolCall | undefined {
  return toolCallsById.value.get(id);
}

function preparingConfirmationStub(toolCallId: string): ChatConfirmation {
  const preparing = props.preparingConfirmation;
  return {
    confirmationId: '',
    toolCallId,
    toolName: preparing?.toolName ?? '',
    action: 'create',
    proposedPath: '',
    humanSummary: '',
  };
}
</script>

<style scoped lang="scss">
.activity-group {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--wp-space-1);
}

.activity-group__toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  max-width: 100%;
  padding: 2px var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  cursor: pointer;
  transition:
    background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-3);
    border-color: color-mix(in srgb, var(--wp-text-muted) 35%, var(--wp-border));
    color: var(--wp-text);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }

  &[aria-expanded='true'] {
    background: var(--wp-surface-3);
    border-color: color-mix(in srgb, var(--wp-text-muted) 35%, var(--wp-border));
    color: var(--wp-text);
  }
}

.activity-group__toggle-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-group__icon {
  flex-shrink: 0;
  color: var(--wp-text-muted);
}

.activity-group__spinner {
  flex-shrink: 0;
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 999px;
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: activity-group-spin 0.7s linear infinite;
}

@keyframes activity-group-spin {
  to {
    transform: rotate(360deg);
  }
}

.activity-group__chevron {
  flex-shrink: 0;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.activity-group__panel {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  width: 100%;
}

.activity-group__confirmation-group {
  display: flex;
  flex-direction: column;
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;

  :deep(.tool-call-card) {
    box-shadow: none;
    border-bottom: none;
    border-radius: var(--wp-r-md) var(--wp-r-md) 0 0;
  }

  :deep(.confirmation-card) {
    margin-top: 0;
    box-shadow: none;
    border-radius: 0 0 var(--wp-r-md) var(--wp-r-md);
    border-top: 1px dashed color-mix(in srgb, var(--wp-accent) 35%, var(--wp-border));
  }
}

.activity-group__unknown-tool {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
}
</style>
