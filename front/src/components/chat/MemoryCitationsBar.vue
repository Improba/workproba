<template>
  <section
    v-if="citations.length"
    class="memory-citations"
    :aria-label="t('memory.citationsLabel')"
  >
    <button
      type="button"
      class="memory-citations__toggle"
      :aria-expanded="expanded"
      :aria-controls="listId"
      @click="expanded = !expanded"
    >
      <Lucide name="brain" size="12" color="wp-violet" />
      <span class="memory-citations__toggle-label">
        {{
          t('memory.citationsToggle', citations.length, {
            count: citations.length,
          })
        }}
      </span>
      <Lucide
        name="chevron-down"
        size="12"
        color="wp-text-muted"
        :class="
          expanded
            ? 'memory-citations__chevron memory-citations__chevron--up'
            : 'memory-citations__chevron'
        "
      />
    </button>

    <div v-if="expanded" :id="listId" class="memory-citations__panel">
      <p class="memory-citations__hint">{{ t('memory.citationsHint') }}</p>
      <ul class="memory-citations__list" role="list">
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
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useMemoryPanel } from '@composables/useMemoryPanel';
import type { MemoryCitation } from '#types';

const props = withDefaults(
  defineProps<{
    citations: MemoryCitation[];
    /** Ouvert par défaut (ex. cartes déjà repliées ailleurs). */
    defaultExpanded?: boolean;
  }>(),
  { defaultExpanded: false },
);

const { t } = useI18n();
const { openMemoryPanel } = useMemoryPanel();
const expanded = ref(props.defaultExpanded);
const listId = computed(
  () => `memory-citations-${props.citations.map((c) => c.id).join('-').slice(0, 48) || 'list'}`,
);

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
  flex-direction: column;
  align-items: flex-start;
  gap: var(--wp-space-1);
}

.memory-citations__toggle {
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
    background: var(--wp-violet-soft);
    border-color: color-mix(in srgb, var(--wp-violet) 35%, var(--wp-border));
    color: var(--wp-violet);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }

  &[aria-expanded='true'] {
    background: var(--wp-violet-soft);
    border-color: color-mix(in srgb, var(--wp-violet) 35%, var(--wp-border));
    color: var(--wp-violet);
  }
}

.memory-citations__toggle-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-citations__chevron {
  flex-shrink: 0;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.memory-citations__panel {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  width: 100%;
  padding: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
}

.memory-citations__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.memory-citations__list {
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
