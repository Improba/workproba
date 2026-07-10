<template>
  <div class="wp-titlebar" data-tauri-drag-region>
    <div class="wp-titlebar__brand" data-tauri-drag-region>
      <span class="wp-titlebar__mark">Workproba</span>
      <span v-if="workspaceTitle" class="wp-titlebar__sep">·</span>
      <span v-if="workspaceTitle" class="wp-titlebar__workspace" :title="activePath ?? ''">
        {{ workspaceTitle }}
      </span>
    </div>

    <div class="wp-titlebar__right">
      <button
        type="button"
        class="wp-titlebar__chip"
        :class="`wp-titlebar__chip--${sidecarState}`"
        :aria-label="`Provider ${providerLabel} — ${sidecarLabel}`"
        @click="sidecarDialogOpen = true"
      >
        <span class="wp-titlebar__chip-dot" />
        <span class="wp-titlebar__chip-label">{{ providerLabel }}</span>
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ providerLabel }} · {{ sidecarLabel }}
        </q-tooltip>
      </button>

      <q-dialog v-model="sidecarDialogOpen">
        <div class="wp-sidecar-dialog">
          <header class="wp-sidecar-dialog__head">
            <span class="wp-sidecar-dialog__title">État du service IA</span>
            <button
              type="button"
              class="wp-sidecar-dialog__close"
              aria-label="Fermer"
              @click="sidecarDialogOpen = false"
            >
              <Lucide name="x" size="16" color="text-muted" />
            </button>
          </header>

          <dl class="wp-sidecar-dialog__list">
            <div class="wp-sidecar-dialog__row">
              <dt>Sidecar</dt>
              <dd>
                <span class="wp-sidecar-dialog__dot" :class="`wp-sidecar-dialog__dot--${sidecarState}`" />
                {{ sidecarLabel }}
              </dd>
            </div>
            <div class="wp-sidecar-dialog__row">
              <dt>Modèle de chat</dt>
              <dd>{{ chatProviderLabel }}</dd>
            </div>
            <div class="wp-sidecar-dialog__row">
              <dt>Embeddings</dt>
              <dd>{{ embeddingProviderLabel }}</dd>
            </div>
          </dl>

          <footer class="wp-sidecar-dialog__foot">
            <button type="button" class="wp-sidecar-dialog__link" @click="onOpenSettings">
              <Lucide name="settings-2" size="15" color="accent" />
              <span>Ouvrir les paramètres</span>
            </button>
          </footer>
        </div>
      </q-dialog>
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
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import ThemeToggler from '@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';

const props = defineProps<{
  workspaceTitle: string | null;
  activePath: string | null;
  filesOpen: boolean;
  sidebarRail: boolean;
  sidecarState?: 'connected' | 'idle' | 'working' | 'error';
}>();

defineEmits<{
  (e: 'toggle-files'): void;
  (e: 'toggle-sidebar'): void;
  (e: 'open-shortcuts'): void;
}>();

const { activeChatProvider, activeEmbeddingProvider } = useAppSettings();
const router = useRouter();

const sidecarDialogOpen = ref(false);

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

const sidecarState = computed(() => props.sidecarState ?? 'idle');
const sidecarLabel = computed(() => {
  switch (sidecarState.value) {
    case 'working':
      return 'Agent au travail';
    case 'error':
      return 'Sidecar injoignable';
    case 'connected':
      return 'Connecté';
    default:
      return 'En attente';
  }
});

function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function providerDisplay(entry: typeof activeChatProvider.value): string {
  if (!entry) return 'Aucun';
  return entry.label?.trim() || capitalize(entry.provider);
}

const providerLabel = computed(() => providerDisplay(activeChatProvider.value));

const chatProviderLabel = computed(() => {
  const entry = activeChatProvider.value;
  if (!entry) return 'Aucun modèle configuré';
  return `${providerDisplay(entry)} · ${entry.model || '—'}`;
});

const embeddingProviderLabel = computed(() => {
  const entry = activeEmbeddingProvider.value;
  if (!entry || !entry.embeddingModel) return 'Aucun modèle d’embedding';
  return `${providerDisplay(entry)} · ${entry.embeddingModel}`;
});

function onOpenSettings(): void {
  sidecarDialogOpen.value = false;
  void router.push({ name: 'settings_models' });
}
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

.wp-titlebar__right {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
  flex: none;
}

.wp-titlebar__chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  height: 26px;
  padding: 0 var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  cursor: pointer;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  transition: background 120ms var(--wp-ease), border-color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface);
    border-color: var(--wp-accent);
  }
}

.wp-titlebar__chip-label {
  max-width: 140px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-titlebar__chip-dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);

  .wp-titlebar__chip--connected & {
    background: var(--wp-success);
  }
  .wp-titlebar__chip--working & {
    background: var(--wp-accent);
    animation: wp-breathe 1.4s ease-in-out infinite;
  }
  .wp-titlebar__chip--error & {
    background: var(--wp-danger);
  }
}

.wp-sidecar-dialog {
  width: 360px;
  max-width: 90vw;
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  padding: var(--wp-space-4);
}

.wp-sidecar-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--wp-space-3);
}

.wp-sidecar-dialog__title {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-base);
  color: var(--wp-text);
}

.wp-sidecar-dialog__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-sidecar-dialog__list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.wp-sidecar-dialog__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-3);
  padding: var(--wp-space-2) 0;
  border-bottom: 1px solid var(--wp-border);

  &:last-child {
    border-bottom: none;
  }

  dt {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  dd {
    margin: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--wp-space-2);
    font-size: var(--wp-fs-sm);
    color: var(--wp-text);
    text-align: right;
  }
}

.wp-sidecar-dialog__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);

  &--connected {
    background: var(--wp-success);
  }
  &--working {
    background: var(--wp-accent);
    animation: wp-breathe 1.4s ease-in-out infinite;
  }
  &--error {
    background: var(--wp-danger);
  }
}

.wp-sidecar-dialog__foot {
  margin-top: var(--wp-space-3);
  display: flex;
  justify-content: flex-end;
}

.wp-sidecar-dialog__link {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  transition: background 120ms var(--wp-ease), border-color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
  }
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
