<template>
  <section class="memory-panel" role="region" :aria-label="t('memory.title')">
    <header class="memory-panel__head">
      <Lucide name="brain" size="18" color="wp-violet" />
      <h2 class="memory-panel__title">{{ t('memory.title') }}</h2>
    </header>

    <div class="memory-panel__search">
      <input
        v-model="searchQuery"
        type="search"
        class="memory-panel__search-input"
        :placeholder="t('memory.searchPlaceholder')"
        :aria-label="t('memory.searchPlaceholder')"
        @keydown.enter.prevent="onSearch"
      />
      <button
        type="button"
        class="memory-panel__search-btn"
        :disabled="searching || !searchQuery.trim()"
        @click="onSearch"
      >
        <Lucide name="search" size="14" color="wp-violet" />
      </button>
    </div>

    <div v-if="loading" class="memory-panel__empty">{{ t('common.loading') }}</div>

    <div v-else-if="loadError" class="memory-panel__empty memory-panel__empty--error">
      <p>{{ t('memory.loadFailed') }}</p>
      <button type="button" class="memory-panel__retry" @click="emit('refresh')">
        {{ t('common.retry') }}
      </button>
    </div>

    <div v-else-if="displayItems.length === 0" class="memory-panel__empty">
      <Lucide name="brain" size="24" color="text-faint" />
      <p>{{ t('memory.empty') }}</p>
    </div>

    <ul v-else class="memory-panel__list" role="list">
      <li v-for="item in displayItems" :key="item.id" class="memory-panel__item">
        <p class="memory-panel__content">{{ item.content }}</p>
        <div class="memory-panel__meta">
          <span v-if="item.source" class="memory-panel__source">{{ item.source }}</span>
          <span v-if="item.created_at" class="memory-panel__date">{{ formatDate(item.created_at) }}</span>
        </div>
        <button
          type="button"
          class="memory-panel__forget"
          :disabled="forgettingId === item.id"
          @click="onForget(item.id)"
        >
          {{ t('memory.forget') }}
        </button>
      </li>
    </ul>

    <footer v-if="!loading && displayItems.length > 0" class="memory-panel__foot">
      <button
        type="button"
        class="memory-panel__forget-all"
        @click="forgetAllStep = 1"
      >
        {{ t('memory.forgetAll') }}
      </button>
    </footer>

    <!-- Double confirmation « Tout oublier » -->
    <q-dialog :model-value="forgetAllStep > 0" @update:model-value="(v) => { if (!v) forgetAllStep = 0; }">
      <div class="memory-panel__confirm" role="alertdialog">
        <header class="memory-panel__confirm-head">
          <Lucide name="alert-triangle" size="20" color="danger" />
          <h3 class="memory-panel__confirm-title">
            {{ forgetAllStep === 1 ? t('memory.forgetAllConfirm1Title') : t('memory.forgetAllConfirm2Title') }}
          </h3>
        </header>
        <p class="memory-panel__confirm-text">
          {{ forgetAllStep === 1 ? t('memory.forgetAllConfirm1Text') : t('memory.forgetAllConfirm2Text') }}
        </p>
        <footer class="memory-panel__confirm-foot">
          <button type="button" class="memory-panel__confirm-btn" @click="forgetAllStep = 0">
            {{ t('common.cancel') }}
          </button>
          <button
            v-if="forgetAllStep === 1"
            type="button"
            class="memory-panel__confirm-btn memory-panel__confirm-btn--warn"
            @click="forgetAllStep = 2"
          >
            {{ t('memory.forgetAllContinue') }}
          </button>
          <button
            v-else
            type="button"
            class="memory-panel__confirm-btn memory-panel__confirm-btn--danger"
            :disabled="forgettingAll"
            @click="onForgetAll"
          >
            {{ forgettingAll ? t('common.inProgress') : t('memory.forgetAllFinal') }}
          </button>
        </footer>
      </div>
    </q-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import type { MemoryItem, MemorySearchResult } from '@services/aiSidecar';

const props = defineProps<{
  memories: MemoryItem[];
  searchResults: MemorySearchResult[];
  loading?: boolean;
  searching?: boolean;
  loadError?: string | null;
}>();

const emit = defineEmits<{
  refresh: [];
  search: [query: string];
  forget: [id: string];
  forgetAll: [];
}>();

const { t, locale } = useI18n();

const searchQuery = ref('');
const forgettingId = ref<string | null>(null);
const forgettingAll = ref(false);
const forgetAllStep = ref(0);
const isSearchMode = ref(false);

const displayItems = computed(() => {
  if (isSearchMode.value && searchQuery.value.trim()) {
    return props.searchResults.map((r) => ({
      id: r.id,
      content: r.content,
      source: r.source ?? '',
      created_at: r.created_at ?? '',
      tags: [] as string[],
    }));
  }
  return props.memories;
});

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'short',
    });
  } catch {
    return '';
  }
}

function onSearch(): void {
  isSearchMode.value = true;
  emit('search', searchQuery.value);
}

async function onForget(id: string): Promise<void> {
  forgettingId.value = id;
  emit('forget', id);
  forgettingId.value = null;
}

async function onForgetAll(): Promise<void> {
  forgettingAll.value = true;
  emit('forgetAll');
  forgettingAll.value = false;
  forgetAllStep.value = 0;
}
</script>

<style scoped lang="scss">
.memory-panel {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding: var(--wp-space-3);
  min-height: 0;
}

.memory-panel__head {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
}

.memory-panel__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-violet);
}

.memory-panel__search {
  display: flex;
  gap: var(--wp-space-2);
}

.memory-panel__search-input {
  flex: 1;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &:focus {
    outline: none;
    border-color: var(--wp-violet);
  }
}

.memory-panel__search-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--wp-violet) 40%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: var(--wp-violet-soft);
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.memory-panel__empty {
  padding: var(--wp-space-4) 0;
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--wp-space-2);

  &--error {
    color: var(--wp-danger);
  }
}

.memory-panel__retry {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  cursor: pointer;
  font-size: var(--wp-fs-xs);
}

.memory-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.memory-panel__item {
  padding: var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-violet) 30%, var(--wp-border));
  border-left: 3px solid var(--wp-violet);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.memory-panel__content {
  margin: 0 0 var(--wp-space-2);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text);
}

.memory-panel__meta {
  display: flex;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.memory-panel__forget {
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-danger);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: color-mix(in srgb, var(--wp-danger) 8%, transparent);
  }

  &:disabled {
    opacity: 0.5;
  }
}

.memory-panel__foot {
  padding-top: var(--wp-space-2);
  border-top: 1px solid var(--wp-border);
}

.memory-panel__forget-all {
  width: 100%;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-danger) 40%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: color-mix(in srgb, var(--wp-danger) 8%, transparent);
  }
}

.memory-panel__confirm {
  width: 380px;
  max-width: 92vw;
  padding: var(--wp-space-4);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
}

.memory-panel__confirm-head {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-3);
}

.memory-panel__confirm-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.memory-panel__confirm-text {
  margin: 0 0 var(--wp-space-4);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text-muted);
}

.memory-panel__confirm-foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.memory-panel__confirm-btn {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);

  &--warn {
    border-color: var(--wp-warning, var(--wp-border));
    color: var(--wp-warning, var(--wp-text));
    font-weight: 600;
  }

  &--danger {
    background: var(--wp-danger);
    border-color: var(--wp-danger);
    color: #fff;
    font-weight: 600;
  }
}
</style>
