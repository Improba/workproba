<template>
  <span
    class="persona-avatar"
    :style="{ backgroundColor: color }"
    :title="name"
    :aria-label="name"
  >
    <Lucide
      v-if="icon"
      class="persona-avatar__icon"
      :name="icon"
      size="16"
      color="wp-canard"
    />
    <span v-else class="persona-avatar__initial">{{ initial }}</span>
    <span class="persona-avatar__badge" aria-hidden="true" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

const props = defineProps<{
  name: string;
  color?: string;
  icon?: string;
}>();

const color = computed(() => props.color || 'var(--wp-gold)');

const icon = computed(() => {
  const trimmed = (props.icon ?? '').trim();
  return trimmed || null;
});

const initial = computed(() => {
  const trimmed = props.name.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() : '?';
});
</script>

<style scoped lang="scss">
.persona-avatar {
  position: relative;
  flex: none;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-pill);
  color: var(--wp-canard);
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  line-height: 1;
}

.persona-avatar__icon {
  flex: none;
}

.persona-avatar__badge {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 10px;
  height: 10px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold);
  border: 2px solid var(--wp-surface);
}
</style>
