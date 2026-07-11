<template>
  <div class="wp-shell" :data-density="density">
    <WorkprobaTitleBar
      :workspace-title="workspaceTitle"
      :active-path="activePath"
      :files-open="filesOpen"
      :sidebar-rail="sidebarRail"
      :sidecar-state="sidecarState"
      :side-chat-open="sideChatOpen"
      :has-side-chat="hasSideChat"
      @toggle-files="filesOpen = !filesOpen"
      @toggle-sidebar="sidebarRail = !sidebarRail"
      @toggle-side-chat="toggleSideChat"
      @open-shortcuts="shortcutsHelpOpen = true"
    />

    <KeyboardShortcutsHelp v-model:open="shortcutsHelpOpen" />

    <div class="wp-shell__body">
      <WorkspaceSidebar
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
        :open="filesOpen"
        @toggle="filesOpen = !filesOpen"
      />

      <SideChatPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import WorkprobaTitleBar from '@components/workproba/WorkprobaTitleBar.vue';
import WorkspaceSidebar from '@components/workproba/WorkspaceSidebar.vue';
import RightPanel from '@components/workproba/RightPanel.vue';
import SideChatPanel from '@components/workproba/SideChatPanel.vue';
import KeyboardShortcutsHelp from '@components/workproba/KeyboardShortcutsHelp.vue';
import { useProject } from '@composables/useProject';
import { useSidecarHealth } from '@composables/useSidecarHealth';
import { useAppSettings } from '@composables/useAppSettings';
import { PERSONAS_PLUGIN_ID } from '@composables/usePlugins';
import { usePluginSlots } from '@composables/usePluginSlots';
import { useSideChat } from '@composables/useSideChat';

useSidecarHealth();

const { load: loadAppSettings, density } = useAppSettings();
void loadAppSettings();

defineProps<{
  streaming?: boolean;
  sidecarState?: 'connected' | 'idle' | 'working' | 'error';
}>();

const { activePath, workspaceTitle, activeDataDir } = useProject();

const sidebarRail = ref(false);
const filesOpen = ref(true);
const shortcutsHelpOpen = ref(false);

const { sideChatOpen, openSideChat, closeSideChat, hasSideChat } = useSideChat();
const { sideChatPluginPanels } = usePluginSlots();

const firstSideChatPluginId = computed(
  () => sideChatPluginPanels.value[0]?.pluginId ?? PERSONAS_PLUGIN_ID,
);

function toggleSideChat(): void {
  if (sideChatOpen.value) {
    closeSideChat();
    return;
  }
  openSideChat(firstSideChatPluginId.value);
  if (window.innerWidth < 1100) {
    filesOpen.value = false;
  }
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
    filesOpen.value = false;
  } else if (w < 1100) {
    filesOpen.value = false;
  }
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && shortcutsHelpOpen.value) {
    e.preventDefault();
    shortcutsHelpOpen.value = false;
    return;
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
    filesOpen.value = !filesOpen.value;
  } else if (key === '\\') {
    e.preventDefault();
    sidebarRail.value = !sidebarRail.value;
  } else if (e.shiftKey && key === 'l' && hasSideChat.value) {
    e.preventDefault();
    toggleSideChat();
  }
}

async function reloadWebview(): Promise<void> {
  // Tauri v2 n'expose plus de méthode `reload` sur l'API Window/Webview
  // (ni dans les types, ni au runtime). `window.location.reload()` recharge
  // le webview courant, qu'on soit en app desktop ou en navigateur web.
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
}
</style>
