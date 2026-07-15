<template>
  <div class="start-prompts" :class="`start-prompts--${variant}`">
    <button
      v-for="item in visiblePrompts"
      :key="item.id"
      type="button"
      class="start-prompts__item"
      :title="variant === 'chips' ? item.subtitle : undefined"
      @click="emit('select', item.prompt)"
    >
      <span v-if="variant === 'cards'" class="start-prompts__icon" aria-hidden="true">
        <Lucide :name="item.icon" size="20" color="wp-accent" />
      </span>
      <span class="start-prompts__text">
        <span class="start-prompts__title">{{ item.title }}</span>
        <span v-if="variant === 'cards'" class="start-prompts__subtitle">{{ item.subtitle }}</span>
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { getStartPrompts } from '../../data/startPrompts';

const props = withDefaults(defineProps<{
  variant?: 'cards' | 'chips';
  limit?: number;
}>(), {
  variant: 'chips',
  limit: 3,
});

const { locale } = useI18n();

const emit = defineEmits<{
  select: [prompt: string];
}>();

const prompts = computed(() => {
  void locale.value;
  return getStartPrompts();
});

const visiblePrompts = computed(() => {
  if (props.variant === 'cards') return prompts.value;
  return prompts.value.slice(0, props.limit);
});
</script>

<style scoped lang="scss">
.start-prompts--cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.65rem;
  width: 100%;
  max-width: 46rem;

  .start-prompts__item {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    padding: 0.75rem 0.85rem;
    border: 1px solid var(--wp-border);
    border-radius: var(--wp-r-md);
    background: var(--wp-surface);
    text-align: left;
    cursor: pointer;
    transition: border-color var(--wp-dur) var(--wp-ease),
      background var(--wp-dur) var(--wp-ease),
      box-shadow var(--wp-dur) var(--wp-ease);

    &:hover {
      border-color: var(--wp-accent);
      background: var(--wp-surface-2);
      box-shadow: var(--wp-shadow-1);
    }
  }

  .start-prompts__icon {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: var(--wp-r-sm);
    background: var(--wp-accent-soft);
  }

  .start-prompts__text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }

  .start-prompts__title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--wp-text);
    line-height: 1.3;
  }

  .start-prompts__subtitle {
    font-size: 0.75rem;
    color: var(--wp-text-muted);
    line-height: 1.35;
  }
}

.start-prompts--chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: center;

  .start-prompts__item {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--wp-border);
    border-radius: var(--wp-r-pill);
    background: transparent;
    color: var(--wp-text-muted);
    font-size: var(--wp-fs-sm);
    font-family: var(--wp-font-ui);
    cursor: pointer;
    transition: color var(--wp-dur) var(--wp-ease),
      border-color var(--wp-dur) var(--wp-ease),
      background var(--wp-dur) var(--wp-ease);

    &:hover {
      color: var(--wp-text);
      border-color: var(--wp-accent);
      background: var(--wp-accent-soft);
    }
  }

  .start-prompts__text {
    display: contents;
  }

  .start-prompts__title {
    white-space: nowrap;
  }
}

.start-prompts__item:focus-visible {
  outline: 2px solid var(--wp-accent);
  outline-offset: 2px;
}
</style>
