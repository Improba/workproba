<template>
  <q-route-tab no-caps style="flex: none" :to="{ name: HOME_ROUTE }">
    <div class="wp-logo-tab full-height row items-center justify-center">
      <slot>
        <WorkprobaBrand variant="logo" />
      </slot>
    </div>
  </q-route-tab>
</template>

<script setup lang="ts">
import WorkprobaBrand from '@components/brand/WorkprobaBrand.vue';
import { HOME_ROUTE } from '@router/meta';
</script>

<style scoped lang="scss">
.wp-logo-tab {
  padding: 0 4px;
}
</style>
