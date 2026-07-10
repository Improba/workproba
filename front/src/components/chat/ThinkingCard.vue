<template>
  <div class="thinking-card" data-testid="thinking-card">
    <button
      type="button"
      class="thinking-card__header"
      :aria-expanded="expanded"
      :aria-label="expanded ? 'Masquer le raisonnement' : 'Voir le raisonnement'"
      @click="toggle"
    >
      <span
        v-if="streaming && !thinking.done"
        class="thinking-card__spinner"
        aria-hidden="true"
      />
      <q-icon v-else name="psychology" size="16px" class="thinking-card__icon" aria-hidden="true" />
      <span class="thinking-card__label">
        {{ streaming && !thinking.done ? 'Le modèle réfléchit…' : 'Raisonnement' }}
      </span>
      <span class="thinking-card__hint">
        {{ expanded ? 'Masquer' : 'Voir le détail' }}
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
      class="thinking-card__body"
      role="region"
      aria-label="Raisonnement"
    >
      <span class="thinking-card__text">{{ thinking.content || 'Le détail du raisonnement apparaîtra ici dès qu’il sera disponible.' }}</span>
      <span
        v-if="streaming && !thinking.done"
        class="thinking-card__cursor"
        aria-hidden="true"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useThinkingExpansion } from '@composables/useToolCallExpansion';
import type { ChatThinkingPart } from '#types';

const props = defineProps<{
  thinking: ChatThinkingPart;
  streaming: boolean;
}>();

// État déplié porté hors du composant pour survivre au recyclage du
// `DynamicScroller` (sinon le bloc se replie immédiatement au re-mesurage).
const { expanded, toggle } = useThinkingExpansion(() => props.thinking.id);
</script>

<style scoped lang="scss">
.thinking-card {
  margin: 0.5rem 0;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  overflow: hidden;
}

.thinking-card__header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
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
  color: var(--wp-text-muted);
}

.thinking-card__label {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  font-weight: 600;
}

.thinking-card__hint {
  flex: 0 0 auto;
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
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.thinking-card__spinner {
  flex: 0 0 auto;
  width: 0.9rem;
  height: 0.9rem;
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
  font-family: var(--wp-font-mono);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text-muted);
}

.thinking-card__text {
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
