<template>
  <article
    class="wp-cap-card"
    :class="{
      'wp-cap-card--nested': nested,
      'wp-cap-card--compact': compact,
    }"
    :data-capability-id="view.definition.id"
    :aria-busy="busy || undefined"
  >
    <header class="wp-cap-card__head">
      <span class="wp-cap-card__icon" aria-hidden="true">
        <Lucide :name="view.definition.icon" :size="compact ? '16' : '18'" color="accent" />
      </span>
      <div class="wp-cap-card__titles">
        <h3 class="wp-cap-card__title" :title="tooltip">{{ title }}</h3>
        <CapabilityStatusBadge :state="view.state" />
      </div>
    </header>

    <p v-if="description && !compact" class="wp-cap-card__description">{{ description }}</p>

    <p v-if="!compact" class="wp-cap-card__home">
      <Lucide name="home" size="13" color="text-faint" />
      <span>{{ homeLabel }}</span>
    </p>

    <footer class="wp-cap-card__actions">
      <button
        v-if="primaryAction"
        type="button"
        class="wp-cap-card__cta"
        :class="`wp-cap-card__cta--${primaryAction.kind}`"
        :disabled="primaryAction.disabled || !!busy"
        @click="onPrimaryAction"
      >
        {{ primaryAction.label }}
      </button>
      <button
        v-if="showOpenAction"
        type="button"
        class="wp-cap-card__secondary"
        :disabled="busy"
        @click="emit('open', view.definition.id)"
      >
        {{ t('capabilities.actions.open') }}
      </button>
      <button
        v-if="showDeactivate"
        type="button"
        class="wp-cap-card__secondary"
        :disabled="busy"
        @click="onDeactivate"
      >
        {{ t('capabilities.actions.deactivate') }}
      </button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, toRefs } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import CapabilityStatusBadge from './CapabilityStatusBadge.vue';
import type { CapabilityId } from '@capabilities/capabilityCatalog';
import type { CapabilityView } from '@composables/useCapabilities';

const props = withDefaults(
  defineProps<{
    view: CapabilityView;
    nested?: boolean;
    compact?: boolean;
    busy?: boolean;
  }>(),
  { nested: false, compact: false, busy: false },
);

const { busy } = toRefs(props);

const emit = defineEmits<{
  (e: 'activate-and-open', id: CapabilityId): void;
  (e: 'open', id: CapabilityId): void;
  (e: 'deactivate', id: CapabilityId): void;
}>();

const { t } = useI18n();

const isManaged = computed(() => props.view.definition.source === 'managed');

const title = computed(() => {
  if (props.view.definition.resolvedTitle?.trim()) {
    return props.view.definition.resolvedTitle;
  }
  if (props.view.definition.titleKey) {
    return t(props.view.definition.titleKey);
  }
  return props.view.definition.managedConnectorId ?? props.view.definition.id;
});

const description = computed(() => {
  if (props.view.definition.resolvedDescription?.trim()) {
    return props.view.definition.resolvedDescription;
  }
  if (props.view.definition.source === 'managed') {
    return t('capabilities.managed.description');
  }
  if (!props.view.definition.descriptionKey) return '';
  return t(props.view.definition.descriptionKey);
});

const homeLabel = computed(() => {
  if (!props.view.definition.homeKey) return '';
  return t(props.view.definition.homeKey);
});

const primaryAction = computed(() => {
  const { state } = props.view;
  const short = props.compact;
  switch (state.kind) {
    case 'active':
      return {
        kind: 'open',
        label: t('capabilities.actions.open'),
        disabled: false,
      };
    case 'available':
      return {
        kind: 'activate',
        label: short
          ? t('capabilities.actions.activate')
          : t('capabilities.actions.activateAndOpen'),
        disabled: false,
      };
    case 'needs_setup':
      return {
        kind: 'setup',
        label: t('capabilities.actions.configure'),
        disabled: false,
      };
    case 'blocked':
    case 'unavailable':
    case 'coming_soon':
      return null;
    default:
      return null;
  }
});

const tooltip = computed(() => {
  if (!props.compact) return undefined;
  return description.value || undefined;
});

const showOpenAction = computed(
  () => props.view.state.kind === 'needs_setup',
);

const showDeactivate = computed(
  () => props.view.state.kind === 'active' && !isManaged.value,
);

function onPrimaryAction(): void {
  if (!primaryAction.value) return;
  if (primaryAction.value.kind === 'open') {
    emit('open', props.view.definition.id);
    return;
  }
  emit('activate-and-open', props.view.definition.id);
}

function onDeactivate(): void {
  emit('deactivate', props.view.definition.id);
}
</script>

<style scoped lang="scss">
.wp-cap-card {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding: var(--wp-space-4);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
}

.wp-cap-card--nested {
  margin-left: 0;
  border-style: solid;
  box-shadow: none;
}

.wp-cap-card--compact {
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);

  .wp-cap-card__icon {
    width: 28px;
    height: 28px;
  }

  .wp-cap-card__title {
    font-size: var(--wp-fs-sm);
  }

  .wp-cap-card__titles {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--wp-space-2);
  }

  .wp-cap-card__cta,
  .wp-cap-card__secondary {
    min-height: 28px;
    font-size: var(--wp-fs-xs);
  }
}

.wp-cap-card--focus {
  outline: 2px solid var(--wp-accent);
  outline-offset: 2px;
}

.wp-cap-card__head {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-3);
}

.wp-cap-card__icon {
  flex: none;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
}

.wp-cap-card__titles {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.wp-cap-card__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 600;
  color: var(--wp-text);
}

.wp-cap-card__description {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.wp-cap-card__home {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.wp-cap-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
}

.wp-cap-card__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 var(--wp-space-3);
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease), border-color var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    filter: brightness(1.05);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &--open {
    background: transparent;
    color: var(--wp-accent);
  }
}

.wp-cap-card__secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
