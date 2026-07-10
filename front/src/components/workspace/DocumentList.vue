<template>
  <section class="document-list">
    <header class="document-list__header">
      <h2 class="document-list__title">Documents</h2>
      <button
        v-if="showRefresh"
        type="button"
        class="document-list__refresh"
        :disabled="loading"
        aria-label="Actualiser"
        @click="emit('refresh')"
      >
        <Lucide name="refresh-cw" size="sm" color="text" />
      </button>
    </header>

    <div v-if="loading" class="document-list__state">
      <q-spinner size="24px" color="primary" />
      <span>Chargement des documents…</span>
    </div>

    <p v-else-if="!documents.length" class="document-list__state">
      Aucun document dans ce dossier.
    </p>

    <ul v-else class="document-list__items">
      <li
        v-for="doc in documents"
        :key="doc.relativePath"
        class="document-list__item"
      >
        <Lucide
          :name="doc.kind === 'directory' ? 'folder' : 'file-text'"
          size="sm"
          color="text"
        />
        <div class="document-list__meta">
          <span class="document-list__name">{{ doc.name }}</span>
          <span class="document-list__path">{{ doc.relativePath }}</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import type { LocalDocumentEntry } from '@composables/useDesktop.types';

withDefaults(
  defineProps<{
    documents: LocalDocumentEntry[];
    loading?: boolean;
    showRefresh?: boolean;
  }>(),
  {
    loading: false,
    showRefresh: true,
  },
);

const emit = defineEmits<{
  refresh: [];
}>();
</script>

<style scoped lang="scss">
.document-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--neutral-low);
  border-radius: 16px;
  background: var(--neutral-lowest);
}

.document-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.document-list__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
}

.document-list__refresh {
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--neutral-low);
  border-radius: 8px;
  background: var(--neutral-lower);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--neutral-low);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.document-list__state {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--neutral-medium);
}

.document-list__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-height: 320px;
  overflow-y: auto;
}

.document-list__item {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.45rem 0.55rem;
  border-radius: 10px;
  background: var(--neutral-lower);
}

.document-list__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.document-list__name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text);
  word-break: break-word;
}

.document-list__path {
  font-size: 0.75rem;
  color: var(--neutral-medium);
  word-break: break-all;
}
</style>
