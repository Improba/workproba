<template>
  <article
    class="specialist-handoff-card"
    role="region"
    :aria-label="t('personas.handoff.cardLabel', { name: card.specialistName })"
  >
    <span
      class="wp-sr-only"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {{ liveStatusMessage }}
    </span>

    <header class="specialist-handoff-card__header">
      <PersonaAvatar
        :name="card.specialistName"
        :color="card.avatarColor"
        :icon="card.avatarIcon"
      />
      <div class="specialist-handoff-card__head-meta">
        <p class="specialist-handoff-card__takeover">
          {{ takeoverLabel }}
        </p>
        <p
          v-if="card.task"
          class="specialist-handoff-card__task"
        >
          {{ card.task }}
        </p>
        <div class="specialist-handoff-card__chips">
          <span
            class="specialist-handoff-card__badge"
            :class="`specialist-handoff-card__badge--${card.mode}`"
          >
            {{ badgeLabel }}
          </span>
        </div>
      </div>
      <span
        v-if="isRunning"
        class="specialist-handoff-card__status"
        aria-hidden="true"
      >
        {{ t('common.inProgress') }}
      </span>
      <span
        v-else-if="isPending"
        class="specialist-handoff-card__status specialist-handoff-card__status--pending"
        aria-hidden="true"
      >
        {{ t('personas.handoff.pendingAuthorization') }}
      </span>
      <span
        v-else-if="card.status === 'error'"
        class="specialist-handoff-card__status specialist-handoff-card__status--error"
        aria-hidden="true"
      >
        {{ t('personas.handoff.statusFailed') }}
      </span>
    </header>

    <div class="specialist-handoff-card__body">
      <p
        v-if="isPending"
        class="specialist-handoff-card__pending"
      >
        {{ t('personas.handoff.pendingAuthorization') }}
      </p>

      <!-- Encadré compact : pas de réponse / raisonnement à l'air libre. -->
      <SpecialistHandoffPreview
        v-if="isRunning && !detailOpen"
        :name="card.specialistName"
        :label="t('personas.handoff.analysing', { name: card.specialistName })"
        :avatar-color="card.avatarColor"
        :avatar-icon="card.avatarIcon"
      />

      <div
        v-if="hasDetailPayload"
        class="specialist-handoff-card__detail"
      >
        <button
          type="button"
          class="specialist-handoff-card__detail-toggle"
          :aria-expanded="detailOpen"
          :aria-controls="detailRegionId"
          @click="toggleDetail"
        >
          <span class="specialist-handoff-card__detail-label">
            {{ detailToggleLabel }}
          </span>
          <span class="specialist-handoff-card__detail-hint">
            {{ detailOpen ? t('common.hide') : t('common.show') }}
          </span>
          <Lucide
            name="chevron-down"
            size="xs"
            color="wp-text-muted"
            :class="
              detailOpen
                ? 'specialist-handoff-card__detail-chevron specialist-handoff-card__detail-chevron--up'
                : 'specialist-handoff-card__detail-chevron'
            "
          />
        </button>

        <div
          v-if="detailOpen"
          :id="detailRegionId"
          class="specialist-handoff-card__detail-body"
          role="region"
          :aria-label="t('personas.handoff.detailRegion')"
        >
          <ThinkingCard
            v-if="card.thinking"
            :thinking="handoffThinkingPart"
            :streaming="thinkingStreaming"
            embedded
          />
          <ul
            v-if="card.nestedTools?.length"
            class="specialist-handoff-card__nested-tools"
            :aria-label="t('personas.handoff.nestedTools')"
          >
            <li
              v-for="tool in card.nestedTools"
              :key="tool.id"
              class="specialist-handoff-card__nested-tool"
              :class="`specialist-handoff-card__nested-tool--${tool.status}`"
            >
              <span
                v-if="tool.status === 'running'"
                class="specialist-handoff-card__nested-tool-spinner"
                aria-hidden="true"
              />
              <span class="specialist-handoff-card__nested-tool-name">
                {{ tool.humanSummary || formatDegradedToolLabel(tool.name) }}
              </span>
            </li>
          </ul>
          <MessageTextPart
            v-if="card.content && card.status !== 'error'"
            class="specialist-handoff-card__content"
            :content="card.content"
            :streaming="isRunning"
          />
        </div>
      </div>

      <template v-if="card.status === 'done'">
        <div
          v-if="card.degradedTools?.length"
          class="specialist-handoff-card__degraded"
        >
          <Lucide name="alert-triangle" size="12" color="wp-text-muted" />
          <div class="specialist-handoff-card__degraded-copy">
            <span>{{ t('personas.handoff.degradedTools') }}</span>
            <ul class="specialist-handoff-card__degraded-list">
              <li
                v-for="toolName in card.degradedTools"
                :key="toolName"
              >
                {{ formatDegradedToolLabel(toolName) }}
              </li>
            </ul>
          </div>
        </div>
        <footer class="specialist-handoff-card__actions">
          <button
            type="button"
            class="specialist-handoff-card__action"
            @click="emit('discuss')"
          >
            {{ t('personas.handoff.discuss') }}
          </button>
        </footer>
      </template>

      <template v-else-if="card.status === 'error'">
        <p
          class="specialist-handoff-card__error"
          role="alert"
        >
          {{ card.content || t('personas.handoff.error') }}
        </p>
        <footer class="specialist-handoff-card__actions">
          <button
            type="button"
            class="specialist-handoff-card__action"
            @click="emit('discuss')"
          >
            {{ t('personas.handoff.discuss') }}
          </button>
        </footer>
      </template>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';
import SpecialistHandoffPreview from '@components/personas/SpecialistHandoffPreview.vue';
import type { ChatThinkingPart, SpecialistHandoffCard } from '#types';
import { fallbackHumanLabel } from '@utils/toolCallHumanLabel';
import { useThinkingExpansion } from '@composables/useToolCallExpansion';
import {
  deriveThinkingSubject,
  deriveThinkingSubjectDone,
  deriveThinkingSummary,
} from '@utils/thinkingPresentation';

const props = defineProps<{
  card: SpecialistHandoffCard;
}>();

const emit = defineEmits<{
  discuss: [];
}>();

const { t } = useI18n();

const { expanded: detailOpen, toggle: toggleDetail } = useThinkingExpansion(
  () => `handoff-detail-${props.card.id}`,
);

const detailRegionId = computed(
  () => `specialist-handoff-detail-${props.card.id}`,
);

const isPending = computed(() => props.card.status === 'pending');

const isRunning = computed(
  () =>
    !isPending.value &&
    (props.card.status === 'running' || props.card.streaming === true),
);

const hasDetailPayload = computed(
  () =>
    (Boolean(props.card.thinking?.trim()) ||
      Boolean(props.card.content?.trim()) ||
      Boolean(props.card.nestedTools?.length)) &&
    props.card.status !== 'error',
);

const detailToggleLabel = computed(() => {
  if (isRunning.value) {
    return t('personas.handoff.detailWhileRunning', {
      name: props.card.specialistName,
    });
  }
  return t('personas.handoff.detailDone', {
    name: props.card.specialistName,
  });
});

const thinkingStreaming = computed(
  () => isRunning.value && props.card.thinkingDone !== true,
);

const handoffThinkingPart = computed<ChatThinkingPart>(() => {
  const content = props.card.thinking ?? '';
  const done = props.card.thinkingDone === true || props.card.status === 'done';
  const subject = done
    ? deriveThinkingSubjectDone(content)
    : deriveThinkingSubject(content);
  const summary = done ? deriveThinkingSummary(content) : null;
  return {
    type: 'thinking',
    id: `${props.card.id}-thinking`,
    thinkingId: `${props.card.toolCallId}-thinking`,
    content,
    done,
    ...(subject ? { subject } : {}),
    ...(summary ? { summary } : {}),
  };
});

const modeLabel = computed(() =>
  props.card.mode === 'operative'
    ? t('personas.handoff.modeOperative')
    : t('personas.handoff.modeRegard'),
);

const badgeLabel = computed(() =>
  t('personas.handoff.badgeWithMode', {
    badge: t('personas.handoff.badge'),
    mode: modeLabel.value,
  }),
);

const takeoverLabel = computed(() => {
  if (props.card.status === 'error') {
    return t('personas.handoff.takeoverError', {
      name: props.card.specialistName,
    });
  }
  if (isPending.value) {
    return t('personas.handoff.pendingAuthorization');
  }
  if (isRunning.value) {
    return t('personas.handoff.takeoverRunning', {
      name: props.card.specialistName,
    });
  }
  return t('personas.handoff.takeoverDone', {
    name: props.card.specialistName,
  });
});

function formatDegradedToolLabel(toolName: string): string {
  return fallbackHumanLabel(toolName);
}

const liveStatusMessage = computed(() => {
  if (isPending.value) {
    return t('personas.handoff.pendingAuthorization');
  }
  if (isRunning.value) {
    return t('personas.handoff.analysing', { name: props.card.specialistName });
  }
  if (props.card.status === 'error') {
    return props.card.content?.trim() || t('personas.handoff.error');
  }
  if (props.card.status === 'done') {
    return t('personas.handoff.takeoverDone', {
      name: props.card.specialistName,
    });
  }
  return '';
});
</script>

<style scoped lang="scss">
.specialist-handoff-card {
  width: 100%;
  margin: var(--wp-space-2) 0;
  border: 1px solid color-mix(in srgb, var(--wp-gold) 40%, var(--wp-border));
  border-left: 3px solid var(--wp-gold);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  animation: specialist-handoff-slide-in 240ms var(--wp-ease) both;
}

@keyframes specialist-handoff-slide-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .specialist-handoff-card {
    animation: none;
  }
}

.specialist-handoff-card__header {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
}

.specialist-handoff-card__head-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.specialist-handoff-card__takeover {
  margin: 0;
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  line-height: var(--wp-lh-normal);
}

.specialist-handoff-card__task {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.specialist-handoff-card__chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--wp-space-1);
}

.specialist-handoff-card__badge {
  display: inline-flex;
  align-items: center;
  padding: 3px var(--wp-space-2);
  border-radius: var(--wp-r-pill);
  font-size: var(--wp-fs-xs);
  font-weight: 700;
  letter-spacing: 0.01em;
  background: var(--wp-surface-2, var(--wp-bg));
  color: var(--wp-text-muted);
  border: 1px solid var(--wp-border);

  &--regard {
    background: color-mix(in srgb, var(--wp-gold) 18%, var(--wp-surface));
    color: color-mix(in srgb, var(--wp-gold) 70%, var(--wp-text));
    border: 1px solid color-mix(in srgb, var(--wp-gold) 55%, transparent);
  }

  &--operative {
    background: color-mix(in srgb, var(--wp-accent) 16%, var(--wp-surface));
    color: var(--wp-accent-high);
    border: 1px solid color-mix(in srgb, var(--wp-accent) 55%, transparent);
  }
}

.specialist-handoff-card__status {
  flex: 0 0 auto;
  font-size: var(--wp-fs-xs);
  color: var(--wp-gold);
  font-weight: 600;
  white-space: nowrap;

  &--pending {
    color: var(--wp-text-muted);
  }

  &--error {
    color: var(--wp-danger);
  }
}

.specialist-handoff-card__body {
  padding: var(--wp-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.specialist-handoff-card__detail {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.specialist-handoff-card__detail-toggle {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2, var(--wp-bg));
  color: var(--wp-text);
  text-align: left;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    filter: brightness(0.98);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.specialist-handoff-card__detail-label {
  flex: 1 1 0;
  min-width: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: var(--wp-lh-normal);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.specialist-handoff-card__detail-hint {
  flex: 0 0 auto;
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

.specialist-handoff-card__detail-chevron {
  flex: 0 0 auto;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.specialist-handoff-card__detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2, var(--wp-bg));
}

.specialist-handoff-card__nested-tools {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.specialist-handoff-card__nested-tool {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);

  &--running {
    color: var(--wp-gold);
  }

  &--error {
    color: var(--wp-danger);
  }
}

.specialist-handoff-card__nested-tool-spinner {
  flex: 0 0 auto;
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 999px;
  border: 1.5px solid color-mix(in srgb, var(--wp-gold) 35%, transparent);
  border-top-color: var(--wp-gold);
  animation: specialist-handoff-nested-spin 0.7s linear infinite;
}

@keyframes specialist-handoff-nested-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .specialist-handoff-card__nested-tool-spinner {
    animation: none;
  }
}

.specialist-handoff-card__nested-tool-name {
  display: block;
  min-width: 0;
}

.specialist-handoff-card__pending {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  font-style: italic;
}

.specialist-handoff-card__content {
  font-family: var(--wp-font-chat, var(--wp-font-ui));
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text);

  :deep(.chat-message__markdown) {
    font-family: inherit;
    font-size: inherit;
    line-height: inherit;
    color: inherit;
  }

  :deep(p) {
    margin: 0 0 0.5rem;
  }

  :deep(p:last-child) {
    margin-bottom: 0;
  }
}

.specialist-handoff-card__degraded {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-1);
  margin: var(--wp-space-2) 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.specialist-handoff-card__degraded-copy {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.specialist-handoff-card__degraded-list {
  margin: 0;
  padding-left: 1.1rem;
}

.specialist-handoff-card__error {
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-danger);
  background: color-mix(in srgb, var(--wp-danger) 8%, var(--wp-surface));
  border: 1px solid color-mix(in srgb, var(--wp-danger) 25%, transparent);
}

.specialist-handoff-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-3);
  padding-top: var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
}

.specialist-handoff-card__action {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-gold) 50%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: var(--wp-gold-soft);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    filter: brightness(0.97);
  }
}
</style>
