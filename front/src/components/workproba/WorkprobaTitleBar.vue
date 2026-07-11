<template>
  <div class="wp-titlebar" data-tauri-drag-region>
    <div class="wp-titlebar__brand" data-tauri-drag-region>
      <span class="wp-titlebar__mark">{{ t('shell.titlebarBrand') }}</span>
      <span v-if="workspaceTitle" class="wp-titlebar__sep">{{ t('shell.titlebarSep') }}</span>
      <span v-if="workspaceTitle" class="wp-titlebar__workspace" :title="activePath ?? ''">
        {{ workspaceTitle }}
      </span>
      <template v-if="displayName">
        <span class="wp-titlebar__sep">{{ t('shell.titlebarSep') }}</span>
        <span class="wp-titlebar__user" :title="userTitle">
          {{ displayName }}<template v-if="displayOrganisation"><span class="wp-titlebar__sep">{{ t('shell.titlebarSep') }}</span>{{ displayOrganisation }}</template>
        </span>
      </template>
    </div>

    <div class="wp-titlebar__right">
      <button
        type="button"
        class="wp-titlebar__chip"
        :class="`wp-titlebar__chip--${sidecarState}`"
        :aria-label="providerAriaLabel"
        @click="sidecarDialogOpen = true"
      >
        <span class="wp-titlebar__chip-dot" />
        <span class="wp-titlebar__chip-label">{{ providerLabel }}</span>
        <span v-if="capabilityChips.length" class="wp-titlebar__chip-caps">
          <span v-for="cap in capabilityChips" :key="cap" class="wp-titlebar__cap">{{ cap }}</span>
        </span>
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ providerTooltip }}
        </q-tooltip>
      </button>

      <q-dialog v-model="sidecarDialogOpen">
        <div class="wp-sidecar-dialog">
          <header class="wp-sidecar-dialog__head">
            <span class="wp-sidecar-dialog__title">{{ t('shell.titlebarSidecarDialogTitle') }}</span>
            <button
              type="button"
              class="wp-sidecar-dialog__close"
              :aria-label="t('common.close')"
              @click="sidecarDialogOpen = false"
            >
              <Lucide name="x" size="16" color="text-muted" />
            </button>
          </header>

          <dl class="wp-sidecar-dialog__list">
            <div class="wp-sidecar-dialog__row">
              <dt>{{ t('shell.titlebarSidecarLabel') }}</dt>
              <dd>
                <span class="wp-sidecar-dialog__dot" :class="`wp-sidecar-dialog__dot--${sidecarState}`" />
                {{ sidecarLabel }}
              </dd>
            </div>
            <div class="wp-sidecar-dialog__row">
              <dt>{{ t('shell.titlebarChatModel') }}</dt>
              <dd>{{ chatProviderLabel }}</dd>
            </div>
            <div v-if="activeSetCapabilities.length" class="wp-sidecar-dialog__row wp-sidecar-dialog__row--caps">
              <dt>{{ t('settings.lockedCapabilities') }}</dt>
              <dd>
                <span v-for="cap in activeSetCapabilities" :key="cap" class="wp-sidecar-dialog__cap">{{ cap }}</span>
              </dd>
            </div>
            <div class="wp-sidecar-dialog__row">
              <dt>{{ t('shell.titlebarEmbeddings') }}</dt>
              <dd>{{ embeddingProviderLabel }}</dd>
            </div>
          </dl>

          <footer class="wp-sidecar-dialog__foot">
            <button type="button" class="wp-sidecar-dialog__link" @click="onOpenSettings">
              <Lucide name="settings-2" size="15" color="accent" />
              <span>{{ t('shell.titlebarOpenSettings') }}</span>
            </button>
          </footer>
        </div>
      </q-dialog>
      <button
        v-if="hasSideChat"
        type="button"
        class="wp-titlebar__btn"
        :class="{ 'wp-titlebar__btn--active': sideChatOpen }"
        :aria-label="t('shell.sideChat.toggle')"
        :title="t('shell.sideChat.toggle')"
        @click="$emit('toggle-side-chat')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ t('shell.sideChat.toggle') }}
        </q-tooltip>
        <Lucide name="message-square" size="16" color="text-muted" />
        <span class="wp-sr-only">{{ t('shell.sideChat.toggle') }}</span>
      </button>
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
        :aria-label="t('shell.titlebarShortcuts')"
        :title="t('shell.titlebarShortcutsTooltip')"
        @click="$emit('open-shortcuts')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ t('shell.titlebarShortcutsTooltip') }}
        </q-tooltip>
        <Lucide name="keyboard" size="16" color="text-muted" />
        <span class="wp-sr-only">{{ t('shell.titlebarShortcuts') }}</span>
      </button>
      <ThemeToggler />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import ThemeToggler from '@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useUserProfile } from '@composables/useUserProfile';
import { capabilityLabels, localizedSetName } from '@utils/providerSets';

const props = defineProps<{
  workspaceTitle: string | null;
  activePath: string | null;
  filesOpen: boolean;
  sidebarRail: boolean;
  sideChatOpen?: boolean;
  hasSideChat?: boolean;
  sidecarState?: 'connected' | 'idle' | 'working' | 'error';
}>();

defineEmits<{
  (e: 'toggle-files'): void;
  (e: 'toggle-sidebar'): void;
  (e: 'toggle-side-chat'): void;
  (e: 'open-shortcuts'): void;
}>();

const { activeSet, activeChatProvider, activeEmbeddingProvider, settingsMode, settingsLocked } = useAppSettings();
const { displayName, displayOrganisation } = useUserProfile();
const router = useRouter();
const { t } = useI18n();

const userTitle = computed(() => {
  if (displayOrganisation.value) {
    return `${displayName.value} — ${displayOrganisation.value}`;
  }
  return displayName.value;
});

const sidecarDialogOpen = ref(false);

const filesAriaLabel = computed(() =>
  props.filesOpen
    ? t('shell.titlebarHideFiles')
    : t('shell.titlebarShowFiles'),
);

const sidebarAriaLabel = computed(() =>
  props.sidebarRail
    ? t('shell.titlebarShowSidebar')
    : t('shell.titlebarHideSidebar'),
);

const sidecarState = computed(() => props.sidecarState ?? 'idle');
const sidecarLabel = computed(() => {
  switch (sidecarState.value) {
    case 'working':
      return t('shell.titlebarSidecarWorking');
    case 'error':
      return t('shell.titlebarSidecarError');
    case 'connected':
      return t('shell.titlebarSidecarConnected');
    default:
      return t('shell.titlebarSidecarIdle');
  }
});

function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function providerDisplay(entry: typeof activeChatProvider.value): string {
  if (!entry) return t('shell.titlebarNoProvider');
  return entry.label?.trim() || capitalize(entry.provider);
}

const labelMode = computed(() => {
  if (settingsLocked.value) return 'guided';
  return settingsMode.value === 'advanced' ? 'advanced' : 'guided';
});

const capabilityChips = computed(() => {
  const set = activeSet.value;
  if (!set) return [];
  const caps = capabilityLabels(set, labelMode.value, t);
  return caps.slice(0, 2);
});

const activeSetCapabilities = computed(() => {
  const set = activeSet.value;
  if (!set) return [];
  return capabilityLabels(set, labelMode.value, t);
});

const providerLabel = computed(() => {
  const set = activeSet.value;
  if (set) return localizedSetName(set, t);
  return providerDisplay(activeChatProvider.value);
});

const providerAriaLabel = computed(() =>
  t('shell.titlebarProviderAria', {
    name: providerLabel.value,
    status: sidecarLabel.value,
  }),
);

const providerTooltip = computed(() =>
  t('shell.titlebarProviderTooltip', {
    name: providerLabel.value,
    status: sidecarLabel.value,
  }),
);

const chatProviderLabel = computed(() => {
  const set = activeSet.value;
  if (set) {
    return `${localizedSetName(set, t)} ${t('shell.titlebarSep')} ${set.chat.model || '—'}`;
  }
  const entry = activeChatProvider.value;
  if (!entry) return t('shell.titlebarNoChatModel');
  return `${providerDisplay(entry)} ${t('shell.titlebarSep')} ${entry.model || '—'}`;
});

const embeddingProviderLabel = computed(() => {
  const set = activeSet.value;
  if (set?.embeddings) {
    return `${localizedSetName(set, t)} ${t('shell.titlebarSep')} ${set.embeddings.model}`;
  }
  const entry = activeEmbeddingProvider.value;
  if (!entry || !entry.embeddingModel) return t('shell.titlebarNoEmbeddingModel');
  return `${providerDisplay(entry)} ${t('shell.titlebarSep')} ${entry.embeddingModel}`;
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

.wp-titlebar__user {
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 28vw;
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
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-titlebar__chip-caps {
  display: inline-flex;
  gap: 4px;
  max-width: 160px;
  overflow: hidden;
}

.wp-titlebar__cap {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent-soft);
  color: var(--wp-text-muted);
  white-space: nowrap;
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
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}

.wp-sidecar-dialog__row--caps dd {
  max-width: 220px;
}

.wp-sidecar-dialog__cap {
  font-size: var(--wp-fs-xs);
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
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
