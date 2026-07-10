<template>
  <div
    class="confirmation-card"
    data-testid="confirmation-card"
    role="region"
    aria-label="Confirmation requise"
  >
    <p class="confirmation-card__summary" v-html="summaryHtml" />

    <div class="confirmation-card__actions">
      <button
        type="button"
        class="confirmation-card__btn confirmation-card__btn--deny"
        :disabled="busy"
        aria-label="Annuler l'action"
        @click="emit('cancel')"
      >
        {{ busy ? 'En cours…' : 'Annuler' }}
      </button>
      <button
        type="button"
        class="confirmation-card__btn confirmation-card__btn--approve"
        :disabled="busy"
        aria-label="Continuer l'action"
        @click="emit('approve')"
      >
        {{ busy ? 'En cours…' : 'Continuer' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ChatConfirmation } from '#types';

const props = defineProps<{
  confirmation: ChatConfirmation;
  busy?: boolean;
}>();

const emit = defineEmits<{
  approve: [];
  cancel: [];
}>();

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

const summaryHtml = computed(() => {
  const summary = props.confirmation.humanSummary?.trim();
  if (summary) {
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
  }

  const verb = props.confirmation.action === 'modify' ? 'modifier' : 'créer';
  const file = escapeHtml(fileLabel(props.confirmation.proposedPath));
  return `Je vais <strong>${verb}</strong> <strong class="confirmation-card__file">${file}</strong>`;
});
</script>

<style scoped lang="scss">
.confirmation-card {
  margin: 0.35rem 0;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
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
