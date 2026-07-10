<template>
  <div
    v-if="visible"
    class="chat-reasoning-control"
    title="Niveau de raisonnement de l'assistant pour cette conversation"
  >
    <span class="chat-reasoning-control__label">Raisonnement</span>
    <q-btn-toggle
      :model-value="modelValue"
      :options="toggleOptions"
      no-caps
      unelevated
      toggle-color="primary"
      class="chat-reasoning-control__toggle"
      aria-label="Niveau de raisonnement de l'assistant pour cette conversation"
      @update:model-value="onUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import { REASONING_EFFORT_OPTIONS, supportsReasoning } from '@utils/reasoningSupport';

const props = defineProps<{
  modelValue: ReasoningEffort;
  provider: LlmProviderName;
  model: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ReasoningEffort];
}>();

const visible = computed(() => supportsReasoning(props.provider, props.model));

const toggleOptions = REASONING_EFFORT_OPTIONS.map((opt) => ({
  label: opt.label,
  value: opt.value,
}));

function onUpdate(value: ReasoningEffort): void {
  emit('update:modelValue', value);
}
</script>

<style scoped lang="scss">
.chat-reasoning-control {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.chat-reasoning-control__label {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  white-space: nowrap;
}

.chat-reasoning-control__toggle {
  :deep(.q-btn) {
    min-height: 36px;
    min-width: 36px;
    padding: 0 0.45rem;
    font-size: var(--wp-fs-xs);
    font-weight: 600;
    border: 1px solid var(--wp-border);
    background: var(--wp-surface-2);
    color: var(--wp-text-muted);
  }

  :deep(.q-btn--active) {
    background: var(--wp-accent-soft);
    color: var(--wp-accent-strong);
    border-color: var(--wp-accent);
  }
}
</style>
