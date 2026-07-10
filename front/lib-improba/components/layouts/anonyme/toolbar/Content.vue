<template>
  <q-toolbar
    class="bg-primary-low"
    style="border-bottom: 1px solid hsla(0, 0%, 100%, 0.12); padding: 20"
  >
    <q-tabs class="full-width text-text" align="left">
      <Logo v-if="!props.hideLogo" />

      <q-route-tab
        v-for="item in props.menuItems"
        :key="item.label"
        :to="item.route"
        :label="item.label"
        :disable="item.disable"
        dense
      />

      <slot />
    </q-tabs>
  </q-toolbar>
</template>

<script lang="ts">
import {
  defineComponent,
  reactive,
  computed,
  onMounted,
  onUnmounted,
} from 'vue';
import { useAuth } from 'src/../lib-improba/composables/use-auth';
import Logo from '../../Logo.vue';
import { useRouter } from 'vue-router';
import { HOME_ROUTE } from '@router/meta';

export default defineComponent({
  components: {
    Logo,
  },
  props: {
    menuItems: {
      type: Array as any,
      default: () => [],
    },
    userMenuItems: {
      type: Array as any,
      default: () => [],
    },
    profileMenuItems: {
      type: Array as any,
      default: () => [],
    },
    roleTitle: {
      type: String,
      default: '',
      required: false,
    },
    themeLabel: {
      type: String,
      default: '',
      required: false,
    },
    hideLogo: {
      type: Boolean,
      default: false,
      required: false,
    },
  },
  setup(props) {
    const router = useRouter();

    const state = reactive({});
    const stateless = {};

    const auth = useAuth(router);

    const computedState = {
      appVersion: computed(() => {
        return process.env.APP_VERSION;
      }),
      userName: computed(() => {
        const user = auth.sharedState?.user;
        const userName =
          user?.firstname ?? user?.userJwt?.username ?? props.roleTitle;
        return userName;
      }),
    };

    const methods = {
      goTo() {
        router.push({ name: HOME_ROUTE });
      },
      async init() {},
      logout() {
        auth.methods.logout();
      },
    };

    onMounted(async () => {
      await methods.init();
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
