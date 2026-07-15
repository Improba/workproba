<template>
  <ul v-if="citations.length" class="memory-citations" role="list">
    <li
      v-for="cite in citations"
      :key="cite.id"
      class="memory-citations__item"
    >
      <button
        type="button"
        class="memory-citations__chip"
        :title="chipTitle(cite)"
        :aria-label="chipAria(cite)"
        @click="onClick(cite)"
      >
        <Lucide name="brain" size="12" color="wp-violet" />
        <span class="memory-citations__snippet">{{ cite.snippet }}</span>
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useMemoryPanel } from '@composables/useMemoryPanel';
import type { MemoryCitation } from '#types';

defineProps<{
  citations: MemoryCitation[];
}>();

const { t } = useI18n();
const { openMemoryPanel } = useMemoryPanel();

function chipTitle(cite: MemoryCitation): string {
  if (cite.source?.trim()) {
    return t('memory.citationTooltip', { source: cite.source, snippet: cite.snippet });
  }
  return cite.snippet;
}

function chipAria(cite: MemoryCitation): string {
  return t('memory.citationAria', { snippet: cite.snippet });
}

function onClick(cite: MemoryCitation): void {
  openMemoryPanel(cite.id);
}
</script>

<style scoped lang="scss">
.memory-citations {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.memory-citations__item {
  margin: 0;
}

.memory-citations__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  max-width: 100%;
  padding: 2px var(--wp-space-2);
  border: 1px solid color-mix(in srgb, var(--wp-violet) 35%, var(--wp-border));
  border-radius: var(--wp-r-pill);
  background: var(--wp-violet-soft);
  color: var(--wp-violet);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  cursor: pointer;
  transition:
    background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: color-mix(in srgb, var(--wp-violet-soft) 70%, var(--wp-violet));
    border-color: var(--wp-violet);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.memory-citations__snippet {
  min-width: 0;
  max-width: 18rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
