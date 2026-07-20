<template>
  <img
    class="wp-brand"
    :class="[`wp-brand--${variant}`, { 'wp-brand--dark': isDark }]"
    :src="src"
    :alt="alt"
    draggable="false"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useUiTheme } from '@composables/useUiTheme';
import markLight from '@assets/brand/workproba-mark-light.svg';
import markDark from '@assets/brand/workproba-mark-dark.svg';
import logoLight from '@assets/brand/workproba-logo-light.svg';
import logoDark from '@assets/brand/workproba-logo-dark.svg';

const props = withDefaults(
  defineProps<{
    /** Icône seule (titlebar) ou lockup complet (toolbar / auth). */
    variant?: 'mark' | 'logo';
  }>(),
  { variant: 'mark' },
);

const { t } = useI18n();
const { isDark } = useUiTheme();

const alt = computed(() => t('shell.titlebarBrand'));

const src = computed(() => {
  if (props.variant === 'logo') {
    return isDark.value ? logoDark : logoLight;
  }
  return isDark.value ? markDark : markLight;
});
</script>

<style scoped lang="scss">
.wp-brand {
  display: block;
  flex: none;
  height: 24px;
  width: auto;
  object-fit: contain;
  user-select: none;
  -webkit-user-select: none;
  pointer-events: none;
}

.wp-brand--logo {
  height: 28px;
}
</style>
