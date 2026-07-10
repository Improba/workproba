<template>
  <template v-if="screen.gt.sm">
    <Content
      :roleTitle="props.roleTitle"
      :menuItems="props.menuItems"
      :userMenuItems="props.userMenuItems"
      :profileMenuItems="props.profileMenuItems"
      :themeLabel="props.themeLabel"
    >
    </Content>
  </template>
  <template v-else>
    <Content_ hideLogo style="padding: 5 !important; text-align: center">
      <div class="full-width row justify-evenly">
        <slot> </slot>
      </div>
    </Content_>
  </template>
</template>

<script lang="ts">
import {
  defineComponent,
  reactive,
  computed,
  onMounted,
  onUnmounted,
} from 'vue';
import Content_ from './Content.vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';

export default defineComponent({
  components: {
    Content_,
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
      type: String,
      default: '',
      required: false,
    },
    themeLabel: {
      type: String,
      default: '',
      required: false,
    },
  },
  setup(props) {
    const router = useRouter();
    const quasar = useQuasar();

    const state = reactive({});

    const stateless = {};

    const computedState = {
      appVersion: computed(() => {
        return process.env.APP_VERSION;
      }),
      userName: computed(() => {
        const user = store.state?.auth?.user;
        const userName =
          user?.firstname ??
          user?.userAuth?.username ??
          user?.userJwt?.username ??
          props.roleTitle;
        return userName;
      }),
    };

    const methods = {
      goToLogin() {
        router.push({ name: 'profilChoice' });
      },
      async init() {},
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
      screen: quasar.screen,
    };
  },
});
</script>
