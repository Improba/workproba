<template>
  <q-route-tab no-caps style="flex: none" :to="{ name: HOME_ROUTE }">
    <div class="full-height text-bold row items-center justify-center text-h4">
      <slot>{{ appName }}</slot>
    </div>
  </q-route-tab>
</template>

<script setup lang="ts">
import { HOME_ROUTE } from '@router/meta';

const appName = process.env.APP_NAME || 'App';
</script>

