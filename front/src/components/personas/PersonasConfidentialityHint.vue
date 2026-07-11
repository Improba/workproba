<template>
  <p class="personas-confidentiality" :title="t('personas.confidentiality.tooltip')">
    <Lucide name="shield" size="12" color="text-faint" />
    <span>{{ t('personas.confidentiality.hint') }}</span>
  </p>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

const { t } = useI18n();
</script>

<style scoped lang="scss">
.personas-confidentiality {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-1);
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  line-height: var(--wp-lh-tight);
  cursor: help;
}
</style>
