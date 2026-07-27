<template>
  <div class="settings-subnav-wrap">
    <div class="settings-subnav__toolbar">
      <button
        type="button"
        class="settings-subnav__back"
        @click="leaveSettings"
      >
        <Lucide name="arrow-left" size="16" color="text-muted" />
        {{ t('settings.back') }}
      </button>
      <button
        type="button"
        class="settings-subnav__close"
        :aria-label="t('common.close')"
        @click="leaveSettings"
      >
        <Lucide name="x" size="16" color="text-muted" />
      </button>
    </div>

    <nav class="settings-subnav" :aria-label="t('settings.plugins.navLabel')">
      <router-link
        :to="{ name: 'settings_models' }"
        class="settings-subnav__link"
        :class="{ 'settings-subnav__link--active': active === 'models' }"
      >
        {{ t('settings.plugins.navModels') }}
      </router-link>
      <router-link
        :to="{ name: 'settings_plugins' }"
        class="settings-subnav__link"
        :class="{ 'settings-subnav__link--active': active === 'plugins' }"
      >
        {{ pluginsNavLabel }}
      </router-link>
      <router-link
        :to="{ name: 'settings_enterprise' }"
        class="settings-subnav__link"
        :class="{ 'settings-subnav__link--active': active === 'enterprise' }"
      >
        {{ t('enterprise.navTitle') }}
      </router-link>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { HOME_ROUTE } from '@router/meta';

defineProps<{
  active: 'models' | 'plugins' | 'enterprise';
}>();

const { t } = useI18n();
const router = useRouter();
const { settingsLocked } = useAppSettings();

const pluginsNavLabel = computed(() =>
  !settingsLocked.value
    ? t('settings.plugins.navTitleAdvanced')
    : t('settings.plugins.navTitle'),
);

function leaveSettings(): void {
  const back = router.options.history.state.back as string | undefined;
  if (back && !back.includes('/settings')) {
    void router.back();
    return;
  }
  void router.push({ name: HOME_ROUTE });
}
</script>

<style scoped lang="scss">
.settings-subnav-wrap {
  margin-bottom: 1rem;
}

.settings-subnav__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.settings-subnav__back {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
  }
}

.settings-subnav__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.settings-subnav {
  display: flex;
  gap: var(--wp-space-2);
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
}

.settings-subnav__link {
  padding: var(--wp-space-2) var(--wp-space-3);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-decoration: none;
  transition: background var(--wp-dur) var(--wp-ease), color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &--active {
    background: var(--wp-accent-soft);
    color: var(--wp-accent);
    font-weight: 600;
  }
}
</style>
