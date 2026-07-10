<template>
  <div class="tool-call-card" data-testid="tool-call-card">
    <div class="tool-call-card__human">
      <span
        class="tool-call-card__dot"
        :class="`tool-call-card__dot--${toolCall.status}`"
        aria-hidden="true"
      />
      <p class="tool-call-card__summary">{{ humanLabel }}</p>
      <button
        v-if="toolCall.filePath"
        type="button"
        class="tool-call-card__file-btn"
        @click="emit('open-file', toolCall.filePath!)"
      >
        <Lucide name="file-text" size="xs" color="wp-accent" />
        {{ fileName }}
      </button>
      <button
        type="button"
        class="tool-call-card__tech-pill"
        :class="{ 'tool-call-card__tech-pill--active': isTechView }"
        :aria-pressed="isTechView"
        @click="toggleTechView"
      >
        Vue technique
      </button>
    </div>

    <RestoreBanner
      v-if="showRestoreBanner"
      :project-path="projectPath!"
      :session-id="sessionId!"
      :file-path="toolCall.filePath!"
      :snapshot-path="toolCall.snapshotPath"
      @restored="(path) => emit('restored', path)"
    />

    <div v-if="isTechView" class="tool-call-card__tech">
      <div class="tool-call-card__tech-header">
        <span class="tool-call-card__tool-name">{{ toolCall.name }}</span>
        <span v-if="durationLabel" class="tool-call-card__duration">{{ durationLabel }}</span>
        <q-spinner
          v-if="toolCall.status === 'running' || toolCall.status === 'awaiting_confirmation'"
          size="14px"
          class="tool-call-card__spinner"
        />
      </div>

      <section v-if="toolCall.args && Object.keys(toolCall.args).length">
        <h4 class="tool-call-card__section-title">Arguments</h4>
        <pre class="tool-call-card__json">{{ formattedArgs }}</pre>
      </section>

      <section v-if="toolCall.result !== undefined">
        <h4 class="tool-call-card__section-title">Résultat</h4>
        <pre class="tool-call-card__json">{{ formattedResult }}</pre>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import RestoreBanner from '@components/chat/RestoreBanner.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { fallbackHumanLabel } from '@utils/toolCallHumanLabel';
import type { ChatToolCall } from '#types';

const props = defineProps<{
  toolCall: ChatToolCall;
  projectPath?: string | null;
  sessionId?: string | null;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
}>();

const { toolCallView, setToolCallView } = useAppSettings();

const isTechView = computed(() => toolCallView.value === 'tech');

const showRestoreBanner = computed(
  () =>
    props.toolCall.name === 'generate_document' &&
    props.toolCall.status === 'success' &&
    Boolean(props.toolCall.filePath) &&
    Boolean(props.projectPath) &&
    Boolean(props.sessionId),
);

const humanLabel = computed(() => {
  if (props.toolCall.status === 'awaiting_confirmation') {
    const summary = props.toolCall.humanSummary?.trim();
    if (summary) return summary;
    return 'En attente de votre confirmation';
  }
  const summary = props.toolCall.humanSummary?.trim();
  if (summary) return summary;
  return fallbackHumanLabel(props.toolCall.name, props.toolCall.args);
});

const durationLabel = computed(() => {
  const { startedAt, endedAt } = props.toolCall;
  if (!startedAt) return '';
  const end = endedAt ?? Date.now();
  const ms = Math.max(0, end - startedAt);
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
});

const formattedArgs = computed(() =>
  JSON.stringify(props.toolCall.args ?? {}, null, 2),
);

const formattedResult = computed(() => {
  const { result } = props.toolCall;
  if (typeof result === 'string') return result;
  return JSON.stringify(result, null, 2);
});

const fileName = computed(() => {
  const path = props.toolCall.filePath ?? '';
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
});

async function toggleTechView(): Promise<void> {
  await setToolCallView(isTechView.value ? 'human' : 'tech');
}
</script>

<style scoped lang="scss">
.tool-call-card {
  margin: 0.5rem 0;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  overflow: hidden;
}

.tool-call-card__human {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  color: var(--wp-text);
}

.tool-call-card__human + .restore-banner {
  margin: 0 0.85rem 0.65rem;
}

.tool-call-card__dot {
  flex: 0 0 auto;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);

  &--running {
    background: var(--wp-accent);
    animation: wp-breathe 1.6s ease-in-out infinite;
  }

  &--success {
    background: var(--wp-success);
  }

  &--error {
    background: var(--wp-danger);
  }

  &--pending {
    background: var(--wp-gold);
  }

  &--awaiting_confirmation {
    background: var(--wp-gold);
    animation: wp-breathe 1.6s ease-in-out infinite;
  }
}

.tool-call-card__summary {
  flex: 1 1 auto;
  margin: 0;
  min-width: 0;
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
}

.tool-call-card__file-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-sm);
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.tool-call-card__tech-pill {
  flex: 0 0 auto;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    color var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    border-color: var(--wp-border-strong);
    color: var(--wp-text);
  }

  &--active {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
    color: var(--wp-accent-strong);
  }
}

.tool-call-card__tech {
  padding: 0.75rem 0.85rem 0.85rem;
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface-2);
}

.tool-call-card__tech-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}

.tool-call-card__tool-name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-call-card__spinner {
  color: var(--wp-accent);
}

.tool-call-card__duration {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  font-variant-numeric: tabular-nums;
}

.tool-call-card__section-title {
  margin: 0 0 0.35rem;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--wp-text-muted);
}

.tool-call-card__json {
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-3);
  color: var(--wp-text);
  font-family: var(--wp-font-mono);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
