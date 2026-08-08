<template>
  <WorkprobaLayout :streaming="streaming">
    <router-view />
  </WorkprobaLayout>
</template>

<script setup lang="ts">
import WorkprobaLayout from '@layouts/WorkprobaLayout.vue';
import { useChatActivity } from '@composables/useChatActivity';

const { streaming } = useChatActivity();
</script>
