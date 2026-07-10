<template>
  <div class="thinking-card" data-testid="thinking-card">
    <div class="thinking-card__header">
      <q-icon name="psychology" size="16px" class="thinking-card__icon" aria-hidden="true" />
      <span class="thinking-card__label">Raisonnement</span>
      <span
        v-if="streaming && !thinking.done"
        class="thinking-card__dot"
        aria-hidden="true"
      />
      <button
        type="button"
        class="thinking-card__toggle"
        :aria-expanded="expanded"
        :aria-label="expanded ? 'Masquer le raisonnement' : 'Voir le raisonnement'"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Masquer le raisonnement' : 'Voir le raisonnement' }}
      </button>
    </div>

    <div
      v-if="expanded"
      class="thinking-card__body"
      role="region"
      aria-label="Raisonnement"
    >
      <span class="thinking-card__text">{{ thinking.content }}</span>
      <span
        v-if="streaming && !thinking.done"
        class="thinking-card__cursor"
        aria-hidden="true"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { ChatThinkingPart } from '#types';

defineProps<{
  thinking: ChatThinkingPart;
  streaming: boolean;
}>();

const expanded = ref(false);
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
  padding: 0.65rem 0.85rem;
  color: var(--wp-text);
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

.thinking-card__dot {
  flex: 0 0 auto;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent);
  animation: wp-breathe 1.6s ease-in-out infinite;
}

.thinking-card__toggle {
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

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
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
