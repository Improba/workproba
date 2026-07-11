<template>
  <aside
    class="wp-files"
    :class="{
      'wp-files--collapsed': !open,
      'wp-files--embedded': embedded,
    }"
  >
    <div v-if="open" class="wp-files__inner">
      <div class="wp-files__filter">
        <Lucide name="search" size="14" color="text-faint" />
        <input
          ref="filterInputEl"
          v-model="filterModel"
          type="text"
          class="wp-files__filter-input"
          :placeholder="t('shell.filterFiles')"
          @keydown.esc="filterModel = ''"
        />
        <span v-if="filterModel" class="wp-files__count">{{ matchCount }}</span>
      </div>

      <div v-if="!activePath" class="wp-files__empty">
        <Lucide name="folder-open" size="26" color="text-faint" />
        <p>{{ t('shell.fileTreeEmpty') }}</p>
      </div>

      <div v-else-if="treeError" class="wp-files__empty wp-files__empty--error">
        <Lucide name="alert-triangle" size="22" color="danger" />
        <p class="wp-files__error-msg">{{ errorMessage }}</p>
        <button type="button" class="wp-files__retry" @click="retry">
          <Lucide name="rotate-cw" size="14" color="text" />
          <span>{{ t('common.retry') }}</span>
        </button>
      </div>

      <div v-else-if="flatList.length === 0 && !treeIndexing" class="wp-files__empty">
        <Lucide name="folder" size="26" color="text-faint" />
        <p>{{ t('shell.folderEmpty') }}</p>
      </div>

      <RecycleScroller
        v-else
        class="wp-files__tree"
        role="tree"
        :aria-label="t('shell.fileTreeLabel')"
        :items="flatList"
        :item-size="rowHeight"
        key-field="relativePath"
        v-slot="{ item }"
      >
        <div
          class="wp-node"
          :class="{
            'wp-node--dir': item.isDir,
            'wp-node--touched': item.sessionState !== 'idle',
            'wp-node--match': filterModel,
            'wp-node--selected': !item.isDir && item.relativePath === selectedPath,
          }"
          role="treeitem"
          :aria-expanded="item.isDir ? item.expanded : undefined"
          :aria-level="item.depth + 1"
          :aria-label="item.name"
          tabindex="0"
          :style="{ paddingLeft: 8 + item.depth * 16 + 'px' }"
          :title="item.relativePath"
          @click="onActivate(item)"
          @dblclick="onOpen(item)"
          @keydown="onKeydown($event, item)"
          @contextmenu.prevent="onContextMenu($event, item)"
        >
          <span
            v-if="item.isDir"
            class="wp-node__chevron"
            :class="{ 'wp-node__chevron--open': item.expanded }"
          >
            <Lucide name="chevron-right" size="14" color="text-muted" />
          </span>
          <span v-else class="wp-node__chevron-spacer" />

          <Lucide :name="iconFor(item)" size="15" :color="colorFor(item)" />

          <span class="wp-node__label">{{ item.name }}</span>
          <span v-if="filterModel && !item.isDir" class="wp-node__parent">
            {{ parentPath(item.relativePath) }}
          </span>

          <span
            v-if="item.sessionState !== 'idle'"
            class="wp-node__dot"
            :title="item.sessionState === 'created' ? t('shell.fileCreatedInSession') : t('shell.fileModifiedInSession')"
          />
        </div>
      </RecycleScroller>

      <Teleport to="body">
        <div
          v-if="contextMenu.open"
          class="wp-contextmenu"
          :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
          @click.stop
          @contextmenu.prevent
        >
          <button type="button" class="wp-contextmenu__item" @click="onContextMenuOpen">
            <Lucide name="external-link" size="15" color="text" />
            <span>{{ t('common.openInOs') }}</span>
          </button>
          <button type="button" class="wp-contextmenu__item" @click="onContextMenuReveal">
            <Lucide name="folder-search" size="15" color="text" />
            <span>{{ t('shell.revealInManager') }}</span>
          </button>
          <button
            v-if="showPublish && contextMenu.node && !contextMenu.node.isDir"
            type="button"
            class="wp-contextmenu__item"
            @click="onContextMenuPublish"
          >
            <Lucide name="upload" size="15" color="text" />
            <span>{{ t('plugin.workproba.projet.publishAction') }}</span>
          </button>
        </div>
      </Teleport>

      <div v-if="treeIndexing && !treeError" class="wp-files__indexing">
        <span class="wp-files__indexing-bar" />
        <span>{{ t('shell.fileIndexing') }}</span>
      </div>

      <!-- Mémoire RAG (power user) -->
      <button
        type="button"
        class="wp-files__rag"
        :class="`wp-files__rag--${ragStatus}`"
        :title="ragLabel"
        @click="onShowRagDetail"
      >
        <span class="wp-files__rag-dot" />
        <span class="wp-files__rag-text">{{ ragLabel }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RecycleScroller } from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useFileTree, type FileNode } from '@composables/useFileTree';
import { useRagIndex } from '@composables/useRagIndex';
import { ragStatusLabel, type RagStatus } from '@services/aiSidecar';
import { openLocalFile, revealInOs } from '@composables/useDesktop';

const props = defineProps<{
  activePath: string | null;
  open: boolean;
  embedded?: boolean;
  selectedPath?: string | null;
  showPublish?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle'): void;
  (e: 'select-file', relativePath: string): void;
  (e: 'publish-file', relativePath: string): void;
}>();

const { t, locale } = useI18n();

const tree = useFileTree(() => props.activePath);
const filterInputEl = ref<HTMLInputElement | null>(null);

const { status: ragStatus, report: ragReport, lastRunAt } = useRagIndex();
const ragLabel = computed(() => ragStatusLabel(ragStatus.value as RagStatus, ragReport.value));

function formatRelativeRun(): string {
  const runAt = lastRunAt.value;
  if (!runAt) return '';
  const diff = Date.now() - runAt;
  if (diff < 60000) return t('common.justNow');
  if (diff < 3600000) return t('common.agoMinutes', { count: Math.floor(diff / 60000) });
  if (diff < 86400000) return t('common.agoHours', { count: Math.floor(diff / 3600000) });
  return new Date(runAt).toLocaleDateString(locale.value, { day: '2-digit', month: 'short' });
}

function onShowRagDetail(): void {
  const r = ragReport.value;

  if (ragStatus.value === 'disabled' || (r && !r.enabled)) {
    Notify.create({
      message: t('shell.memoryDisabled'),
      caption: t('shell.memoryDisabledCaption'),
      color: 'dark',
      timeout: 5000,
      multiLine: true,
    });
    return;
  }

  if (ragStatus.value === 'error') {
    Notify.create({
      message: t('shell.memoryAnalysisFailed'),
      caption: t('shell.memoryAnalysisFailedCaption'),
      color: 'negative',
      timeout: 5000,
      multiLine: true,
    });
    return;
  }

  if (!r) {
    Notify.create({ message: t('shell.memoryAnalysisPending'), color: 'dark' });
    return;
  }

  const added = r.indexed;
  const upToDate = r.unchanged;
  const lines: string[] = [];

  if (added > 0) {
    lines.push(t('shell.memoryFilesAdded', added, { count: added }));
  }
  if (upToDate > 0) {
    lines.push(
      added > 0
        ? t('shell.memoryKnownUnchanged', upToDate, { count: upToDate })
        : t('shell.memoryFilesUpToDate', upToDate, { count: upToDate }),
    );
  }
  if (added === 0 && upToDate === 0) {
    lines.push(t('shell.memoryNoDocuments'));
  }
  if (r.skipped > 0) {
    lines.push(t('shell.memoryFilesSkipped', r.skipped, { count: r.skipped }));
  }
  if (r.errors > 0) {
    lines.push(t('shell.memoryFilesError', r.errors, { count: r.errors }));
  }
  if (r.truncated) {
    lines.push(t('shell.memoryTruncated'));
  }

  const relative = formatRelativeRun();
  Notify.create({
    message: `${t('shell.ragDetailTitle')}${relative ? ` · ${relative}` : ''}`,
    caption: lines.join(' '),
    color: 'dark',
    timeout: 6000,
    multiLine: true,
  });
}

const contextMenu = ref<{ open: boolean; x: number; y: number; node: FileNode | null }>({
  open: false,
  x: 0,
  y: 0,
  node: null,
});

const filterModel = computed({
  get: () => tree.filter.value,
  set: (v: string) => {
    tree.filter.value = v;
  },
});

const errorMessage = computed(() => {
  const raw = tree.error.value;
  if (raw === null || raw === undefined) return '';
  const s = String(raw);
  return s && s.trim() ? s : t('shell.indexErrorFallback');
});

watch(
  () => tree.error.value,
  (err) => {
    if (err) {
      console.error('[FileExplorer] tree.error =', JSON.stringify(err), err);
    }
  },
);

const flatList = computed(() => tree.flatList.value);
const matchCount = computed(() => tree.matchCount.value);
const treeError = computed(() => tree.error.value);
const treeIndexing = computed(() => tree.indexing.value);
const rowHeight = tree.rowHeight;

watch(
  () => props.activePath,
  (path) => {
    tree.reset();
    if (path) void tree.loadRoot();
  },
  { immediate: false },
);

onMounted(() => {
  if (props.activePath) void tree.loadRoot();
  window.addEventListener('click', onGlobalClick);
  window.addEventListener('resize', closeContextMenu);
  window.addEventListener('keydown', onGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener('click', onGlobalClick);
  window.removeEventListener('resize', closeContextMenu);
  window.removeEventListener('keydown', onGlobalKeydown);
});

function iconFor(node: FileNode): string {
  if (node.isDir) return node.expanded ? 'folder-open' : 'folder';
  const map: Record<string, string> = {
    spreadsheet: 'file-spreadsheet',
    document: 'file-text',
    presentation: 'file-text',
    pdf: 'file-text',
    image: 'file-image',
    text: 'file-text',
    code: 'file-code',
    archive: 'file-archive',
    file: 'file',
  };
  return map[node.kind] ?? 'file';
}

function colorFor(node: FileNode): string {
  if (node.isDir) return 'accent';
  if (node.kind === 'code') return 'wp-violet';
  if (node.kind === 'image') return 'warning';
  return 'text-muted';
}

function parentPath(relativePath: string): string {
  const idx = relativePath.lastIndexOf('/');
  return idx >= 0 ? relativePath.slice(0, idx) : '';
}

async function onActivate(node: FileNode): Promise<void> {
  if (node.isDir) {
    await tree.toggle(node);
    return;
  }
  emit('select-file', node.relativePath);
}

async function onOpen(node: FileNode): Promise<void> {
  if (node.isDir) return;
  try {
    await openLocalFile(node.relativePath, props.activePath);
  } catch {
    Notify.create({ message: t('shell.openFileFailed', { name: node.name }), classes: 'bg-danger text-white' });
  }
}

async function onReveal(node: FileNode): Promise<void> {
  if (!props.activePath) return;
  const full = `${props.activePath.replace(/\/$/, '')}/${node.relativePath}`;
  try {
    await revealInOs(full);
  } catch {
    Notify.create({ message: t('shell.revealFailed'), classes: 'bg-danger text-white' });
  }
}

function onContextMenu(e: MouseEvent, node: FileNode): void {
  contextMenu.value = { open: true, x: e.clientX, y: e.clientY, node };
}

function closeContextMenu(): void {
  if (contextMenu.value.open) {
    contextMenu.value = { ...contextMenu.value, open: false, node: null };
  }
}

function onContextMenuOpen(): Promise<void> {
  const node = contextMenu.value.node;
  closeContextMenu();
  return node ? onOpen(node) : Promise.resolve();
}

function onContextMenuReveal(): Promise<void> {
  const node = contextMenu.value.node;
  closeContextMenu();
  return node ? onReveal(node) : Promise.resolve();
}

function onContextMenuPublish(): void {
  const node = contextMenu.value.node;
  closeContextMenu();
  if (node && !node.isDir) {
    emit('publish-file', node.relativePath);
  }
}

async function onKeydown(e: KeyboardEvent, node: FileNode): Promise<void> {
  switch (e.key) {
    case 'Enter':
      e.preventDefault();
      if (node.isDir) {
        await tree.toggle(node);
      } else {
        await onOpen(node);
      }
      break;
    case 'ArrowRight':
      if (node.isDir && !node.expanded) {
        e.preventDefault();
        await tree.toggle(node);
      }
      break;
    case 'ArrowLeft':
      if (node.isDir && node.expanded) {
        e.preventDefault();
        node.expanded = false;
      }
      break;
  }
}

function onGlobalClick(): void {
  closeContextMenu();
}

function onGlobalKeydown(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p') {
    e.preventDefault();
    filterInputEl.value?.focus();
  }
}

function retry(): void {
  tree.reset();
  if (props.activePath) void tree.loadRoot();
}

defineExpose({
  refresh: () => {
    tree.reset();
    if (props.activePath) void tree.loadRoot();
  },
  reveal: onReveal,
  markTouched: tree.markSessionTouched,
  clearMarks: tree.clearSessionMarks,
});
</script>

<style scoped lang="scss">
.wp-files {
  flex: none;
  width: 320px;
  min-width: 240px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  border-left: 1px solid var(--wp-border);
  transition: width var(--wp-dur) var(--wp-ease);
}

.wp-files--collapsed {
  width: 0;
  min-width: 0;
  border-left: none;
  overflow: hidden;
}

.wp-files__inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 320px;
}

.wp-files__filter {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
}

.wp-files__filter-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);
}

.wp-files__filter-input::placeholder {
  color: var(--wp-text-faint);
}

.wp-files__count {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  background: var(--wp-surface-2);
  border-radius: var(--wp-r-pill);
  padding: 1px var(--wp-space-2);
}

.wp-files__tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.wp-files__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-6);
  text-align: center;
  color: var(--wp-text-faint);

  p {
    margin: 0;
    font-size: var(--wp-fs-sm);
    line-height: var(--wp-lh-normal);
  }
}

.wp-files__empty--error {
  align-items: stretch;
  text-align: left;
  gap: 12px;

  > :first-child {
    align-self: center;
  }
}

.wp-files__error-msg {
  color: var(--wp-danger, #d23a3a);
  font-family: var(--wp-font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  padding: 8px 10px;
}

.wp-files__retry {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-1);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-ui);
  cursor: pointer;
  transition: background 120ms var(--wp-ease), border-color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
  }
}

.wp-files--embedded {
  width: 100%;
  max-width: none;
  min-width: 0;
  border-left: none;
}

.wp-files--embedded .wp-files__inner {
  width: 100%;
}

.wp-node--selected {
  background: var(--wp-accent-soft);
}

.wp-node {
  height: 26px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding-right: var(--wp-space-3);
  cursor: default;
  border-radius: 0;
  transition: background 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }

  &:focus-visible {
    background: var(--wp-accent-soft);
  }
}

.wp-node__chevron {
  display: inline-flex;
  transition: transform 150ms var(--wp-ease);

  &--open {
    transform: rotate(90deg);
  }
}

.wp-node__chevron-spacer {
  width: 14px;
  flex: none;
}

.wp-node__label {
  flex: 1;
  min-width: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-node--dir .wp-node__label {
  font-weight: 600;
}

.wp-node__parent {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 40%;
}

.wp-node__dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent);
}

.wp-files__indexing {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  border-top: 1px solid var(--wp-border);
}

.wp-files__indexing-bar {
  width: 32px;
  height: 3px;
  border-radius: var(--wp-r-pill);
  background: linear-gradient(90deg, var(--wp-accent) 0%, var(--wp-accent-soft) 100%);
  animation: wp-breathe 1.4s ease-in-out infinite;
}

/* Mémoire RAG (power user) */
.wp-files__rag {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  width: 100%;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-top: 1px solid var(--wp-border);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  text-align: left;
  transition: background 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-files__rag-text {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-files__rag-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);

  .wp-files__rag--indexing & {
    background: var(--wp-accent);
    animation: wp-breathe 1.4s ease-in-out infinite;
  }
  .wp-files__rag--done & {
    background: var(--wp-success);
  }
  .wp-files__rag--error & {
    background: var(--wp-danger);
  }
  .wp-files__rag--disabled & {
    background: var(--wp-text-faint);
  }
}

/* Menu contextuel (téléporté au body) */
.wp-contextmenu {
  position: fixed;
  z-index: 1000;
  min-width: 200px;
  padding: 6px;
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
  animation: wp-fade-in 120ms var(--wp-ease) both;
}

.wp-contextmenu__item {
  display: flex;
  align-items: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  text-align: left;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);

  &:hover {
    background: var(--wp-accent-soft);
  }
}
</style>
