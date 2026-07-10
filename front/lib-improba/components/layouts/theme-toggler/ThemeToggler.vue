<template>
  <q-toggle
    class="q-pa-none wp-theme-toggle"
    :modelValue="!theme.quasar.dark.isActive"
    @update:modelValue="theme.methods.setTheme(!$event)"
    size="md"
    color="accent"
    checkedIcon="light_mode"
    uncheckedIcon="brightness_2"
    :label="i18n.t('theme')"
    left-label
    aria-label="Basculer le thème clair/sombre"
    title="Basculer le thème clair/sombre"
  />
</template>

<script lang="ts">
import { defineComponent, reactive, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import { useTheme } from 'src/../lib-improba/composables/use-theme';

export default defineComponent({
  setup() {
    const quasar = useQuasar();
    const theme = useTheme(quasar);
    const i18n = useI18n();
    const state = reactive({});

    const methods = {
      init() {
        theme.methods.init();
      },
    };

    onMounted(() => {
      methods.init();
    });

    return {
      i18n,
      theme,
    };
  },
});
</script>
<style scoped lang="scss">
.wp-theme-toggle :deep(.q-toggle__label) {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  font-family: var(--wp-font-ui);
}

.wp-theme-toggle:focus-within :deep(.q-toggle__inner) {
  outline: 2px solid var(--wp-focus-ring);
  outline-offset: var(--wp-focus-offset);
  border-radius: var(--wp-r-sm);
}
</style>
