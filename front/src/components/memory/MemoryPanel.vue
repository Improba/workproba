<template>
  <section class="memory-panel" role="region" :aria-label="t('memory.title')">
    <header class="memory-panel__head">
      <Lucide name="brain" size="18" color="wp-violet" />
      <h2 class="memory-panel__title">{{ t('memory.title') }}</h2>
    </header>

    <!-- Onglets de scope : User (global) / Project (espace) -->
    <div class="memory-panel__scopes" role="tablist">
      <button
        type="button"
        role="tab"
        class="memory-panel__scope"
        :class="{ 'memory-panel__scope--active': activeScope === 'user' }"
        :aria-selected="activeScope === 'user'"
        @click="onSwitchScope('user')"
      >
        <Lucide name="user" size="14" :color="activeScope === 'user' ? 'wp-violet' : 'text-muted'" />
        <span class="memory-panel__scope-label">{{ t('memory.scopeUser') }}</span>
        <span class="memory-panel__scope-hint">{{ t('memory.scopeUserHint') }}</span>
      </button>
      <button
        type="button"
        role="tab"
        class="memory-panel__scope"
        :class="{ 'memory-panel__scope--active': activeScope === 'project' }"
        :aria-selected="activeScope === 'project'"
        @click="onSwitchScope('project')"
      >
        <Lucide name="folder" size="14" :color="activeScope === 'project' ? 'wp-violet' : 'text-muted'" />
        <span class="memory-panel__scope-label">{{ t('memory.scopeProject') }}</span>
        <span class="memory-panel__scope-hint">{{ t('memory.scopeProjectHint') }}</span>
      </button>
    </div>

    <!-- Ajout d'un souvenir -->
    <form class="memory-panel__add" @submit.prevent="onAdd">
      <input
        v-model="newContent"
        type="text"
        class="memory-panel__add-input"
        :placeholder="t('memory.addPlaceholder')"
        :aria-label="t('memory.addPlaceholder')"
        :disabled="adding"
      />
      <button
        type="submit"
        class="memory-panel__add-btn"
        :disabled="adding || !newContent.trim()"
      >
        <Lucide name="plus" size="14" color="wp-violet" />
        <span>{{ t('memory.add') }}</span>
      </button>
    </form>

    <!-- Recherche -->
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
      <button
        v-if="isSearchMode"
        type="button"
        class="memory-panel__search-clear"
        @click="onClearSearch"
      >
        {{ t('common.cancel') }}
      </button>
    </div>

    <div v-if="loading" class="memory-panel__empty">{{ t('common.loading') }}</div>

    <div v-else-if="loadError" class="memory-panel__empty memory-panel__empty--error">
      <p>{{ t('memory.loadFailed') }}</p>
      <button type="button" class="memory-panel__retry" @click="reload">
        {{ t('common.retry') }}
      </button>
    </div>

    <div v-else-if="displayItems.length === 0" class="memory-panel__empty">
      <Lucide name="brain" size="24" color="text-faint" />
      <p>{{ activeScope === 'user' ? t('memory.emptyUser') : t('memory.empty') }}</p>
    </div>

    <ul v-else class="memory-panel__list" role="list">
      <li v-for="item in displayItems" :key="item.id" class="memory-panel__item">
        <p class="memory-panel__content">{{ item.content }}</p>
        <div class="memory-panel__meta">
          <span v-if="item.source" class="memory-panel__source">{{ item.source }}</span>
          <span v-if="item.created_at" class="memory-panel__date">{{ formatDate(item.created_at) }}</span>
        </div>
        <button
          v-if="isForgettingble(item)"
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
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useMemory } from '@composables/useMemory';
import type { MemoryItem, MemoryScope } from '@services/aiSidecar';

const props = defineProps<{
  workspaceDataDir: string | null;
}>();

const { t, locale } = useI18n();
const {
  memories,
  searchResults,
  loading,
  searching,
  loadError,
  refresh,
  searchMemory,
  addMemory,
  forgetMemory,
  forgetAll,
} = useMemory();

const activeScope = ref<MemoryScope>('project');
const searchQuery = ref('');
const newContent = ref('');
const forgettingId = ref<string | null>(null);
const forgettingAll = ref(false);
const adding = ref(false);
const forgetAllStep = ref(0);
const isSearchMode = ref(false);

const displayItems = computed<MemoryItem[]>(() => {
  if (isSearchMode.value && searchQuery.value.trim()) {
    return searchResults.value.map((r) => ({
      id: r.memory_id ?? r.id ?? r.document_id ?? '',
      content: r.content,
      source: r.source ?? '',
      created_at: r.created_at ?? '',
      tags: [] as string[],
    }));
  }
  return memories.value;
});

function isForgettingble(item: MemoryItem): boolean {
  // En mode recherche, seuls les souvenirs explicites (kind=memory, avec id
  // memory_*) sont oubliables ; les chunks RAG (document_id) ne le sont pas.
  if (!isSearchMode.value) return true;
  const hit = searchResults.value.find(
    (r) => (r.memory_id ?? r.id) === item.id,
  );
  return hit?.kind === 'memory';
}

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

function reload(): void {
  isSearchMode.value = false;
  searchQuery.value = '';
  void refresh(props.workspaceDataDir, activeScope.value);
}

function onSwitchScope(scope: MemoryScope): void {
  if (scope === activeScope.value) return;
  activeScope.value = scope;
}

async function onSearch(): Promise<void> {
  if (!searchQuery.value.trim()) return;
  isSearchMode.value = true;
  await searchMemory(props.workspaceDataDir, searchQuery.value, activeScope.value);
}

function onClearSearch(): void {
  isSearchMode.value = false;
  searchQuery.value = '';
}

async function onAdd(): Promise<void> {
  const content = newContent.value.trim();
  if (!content) {
    Notify.create({ message: t('memory.addEmpty'), classes: 'bg-warning text-white' });
    return;
  }
  adding.value = true;
  try {
    const entry = await addMemory(props.workspaceDataDir, content, activeScope.value);
    if (entry) {
      newContent.value = '';
      Notify.create({ message: t('memory.addDone'), color: 'positive' });
    } else {
      Notify.create({ message: t('memory.addFailed'), classes: 'bg-danger text-white' });
    }
  } finally {
    adding.value = false;
  }
}

async function onForget(id: string): Promise<void> {
  forgettingId.value = id;
  try {
    await forgetMemory(props.workspaceDataDir, id, activeScope.value);
  } finally {
    forgettingId.value = null;
  }
}

async function onForgetAll(): Promise<void> {
  forgettingAll.value = true;
  try {
    const ok = await forgetAll(props.workspaceDataDir, 'all', activeScope.value);
    if (ok) {
      Notify.create({ message: t('memory.forgetAllDone'), color: 'positive' });
    }
  } finally {
    forgettingAll.value = false;
    forgetAllStep.value = 0;
  }
}

watch(
  () => props.workspaceDataDir,
  () => reload(),
);

watch(activeScope, () => reload());

onMounted(() => {
  void refresh(props.workspaceDataDir, activeScope.value);
});
</script>

<style scoped lang="scss">
.memory-panel {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding: var(--wp-space-3);
  flex: 1;
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

.memory-panel__scopes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--wp-space-2);
}

.memory-panel__scope {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  cursor: pointer;
  text-align: left;

  &--active {
    border-color: var(--wp-violet);
    background: var(--wp-violet-soft);
  }
}

.memory-panel__scope-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.memory-panel__scope-hint {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.memory-panel__add {
  display: flex;
  gap: var(--wp-space-2);
}

.memory-panel__add-input {
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

.memory-panel__add-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-violet) 40%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: var(--wp-violet-soft);
  color: var(--wp-violet);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.memory-panel__search {
  display: flex;
  gap: var(--wp-space-2);
  align-items: center;
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

.memory-panel__search-clear {
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
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
