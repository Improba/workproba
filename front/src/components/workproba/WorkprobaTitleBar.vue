<template>
  <div class="wp-titlebar" data-tauri-drag-region>
    <div class="wp-titlebar__brand" data-tauri-drag-region>
      <span class="wp-titlebar__mark">Workproba</span>
      <span v-if="workspaceTitle" class="wp-titlebar__sep">·</span>
      <span v-if="workspaceTitle" class="wp-titlebar__workspace" :title="activePath ?? ''">
        {{ workspaceTitle }}
      </span>
    </div>

    <span
      class="wp-titlebar__sovereignty"
      :title="sovereigntyTooltip"
      :aria-label="sovereigntyTooltip"
    >
      <Lucide :name="isLocalChatProvider ? 'shield-check' : 'cloud'" size="14" color="text-muted" />
      <span class="wp-titlebar__sovereignty-text">{{ sovereigntyLabel }}</span>
    </span>

    <div class="wp-titlebar__right">
      <button
        type="button"
        class="wp-titlebar__btn"
        :class="{ 'wp-titlebar__btn--active': filesOpen }"
        :aria-label="filesAriaLabel"
        :title="filesAriaLabel"
        @click="$emit('toggle-files')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ filesAriaLabel }}
        </q-tooltip>
        <Lucide
          :name="filesOpen ? 'panel-right-close' : 'panel-right-open'"
          size="16"
          color="text-muted"
        />
        <span class="wp-sr-only">{{ filesAriaLabel }}</span>
      </button>
      <button
        type="button"
        class="wp-titlebar__btn"
        :class="{ 'wp-titlebar__btn--active': !sidebarRail }"
        :aria-label="sidebarAriaLabel"
        :title="sidebarAriaLabel"
        @click="$emit('toggle-sidebar')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ sidebarAriaLabel }}
        </q-tooltip>
        <Lucide
          :name="sidebarRail ? 'panel-left-open' : 'panel-left-close'"
          size="16"
          color="text-muted"
        />
        <span class="wp-sr-only">{{ sidebarAriaLabel }}</span>
      </button>
      <button
        type="button"
        class="wp-titlebar__btn"
        aria-label="Raccourcis clavier"
        title="Raccourcis clavier (?)"
        @click="$emit('open-shortcuts')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          Raccourcis clavier (?)
        </q-tooltip>
        <Lucide name="keyboard" size="16" color="text-muted" />
        <span class="wp-sr-only">Raccourcis clavier</span>
      </button>
      <ThemeToggler />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ThemeToggler from '@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';

const props = defineProps<{
  workspaceTitle: string | null;
  activePath: string | null;
  filesOpen: boolean;
  sidebarRail: boolean;
}>();

defineEmits<{
  (e: 'toggle-files'): void;
  (e: 'toggle-sidebar'): void;
  (e: 'open-shortcuts'): void;
}>();

const { isLocalChatProvider } = useAppSettings();

const filesAriaLabel = computed(() =>
  props.filesOpen
    ? "Masquer l'explorateur de fichiers (Ctrl+B)"
    : "Afficher l'explorateur de fichiers (Ctrl+B)",
);

const sidebarAriaLabel = computed(() =>
  props.sidebarRail
    ? 'Afficher la barre latérale (Ctrl+\\)'
    : 'Réduire la barre latérale (Ctrl+\\)',
);

const sovereigntyLabel = computed(() =>
  isLocalChatProvider.value
    ? 'Local · documents non envoyés'
    : 'Cloud tiers',
);

const sovereigntyTooltip = computed(() =>
  isLocalChatProvider.value
    ? 'Vos documents restent sur votre machine'
    : 'Les requêtes IA passent par un service cloud tiers',
);
</script>

<style scoped lang="scss">
.wp-titlebar {
  height: 40px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  padding: 0 var(--wp-space-2) 0 var(--wp-space-3);
  background: var(--wp-surface);
  border-bottom: 1px solid var(--wp-border);
  user-select: none;
  -webkit-user-select: none;
}

.wp-titlebar__brand {
  display: flex;
  align-items: baseline;
  gap: var(--wp-space-2);
  min-width: 0;
  flex: 1;
}

.wp-titlebar__mark {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-tight);
  color: var(--wp-primary);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.wp-titlebar__sep {
  color: var(--wp-text-faint);
  font-weight: 400;
}

.wp-titlebar__workspace {
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 36vw;
}

.wp-titlebar__sovereignty {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1) var(--wp-space-2);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  color: var(--wp-text-muted);
  white-space: nowrap;
}

.wp-titlebar__sovereignty-text {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-titlebar__right {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
  flex: none;
}

.wp-titlebar__btn {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  color: var(--wp-text-muted);
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &--active {
    color: var(--wp-accent);
  }
}
</style>
