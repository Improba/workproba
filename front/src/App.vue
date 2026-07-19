<template>
  <router-view />
  <ErrorReportDialog />
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import ErrorReportDialog from '@components/workproba/ErrorReportDialog.vue';

export default defineComponent({
  name: 'App',
  components: {
    ErrorReportDialog,
  },
  setup() {},
});
</script>
