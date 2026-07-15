<template>
  <section v-if="citations.length" class="web-search-citations" :aria-label="t('webSearch.sourcesLabel')">
    <p class="web-search-citations__label">{{ t('webSearch.sourcesLabel') }}</p>
    <ul class="web-search-citations__list" role="list">
      <li
        v-for="cite in citations"
        :key="cite.url"
        class="web-search-citations__item"
      >
        <button
          type="button"
          class="web-search-citations__chip"
          :title="chipTitle(cite)"
          :aria-label="chipAria(cite)"
          @click="onClick(cite)"
        >
          <Lucide name="globe" size="12" color="wp-accent" />
          <span class="web-search-citations__title">{{ cite.title }}</span>
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { openExternalUrl } from '@composables/useDesktop';
import type { WebSearchCitation } from '#types';

defineProps<{
  citations: WebSearchCitation[];
}>();

const { t } = useI18n();

function chipTitle(cite: WebSearchCitation): string {
  if (cite.snippet?.trim()) {
    return t('webSearch.citationTooltip', { title: cite.title, snippet: cite.snippet });
  }
  return cite.title;
}

function chipAria(cite: WebSearchCitation): string {
  return t('webSearch.citationAria', { title: cite.title });
}

function onClick(cite: WebSearchCitation): void {
  void openExternalUrl(cite.url);
}
</script>

<style scoped lang="scss">
.web-search-citations {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.web-search-citations__label {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--wp-text-faint);
}

.web-search-citations__list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.web-search-citations__item {
  margin: 0;
}

.web-search-citations__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  max-width: 100%;
  padding: 2px var(--wp-space-2);
  border: 1px solid color-mix(in srgb, var(--wp-accent) 35%, var(--wp-border));
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent-soft);
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  cursor: pointer;
  transition:
    background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: color-mix(in srgb, var(--wp-accent-soft) 70%, var(--wp-accent));
    border-color: var(--wp-accent);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.web-search-citations__title {
  min-width: 0;
  max-width: 18rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
