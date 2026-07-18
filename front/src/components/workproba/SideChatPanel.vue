<template>
  <aside
    v-if="sideChatOpen"
    class="wp-side-chat"
    :aria-label="panelTitle"
  >
    <header class="wp-side-chat__header">
      <h2 class="wp-side-chat__title">{{ panelTitle }}</h2>
      <div v-if="sideChatPluginPanels.length > 1" class="wp-side-chat__selector" role="tablist">
        <button
          v-for="panel in sideChatPluginPanels"
          :key="panel.pluginId"
          type="button"
          role="tab"
          class="wp-side-chat__selector-btn"
          :class="{ 'wp-side-chat__selector-btn--active': panel.pluginId === activeSideChatPluginId }"
          :aria-selected="panel.pluginId === activeSideChatPluginId"
          @click="openSideChat(panel.pluginId)"
        >
          <Lucide :name="panel.icon" size="14" color="text-muted" />
          <span>{{ panel.label }}</span>
        </button>
      </div>
      <button
        type="button"
        class="wp-side-chat__close"
        :aria-label="t('shell.sideChat.closeAria')"
        @click="closeSideChat"
      >
        <Lucide name="x" size="16" color="text-muted" />
      </button>
    </header>

    <div class="wp-side-chat__body">
      <component
        :is="activePanel.component"
        v-if="activePanel"
        :plugin-id="activePanel.pluginId"
        @close="closeSideChat"
      />
      <p v-else class="wp-side-chat__empty">{{ t('shell.sideChat.empty') }}</p>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { usePluginSlots } from '@composables/usePluginSlots';
import { useSideChat } from '@composables/useSideChat';

const { t } = useI18n();
const { sideChatPluginPanels } = usePluginSlots();
const { sideChatOpen, activeSideChatPluginId, openSideChat, closeSideChat } = useSideChat();

const activePanel = computed(() =>
  sideChatPluginPanels.value.find((p) => p.pluginId === activeSideChatPluginId.value) ?? null,
);

const panelTitle = computed(() => activePanel.value?.label ?? t('shell.sideChat.title'));
</script>

<style scoped lang="scss">
.wp-side-chat {
  flex: none;
  width: 380px;
  min-width: 320px;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  border-left: 1px solid var(--wp-border);
  transition: width var(--wp-dur) var(--wp-ease);
}

.wp-side-chat__header {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
  min-height: 40px;
}

.wp-side-chat__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
  white-space: nowrap;
}

.wp-side-chat__selector {
  flex: 1;
  display: flex;
  gap: var(--wp-space-1);
  min-width: 0;
  overflow-x: auto;
}

.wp-side-chat__selector-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: transparent;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: var(--wp-surface-2);
  }

  &--active {
    border-color: var(--wp-accent);
    color: var(--wp-accent);
    font-weight: 600;
  }
}

.wp-side-chat__close {
  flex: none;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  margin-left: auto;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-side-chat__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wp-side-chat__empty {
  margin: auto;
  padding: var(--wp-space-4);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-align: center;
}
</style>
