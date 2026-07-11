<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="wp-shortcuts"
      @click.self="close"
    >
      <div
        ref="panelEl"
        class="wp-shortcuts__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="wp-shortcuts-title"
        @keydown="onPanelKeydown"
      >
        <header class="wp-shortcuts__header">
          <h2 id="wp-shortcuts-title" class="wp-shortcuts__title">
            {{ t('shell.keyboardTitle') }}
          </h2>
          <button
            ref="closeBtnEl"
            type="button"
            class="wp-shortcuts__close"
            :aria-label="t('shell.keyboardCloseAria')"
            @click="close"
          >
            <Lucide name="x" size="16" color="text-muted" />
          </button>
        </header>

        <dl class="wp-shortcuts__list">
          <div
            v-for="item in shortcuts"
            :key="item.keys"
            class="wp-shortcuts__row"
          >
            <dt class="wp-shortcuts__keys">
              <kbd v-for="(part, index) in item.keyParts" :key="index">{{ part }}</kbd>
            </dt>
            <dd class="wp-shortcuts__desc">{{ item.description }}</dd>
          </div>
        </dl>

        <p class="wp-shortcuts__hint">
          {{ t('shell.keyboardHintPrefix') }}
          <kbd>{{ t('shell.keyboardKeyQuestion') }}</kbd>
          {{ t('shell.keyboardHintOr') }}
          <kbd>{{ t('shell.keyboardKeyEscape') }}</kbd>
          {{ t('shell.keyboardHintSuffix') }}
        </p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

export interface ShortcutItem {
  keys: string;
  keyParts: string[];
  description: string;
}

const { t } = useI18n();

const shortcuts = computed<ShortcutItem[]>(() => [
  {
    keys: 'ctrl-b',
    keyParts: ['Ctrl', 'B'],
    description: t('shell.keyboardToggleFiles'),
  },
  {
    keys: 'ctrl-backslash',
    keyParts: ['Ctrl', '\\'],
    description: t('shell.keyboardToggleSidebar'),
  },
  {
    keys: 'ctrl-p',
    keyParts: ['Ctrl', 'P'],
    description: t('shell.keyboardFilterFiles'),
  },
  {
    keys: 'ctrl-enter',
    keyParts: ['Ctrl', t('shell.keyboardKeyEnter')],
    description: t('shell.keyboardSendMessage'),
  },
  {
    keys: 'enter',
    keyParts: [t('shell.keyboardKeyEnter')],
    description: t('shell.keyboardNewline'),
  },
  {
    keys: 'f5',
    keyParts: ['F5'],
    description: t('shell.keyboardReload'),
  },
  {
    keys: 'question',
    keyParts: [t('shell.keyboardKeyQuestion')],
    description: t('shell.keyboardToggleHelp'),
  },
]);

const open = defineModel<boolean>('open', { default: false });

const panelEl = ref<HTMLElement | null>(null);
const closeBtnEl = ref<HTMLButtonElement | null>(null);

function close(): void {
  open.value = false;
}

function getFocusables(): HTMLElement[] {
  const root = panelEl.value;
  if (!root) return [];
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => !el.hasAttribute('disabled'));
}

function onPanelKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    e.preventDefault();
    close();
    return;
  }
  if (e.key !== 'Tab') return;

  const focusables = getFocusables();
  if (focusables.length === 0) return;

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active = document.activeElement as HTMLElement | null;

  if (e.shiftKey) {
    if (active === first || !panelEl.value?.contains(active)) {
      e.preventDefault();
      last.focus();
    }
    return;
  }

  if (active === last) {
    e.preventDefault();
    first.focus();
  }
}

watch(open, (isOpen) => {
  if (!isOpen) return;
  void nextTick(() => {
    closeBtnEl.value?.focus();
  });
});
</script>

<style scoped lang="scss">
.wp-shortcuts {
  position: fixed;
  inset: 0;
  z-index: 7000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--wp-space-4);
  background: rgba(28, 42, 54, 0.35);
}

.wp-shortcuts__panel {
  width: min(100%, 420px);
  max-height: min(80vh, 520px);
  overflow: auto;
  padding: var(--wp-space-4);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-2);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
}

.wp-shortcuts__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-3);
}

.wp-shortcuts__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-md);
  font-weight: 700;
  line-height: var(--wp-lh-tight);
  color: var(--wp-text);
}

.wp-shortcuts__close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: var(--wp-focus-offset);
  }
}

.wp-shortcuts__list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.wp-shortcuts__row {
  display: grid;
  grid-template-columns: minmax(120px, 38%) 1fr;
  gap: var(--wp-space-2);
  align-items: baseline;
  margin: 0;
}

.wp-shortcuts__keys {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1);
}

.wp-shortcuts__desc {
  margin: 0;
  color: var(--wp-text-muted);
}

.wp-shortcuts__hint {
  margin: var(--wp-space-4) 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.6em;
  padding: 2px var(--wp-space-2);
  border: 1px solid var(--wp-border-strong);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-family: var(--wp-font-mono);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  color: var(--wp-text);
}
</style>
