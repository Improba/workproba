<template>
  <q-layout view="hHh lpR fff">
    <q-header>
      <Toolbar
        :roleTitle="props.roleTitle"
        :menuItems="props.menuItems"
        :profileMenuItems="props.profileMenuItems"
        :themeLabel="props.themeLabel"
      />
    </q-header>
    <q-page-container>
      <slot />
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import {
  defineComponent,
  reactive,
  computed,
  onMounted,
  onUnmounted,
} from 'vue';
import { useRouter } from 'vue-router';
import Toolbar from './toolbar/Index.vue';
import { useTheme } from 'src/../lib-improba/composables/use-theme';
import { useQuasar } from 'quasar';

export default defineComponent({
  components: {
    Toolbar,
  },
  props: {
    menuItems: {
      type: Array as any,
      default: () => [],
    },
    profileMenuItems: {
      type: Array as any,
      default: () => [],
    },
    roleTitle: {
      type: String as any,
      default: '',
    },
    themeLabel: {
      type: String as any,
      default: '',
    },
  },
  setup(props) {
    const quasar = useQuasar();
    const router = useRouter();
    const theme = useTheme(quasar);

    const state = reactive({});
    const stateless = {};

    const computedState = {
      appVersion: computed(() => {
        return process.env.APP_VERSION;
      }),
    };

    const methods = {
      init() {
        // theme.methods.setTheme(true, false);
      },
    };

    onMounted(() => {
      methods.init();
    });

    onUnmounted(() => {});

    return {
      props,
      state,
      stateless,
      computedState,
      methods,
    };
  },
});
</script>
../../../../composables/useTheme
