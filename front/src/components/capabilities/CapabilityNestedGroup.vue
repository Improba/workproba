<template>
  <section
    class="wp-cap-nested"
    :data-parent-capability-id="parentId"
  >
    <button
      type="button"
      class="wp-cap-nested__toggle"
      :aria-expanded="expanded"
      :aria-controls="panelId"
      @click="toggle"
    >
      <Lucide
        :name="expanded ? 'chevron-down' : 'chevron-right'"
        size="16"
        color="text-muted"
      />
      <span class="wp-cap-nested__label">{{ t('capabilities.nested.toggle') }}</span>
      <span class="wp-cap-nested__count">{{ views.length }}</span>
    </button>

    <div
      v-show="expanded"
      :id="panelId"
      class="wp-cap-nested__panel"
      role="region"
      :aria-label="regionLabel"
    >
      <div class="wp-cap-nested__scroll">
        <CapabilityCard
          v-for="view in views"
          :key="view.definition.id"
          :view="view"
          nested
          compact
          :busy="busyCapabilityId === view.definition.id"
          :class="{ 'wp-cap-card--focus': focusCapabilityId === view.definition.id }"
          @activate-and-open="emit('activate-and-open', $event)"
          @open="emit('open', $event)"
          @deactivate="emit('deactivate', $event)"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import CapabilityCard from './CapabilityCard.vue';
import type { CapabilityId } from '@capabilities/capabilityCatalog';
import type { CapabilityView } from '@composables/useCapabilities';

const props = withDefaults(
  defineProps<{
    parentId: CapabilityId;
    views: CapabilityView[];
    busyCapabilityId: CapabilityId | null;
    focusCapabilityId: CapabilityId | null;
    /** Ouverture initiale (ex. Workproba Cloud). Ne force pas la réouverture après fermeture user. */
    initiallyExpanded?: boolean;
  }>(),
  { initiallyExpanded: true },
);

const emit = defineEmits<{
  (e: 'activate-and-open', id: CapabilityId): void;
  (e: 'open', id: CapabilityId): void;
  (e: 'deactivate', id: CapabilityId): void;
}>();

const { t } = useI18n();

const panelId = computed(
  () => `wp-cap-nested-${String(props.parentId).replace(/[^a-z0-9_-]/gi, '-')}`,
);

const expanded = ref(props.initiallyExpanded);

const regionLabel = computed(() =>
  t('capabilities.nested.region', { count: props.views.length }),
);

function toggle(): void {
  expanded.value = !expanded.value;
}

watch(
  () => props.focusCapabilityId,
  (focusId) => {
    if (!focusId) return;
    if (props.views.some((v) => v.definition.id === focusId)) {
      expanded.value = true;
    }
  },
);
</script>

<style scoped lang="scss">
.wp-cap-nested {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  margin: calc(var(--wp-space-2) * -1) 0 0;
  padding: var(--wp-space-2) var(--wp-space-3) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-top: none;
  border-radius: 0 0 var(--wp-r-md) var(--wp-r-md);
  background: var(--wp-surface-2, color-mix(in srgb, var(--wp-surface) 92%, var(--wp-text) 4%));
}

.wp-cap-nested__toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  align-self: flex-start;
  min-height: 32px;
  padding: 0 var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-surface);
    color: var(--wp-text);
  }
}

.wp-cap-nested__label {
  text-align: left;
}

.wp-cap-nested__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  height: 1.25rem;
  padding: 0 6px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

.wp-cap-nested__panel {
  min-width: 0;
}

.wp-cap-nested__scroll {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  max-height: min(52vh, 420px);
  overflow-y: auto;
  padding-right: 2px;
}
</style>
