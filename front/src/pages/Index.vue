<template>
  <WorkprobaLayout :streaming="streaming" :sidecar-state="sidecarState">
    <router-view />
  </WorkprobaLayout>
</template>

<script setup lang="ts">
import WorkprobaLayout from '@layouts/WorkprobaLayout.vue';
import { useChatActivity } from '@composables/useChatActivity';

const { streaming, sidecarState } = useChatActivity();
</script>
