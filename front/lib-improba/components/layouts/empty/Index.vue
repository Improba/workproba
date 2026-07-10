<template>
  <q-layout>
    <q-page-container>
      <slot />
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import { defineComponent, onMounted } from 'vue';
import { useTheme } from 'src/../lib-improba/composables/use-theme';
import { useQuasar } from 'quasar';

export default defineComponent({
  setup(props) {
    const quasar = useQuasar();
    const theme = useTheme(quasar);
    onMounted(() => {
      // theme.methods.setTheme(true, false);
    });

    return { props };
  },
});
</script>
