<template>
  <div class="thinking-card" data-testid="thinking-card">
    <button
      type="button"
      class="thinking-card__header"
      :aria-expanded="expanded"
      :aria-controls="bodyRegionId"
      :aria-label="headerAriaLabel"
      @click="toggle"
    >
      <span
        v-if="showSpinner"
        class="thinking-card__spinner"
        aria-hidden="true"
      />
      <q-icon
        v-else
        name="psychology"
        size="16px"
        class="thinking-card__icon"
        aria-hidden="true"
      />
      <span class="thinking-card__labels">
        <span
          class="thinking-card__label"
          data-testid="thinking-card__subject"
          aria-live="polite"
          :aria-busy="showSpinner"
        >
          {{ headerPrimaryLabel }}
        </span>
        <span
          v-if="headerSecondaryLabel"
          class="thinking-card__label-secondary"
        >
          {{ headerSecondaryLabel }}
        </span>
      </span>
      <span class="thinking-card__hint">
        {{ expanded ? t('common.hide') : t('common.show') }}
      </span>
      <Lucide
        name="chevron-down"
        size="xs"
        color="wp-text-muted"
        :class="expanded ? 'thinking-card__chevron thinking-card__chevron--up' : 'thinking-card__chevron'"
      />
    </button>

    <div
      v-if="expanded"
      :id="bodyRegionId"
      class="thinking-card__body"
      role="region"
      :aria-label="t('chat.reasoning')"
    >
      <div
        class="thinking-card__view-toggle"
        data-testid="thinking-card__view-toggle"
        role="group"
        :aria-label="t('chat.thinkingViewToggleAria')"
      >
        <button
          type="button"
          class="thinking-card__view-btn"
          :class="{ 'thinking-card__view-btn--active': detailView === 'summary' }"
          :aria-pressed="detailView === 'summary'"
          @click.stop="setDetailView('summary')"
        >
          {{ t('chat.thinkingViewSummary') }}
        </button>
        <button
          type="button"
          class="thinking-card__view-btn"
          :class="{ 'thinking-card__view-btn--active': detailView === 'raw' }"
          :aria-pressed="detailView === 'raw'"
          @click.stop="setDetailView('raw')"
        >
          {{ t('chat.thinkingViewRaw') }}
        </button>
      </div>

      <div
        v-if="detailView === 'summary'"
        class="thinking-card__summary"
        data-testid="thinking-card__summary"
      >
        <span class="thinking-card__summary-text">
          {{ summaryText }}
        </span>
      </div>
      <div
        v-else
        class="thinking-card__raw"
        data-testid="thinking-card__raw"
      >
        <span class="thinking-card__raw-text">{{ rawText }}</span>
        <span
          v-if="showCursor"
          class="thinking-card__cursor"
          aria-hidden="true"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useI18n } from 'vue-i18n';
import { useAppSettings } from '@composables/useAppSettings';
import { useThinkingExpansion } from '@composables/useToolCallExpansion';
import type { ChatThinkingPart } from '#types';
import type { ThinkingDetailViewMode } from '@composables/useDesktop.types';

const props = defineProps<{
  thinking: ChatThinkingPart;
  streaming: boolean;
}>();

const { t } = useI18n();
const { thinkingDetailView, setThinkingDetailView } = useAppSettings();

const { expanded, toggle } = useThinkingExpansion(() => props.thinking.id);

const detailView = computed(() => thinkingDetailView.value);

const bodyRegionId = computed(() => `thinking-card-body-${props.thinking.id}`);

const showSpinner = computed(
  () => props.streaming && !props.thinking.done,
);

const debouncedSubject = ref<string | null>(null);
let subjectDebounceTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.thinking.subject,
  (subject) => {
    if (subjectDebounceTimer) clearTimeout(subjectDebounceTimer);
    if (!props.streaming || props.thinking.done) {
      debouncedSubject.value = subject ?? null;
      return;
    }
    subjectDebounceTimer = setTimeout(() => {
      debouncedSubject.value = subject ?? null;
    }, 300);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (subjectDebounceTimer) {
    clearTimeout(subjectDebounceTimer);
    subjectDebounceTimer = null;
  }
});

const headerPrimaryLabel = computed(() => {
  const subject = debouncedSubject.value?.trim();
  if (subject) return subject;
  if (props.streaming && !props.thinking.done) return t('chat.thinking');
  return t('chat.reasoning');
});

const headerSecondaryLabel = computed(() => {
  if (!props.thinking.done) return '';
  if (debouncedSubject.value?.trim()) return t('chat.reasoning');
  return '';
});

const headerAriaLabel = computed(() => {
  const subject = debouncedSubject.value?.trim();
  if (subject) return t('chat.thinkingSubjectAria', { subject });
  return expanded.value ? t('common.hide') : t('chat.reasoning');
});

const summaryText = computed(() => {
  if (props.thinking.summary?.trim()) return props.thinking.summary;
  if (props.thinking.content?.trim()) return props.thinking.content;
  return t('chat.thinkingPlaceholder');
});

const rawText = computed(() => {
  if (props.thinking.content?.trim()) return props.thinking.content;
  return t('chat.thinkingPlaceholder');
});

const showCursor = computed(
  () =>
    detailView.value === 'raw' &&
    props.streaming &&
    !props.thinking.done &&
    Boolean(props.thinking.content?.trim()),
);

function setDetailView(view: ThinkingDetailViewMode): void {
  if (detailView.value === view) return;
  void setThinkingDetailView(view);
}
</script>

<style scoped lang="scss">
.thinking-card {
  width: 100%;
  margin: 0;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;
}

.thinking-card__header {
  display: flex;
  /* Première ligne du subject : icône alignée dessus, jamais seule au-dessus. */
  align-items: flex-start;
  flex-wrap: nowrap;
  gap: 0.5rem;
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: none;
  background: transparent;
  color: var(--wp-text);
  text-align: left;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.thinking-card__icon {
  flex: 0 0 auto;
  /* Aligne le glyphe 16px sur la 1re ligne du label (fs-sm / lh-normal). */
  margin-top: 0.15rem;
  color: var(--wp-text-muted);
}

.thinking-card__labels {
  /* Basis 0 : tronque le subject au lieu de faire wraper l'icône. */
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.thinking-card__label {
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thinking-card__label-secondary {
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  font-weight: 500;
  color: var(--wp-text-muted);
}

.thinking-card__hint {
  flex: 0 0 auto;
  align-self: center;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

.thinking-card__chevron {
  flex: 0 0 auto;
  align-self: center;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.thinking-card__spinner {
  flex: 0 0 auto;
  width: 0.9rem;
  height: 0.9rem;
  margin-top: 0.2rem;
  border-radius: 999px;
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: thinking-spin 0.7s linear infinite;
}

@keyframes thinking-spin {
  to {
    transform: rotate(360deg);
  }
}

.thinking-card__body {
  padding: 0.75rem 0.85rem 0.85rem;
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface-2);
  max-height: 320px;
  overflow-y: auto;
}

.thinking-card__view-toggle {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.65rem;
}

.thinking-card__view-btn {
  padding: 0.15rem 0.45rem;
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: color var(--wp-dur) var(--wp-ease),
    background var(--wp-dur) var(--wp-ease);

  &:hover {
    color: var(--wp-text);
    background: var(--wp-surface);
  }

  &--active {
    color: var(--wp-text);
    background: var(--wp-surface);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.thinking-card__summary {
  font-family: var(--wp-font);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text);
}

.thinking-card__summary-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.thinking-card__raw {
  font-family: var(--wp-font-mono);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text-muted);
}

.thinking-card__raw-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.thinking-card__cursor {
  display: inline-block;
  width: 0.45rem;
  height: 1em;
  margin-left: 1px;
  vertical-align: text-bottom;
  background: var(--wp-accent);
  animation: thinking-cursor-blink 1s step-end infinite;
}

@keyframes thinking-cursor-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
