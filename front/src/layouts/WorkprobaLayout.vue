<template>
  <div class="wp-shell" :data-density="density">
    <WorkprobaTitleBar
      :workspace-title="spaceTitle"
      :active-path="activePath"
      :right-panel-open="rightPanelOpen"
      :capabilities-open="capabilitiesOpen"
      :sidebar-rail="sidebarRail"
      :sidecar-state="sidecarState"
      :side-chat-open="sideChatOpen"
      :has-side-chat="hasSideChat"
      @toggle-right-panel="toggleRightPanel()"
      @toggle-capabilities="toggleCapabilities()"
      @toggle-sidebar="sidebarRail = !sidebarRail"
      @toggle-side-chat="onToggleSideChat"
      @open-shortcuts="shortcutsHelpOpen = true"
    />

    <KeyboardShortcutsHelp v-model:open="shortcutsHelpOpen" />

    <div class="wp-shell__body">
      <SpaceSidebar
        :rail="sidebarRail"
        :streaming="streaming"
        @expand="sidebarRail = false"
      />

      <main class="wp-center">
        <slot><router-view /></slot>
      </main>

      <RightPanel
        :active-path="activePath"
        :workspace-data-dir="activeDataDir"
        :open="rightPanelOpen"
        @toggle="toggleRightPanel()"
      />

      <SideChatPanel />

      <CapabilitiesDrawer />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import WorkprobaTitleBar from '@components/workproba/WorkprobaTitleBar.vue';
import SpaceSidebar from '@components/workproba/SpaceSidebar.vue';
import RightPanel from '@components/workproba/RightPanel.vue';
import SideChatPanel from '@components/workproba/SideChatPanel.vue';
import KeyboardShortcutsHelp from '@components/workproba/KeyboardShortcutsHelp.vue';
import CapabilitiesDrawer from '@components/capabilities/CapabilitiesDrawer.vue';
import { useSpace } from '@composables/useSpace';
import { useSidecarHealth } from '@composables/useSidecarHealth';
import { useAppSettings } from '@composables/useAppSettings';
import { useUiTheme } from '@composables/useUiTheme';
import { PERSONAS_PLUGIN_ID } from '@composables/usePlugins';
import { usePluginSlots } from '@composables/usePluginSlots';
import { useShellSurfaces } from '@composables/useShellSurfaces';

useSidecarHealth();

const { load: loadAppSettings, density, loaded } = useAppSettings();
useUiTheme();
if (!loaded.value) {
  void loadAppSettings();
}

defineProps<{
  streaming?: boolean;
  sidecarState?: 'connected' | 'idle' | 'working' | 'error';
}>();

const { activePath, spaceTitle, activeDataDir } = useSpace();

const sidebarRail = ref(false);
const shortcutsHelpOpen = ref(false);

const {
  rightPanelOpen,
  capabilitiesOpen,
  sideChatOpen,
  toggleRightPanel,
  toggleSideChat,
  openCapabilities,
  closeCapabilities,
  closeSideChat,
  closeRightPanel,
} = useShellSurfaces();

const route = useRoute();

watch(
  () => route?.name,
  (name) => {
    if (name === 'home') {
      closeRightPanel();
    }
  },
  { immediate: true },
);

const { sideChatPluginPanels } = usePluginSlots();

const firstSideChatPluginId = computed(
  () => sideChatPluginPanels.value[0]?.pluginId ?? PERSONAS_PLUGIN_ID,
);

const hasSideChat = computed(() => sideChatPluginPanels.value.length > 0);

function onToggleSideChat(): void {
  toggleSideChat(firstSideChatPluginId.value);
}

function toggleCapabilities(): void {
  if (capabilitiesOpen.value) {
    closeCapabilities();
    return;
  }
  closeSideChat();
  openCapabilities();
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable;
}

function applyResponsive(): void {
  const w = window.innerWidth;
  if (w < 820) {
    sidebarRail.value = true;
    rightPanelOpen.value = false;
    closeCapabilities();
  } else if (w < 1100) {
    rightPanelOpen.value = false;
  }
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    if (shortcutsHelpOpen.value) {
      e.preventDefault();
      shortcutsHelpOpen.value = false;
      return;
    }
    if (capabilitiesOpen.value) {
      e.preventDefault();
      closeCapabilities();
      return;
    }
  }

  if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && !isTypingTarget(e.target)) {
    e.preventDefault();
    shortcutsHelpOpen.value = !shortcutsHelpOpen.value;
    return;
  }

  const mod = e.ctrlKey || e.metaKey;
  const key = e.key.toLowerCase();
  if (mod && key === 'r') {
    e.preventDefault();
    void reloadWebview();
    return;
  }
  if (e.key === 'F5') {
    e.preventDefault();
    void reloadWebview();
    return;
  }
  if (!mod) return;
  if (key === 'b') {
    e.preventDefault();
    toggleRightPanel();
  } else if (key === '\\') {
    e.preventDefault();
    sidebarRail.value = !sidebarRail.value;
  } else if (e.shiftKey && key === 'l' && hasSideChat.value) {
    e.preventDefault();
    onToggleSideChat();
  }
}

async function reloadWebview(): Promise<void> {
  window.location.reload();
}

let resizeTimer: ReturnType<typeof setTimeout> | null = null;
function onResize(): void {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(applyResponsive, 180);
}

onMounted(() => {
  applyResponsive();
  window.addEventListener('keydown', onKeydown);
  window.addEventListener('resize', onResize);
});

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown);
  window.removeEventListener('resize', onResize);
  if (resizeTimer) clearTimeout(resizeTimer);
});
</script>

<style scoped lang="scss">
.wp-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--wp-bg);
}

.wp-shell__body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}

.wp-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--wp-bg);
  overflow: hidden;

  /* Les pages (Home, Chat, Settings) remplissent la zone centrale. */
  > * {
    flex: 1;
    min-height: 0;
    min-width: 0;
    width: 100%;
  }
}
</style>
