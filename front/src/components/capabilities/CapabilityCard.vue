<template>
  <article
    class="wp-cap-card"
    :class="{ 'wp-cap-card--nested': nested }"
    :data-capability-id="view.definition.id"
    :aria-busy="busy || undefined"
  >
    <header class="wp-cap-card__head">
      <span class="wp-cap-card__icon" aria-hidden="true">
        <Lucide :name="view.definition.icon" size="18" color="accent" />
      </span>
      <div class="wp-cap-card__titles">
        <h3 class="wp-cap-card__title">{{ t(view.definition.titleKey) }}</h3>
        <CapabilityStatusBadge :state="view.state" />
      </div>
    </header>

    <p class="wp-cap-card__description">{{ t(view.definition.descriptionKey) }}</p>

    <p class="wp-cap-card__home">
      <Lucide name="home" size="13" color="text-faint" />
      <span>{{ t(view.definition.homeKey) }}</span>
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

const props = defineProps<{
  view: CapabilityView;
  nested?: boolean;
  busy?: boolean;
}>();

const { busy } = toRefs(props);

const emit = defineEmits<{
  (e: 'activate-and-open', id: CapabilityId): void;
  (e: 'open', id: CapabilityId): void;
  (e: 'deactivate', id: CapabilityId): void;
}>();

const { t } = useI18n();

const primaryAction = computed(() => {
  const { state } = props.view;
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
        label: t('capabilities.actions.activateAndOpen'),
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

const showOpenAction = computed(
  () => props.view.state.kind === 'needs_setup',
);

const showDeactivate = computed(() => props.view.state.kind === 'active');

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
  margin-left: var(--wp-space-4);
  border-style: dashed;
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
  color: var(--wp-on-accent, #fff);
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
