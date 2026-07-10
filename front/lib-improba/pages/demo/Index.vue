<template>
  <StandardLayout>
    <Drawer />
    <router-view />
  </StandardLayout>
</template>

<script setup lang="ts">
import StandardLayout from '@layouts/StandardLayout.vue';
import Drawer from '@pages/adminspace/_components/Drawer.vue';

</script>
