<template>
  <div class="wp-titlebar" data-tauri-drag-region>
    <div class="wp-titlebar__brand" data-tauri-drag-region>
      <button
        type="button"
        class="wp-titlebar__mark"
        :aria-label="t('shell.titlebarHome')"
        @click="goHome"
      >
        <WorkprobaBrand variant="mark" />
      </button>
      <span v-if="workspaceTitle" class="wp-titlebar__sep">{{ t('shell.titlebarSep') }}</span>
      <span v-if="workspaceTitle" class="wp-titlebar__workspace" :title="activePath ?? ''">
        {{ workspaceTitle }}
      </span>
    </div>

    <div class="wp-titlebar__right">
      <button
        type="button"
        class="wp-titlebar__chip"
        :class="[
          `wp-titlebar__chip--${environmentChipState}`,
          { 'wp-titlebar__chip--active': environmentOpen },
        ]"
        :aria-label="environmentAriaLabel"
        :aria-expanded="environmentOpen"
        @click="$emit('toggle-environment')"
      >
        <span class="wp-titlebar__chip-dot" />
        <span class="wp-titlebar__chip-label">{{ environmentLabel }}</span>
        <Lucide name="chevron-down" size="13" color="text-faint" />
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ environmentTooltip }}
        </q-tooltip>
      </button>

      <button
        type="button"
        class="wp-titlebar__btn"
        :class="{ 'wp-titlebar__btn--active': rightPanelOpen }"
        :aria-label="filesAriaLabel"
        :title="filesAriaLabel"
        @click="$emit('toggle-right-panel')"
      >
        <q-tooltip anchor="bottom middle" self="top middle" :offset="[0, 6]">
          {{ filesAriaLabel }}
        </q-tooltip>
        <Lucide
          :name="rightPanelOpen ? 'panel-right-close' : 'panel-right-open'"
          size="16"
          color="text-muted"
        />
        <span class="wp-sr-only">{{ filesAriaLabel }}</span>
      </button>

      <button
        type="button"
        class="wp-titlebar__btn"
        :aria-label="t('shell.titlebarMenu')"
        :title="t('shell.titlebarMenu')"
        aria-haspopup="menu"
      >
        <Lucide name="ellipsis" size="16" color="text-muted" />
        <span class="wp-sr-only">{{ t('shell.titlebarMenu') }}</span>
        <q-menu anchor="bottom right" self="top right" :offset="[0, 6]">
          <q-list dense class="wp-titlebar__menu">
            <q-item clickable @click="$emit('toggle-sidebar')">
              <q-item-section avatar>
                <Lucide
                  :name="sidebarRail ? 'panel-left-open' : 'panel-left-close'"
                  size="16"
                  color="text-muted"
                />
              </q-item-section>
              <q-item-section>{{ sidebarAriaLabel }}</q-item-section>
            </q-item>
            <q-item clickable @click="$emit('open-shortcuts')">
              <q-item-section avatar>
                <Lucide name="keyboard" size="16" color="text-muted" />
              </q-item-section>
              <q-item-section>{{ t('shell.titlebarShortcuts') }}</q-item-section>
            </q-item>
            <q-separator />
            <q-item class="wp-titlebar__theme-item">
              <q-item-section avatar>
                <Lucide name="sun-moon" size="16" color="text-muted" />
              </q-item-section>
              <q-item-section>{{ t('shell.titlebarTheme') }}</q-item-section>
              <q-item-section side>
                <ThemeToggler />
              </q-item-section>
            </q-item>
          </q-list>
        </q-menu>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import ThemeToggler from '@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import WorkprobaBrand from '@components/brand/WorkprobaBrand.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useOrganizationEnvironment } from '@composables/useOrganizationEnvironment';
import { resolveEnvironmentChipState, resolveEnvironmentStatusLabel } from '@utils/environmentStatus';
import { useChatActivity } from '@composables/useChatActivity';

const props = defineProps<{
  workspaceTitle: string | null;
  activePath: string | null;
  rightPanelOpen: boolean;
  environmentOpen?: boolean;
  sidebarRail: boolean;
}>();

defineEmits<{
  (e: 'toggle-right-panel'): void;
  (e: 'toggle-environment'): void;
  (e: 'toggle-sidebar'): void;
  (e: 'open-shortcuts'): void;
}>();

const router = useRouter();
const { t } = useI18n();
const { effectiveActiveSet } = useAppSettings();
const { sidecarState } = useChatActivity();
const {
  organizationName,
  cloudConnected,
  loading: environmentLoading,
  refresh: refreshEnvironment,
} = useOrganizationEnvironment();

const filesAriaLabel = computed(() =>
  props.rightPanelOpen
    ? t('shell.titlebarHideFiles')
    : t('shell.titlebarShowFiles'),
);

const sidebarAriaLabel = computed(() =>
  props.sidebarRail
    ? t('shell.titlebarShowSidebar')
    : t('shell.titlebarHideSidebar'),
);

const sidecarStateValue = computed(() => sidecarState.value);
const hasEffectiveEngine = computed(() => Boolean(effectiveActiveSet.value));
const environmentLabel = computed(
  () => organizationName.value || t('environment.defaultOrganization'),
);
const environmentChipState = computed(() => resolveEnvironmentChipState({
  sidecarState: sidecarStateValue.value,
  hasEffectiveEngine: hasEffectiveEngine.value,
  cloudConnected: cloudConnected.value,
}));
const environmentStatusLabel = computed(() => resolveEnvironmentStatusLabel({
  loading: environmentLoading.value,
  sidecarState: sidecarStateValue.value,
  hasEffectiveEngine: hasEffectiveEngine.value,
  cloudConnected: cloudConnected.value,
  t,
}));
const environmentAriaLabel = computed(() => t('environment.headerAria', {
  organization: environmentLabel.value,
  status: environmentStatusLabel.value,
}));
const environmentTooltip = computed(() => t('environment.headerTooltip', {
  organization: environmentLabel.value,
  status: environmentStatusLabel.value,
}));

onMounted(() => {
  void refreshEnvironment();
});

function goHome(): void {
  void router.push({ name: 'home' });
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
  align-items: center;
  gap: var(--wp-space-2);
  min-width: 0;
  flex: 1;
}

.wp-titlebar__mark {
  flex: none;
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: transparent;
  line-height: 0;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  transition: opacity 120ms var(--wp-ease);

  &:hover {
    opacity: 0.85;
  }

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: 2px;
  }
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
  max-width: 48vw;
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

  &--active {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
    color: var(--wp-text);
  }
}

.wp-titlebar__chip-label {
  max-width: 120px;
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

.wp-titlebar__theme-item {
  min-width: 220px;
}
</style>
