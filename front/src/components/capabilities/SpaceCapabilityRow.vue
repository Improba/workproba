<template>
  <div
    class="wp-space-cap-row"
    :class="{
      'wp-space-cap-row--unavailable': item.status === 'unavailable',
      'wp-space-cap-row--busy': busy,
    }"
    :data-capability-id="item.id"
  >
    <div class="wp-space-cap-row__main">
      <span class="wp-space-cap-row__icon" aria-hidden="true">
        <Lucide :name="icon" size="14" color="accent" />
      </span>
      <div class="wp-space-cap-row__text">
        <span class="wp-space-cap-row__name">{{ title }}</span>
        <span v-if="reasonLabel" class="wp-space-cap-row__reason">{{ reasonLabel }}</span>
      </div>
    </div>

    <div class="wp-space-cap-row__actions">
      <button
        v-if="showSetupLink"
        type="button"
        class="wp-space-cap-row__setup"
        @click="emit('open-setup', item)"
      >
        {{ t('capabilities.space.setupLink') }}
      </button>
      <q-toggle
        v-if="canToggle"
        dense
        size="sm"
        color="primary"
        :model-value="item.wanted"
        :disable="busy"
        :aria-label="t('capabilities.space.toggleAria', { name: title })"
        @update:model-value="onToggle"
      />
      <q-toggle
        v-else
        dense
        size="sm"
        color="primary"
        :model-value="item.wanted"
        disable
        :aria-label="t('capabilities.space.toggleAria', { name: title })"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import {
  buildManagedCapabilityDefinition,
  connectorIdFromManagedCapability,
  getCapabilityDefinition,
  isManagedCapabilityId,
  type CapabilityId,
  type ManagedCapabilityId,
} from '@capabilities/capabilityCatalog';
import { useCloud } from '@composables/useCloud';
import type { SpaceCapabilityItem } from '@services/aiSidecar';

const props = defineProps<{
  item: SpaceCapabilityItem;
  busy?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle', item: SpaceCapabilityItem, next: boolean): void;
  (e: 'open-setup', item: SpaceCapabilityItem): void;
}>();

const { t } = useI18n();
const { connectors } = useCloud();

const definition = computed(() => {
  const id = props.item.id as CapabilityId;
  if (isManagedCapabilityId(id)) {
    const connectorId = connectorIdFromManagedCapability(id as ManagedCapabilityId);
    const connector = connectors.value.find((c) => c.id === connectorId);
    return buildManagedCapabilityDefinition({
      connectorId,
      name: connector?.name ?? connectorId,
      description: connector?.description,
    });
  }
  return getCapabilityDefinition(id);
});

const title = computed(() => {
  const def = definition.value;
  if (!def) return props.item.id;
  if (def.resolvedTitle?.trim()) return def.resolvedTitle;
  if (def.titleKey) return t(def.titleKey);
  return props.item.id;
});

const icon = computed(() => definition.value?.icon ?? 'puzzle');

const canToggle = computed(() => props.item.entitled);

const showSetupLink = computed(() => {
  const reason = props.item.unavailableReason;
  return (
    props.item.status === 'unavailable'
    && (reason === 'cloud_not_ready' || reason === 'parent_cloud_off' || reason === 'not_entitled')
  );
});

const reasonLabel = computed(() => {
  if (props.item.status !== 'unavailable') return '';
  const reason = props.item.unavailableReason;
  if (reason === 'parent_cloud_off') {
    return t('capabilities.space.reasonParentCloudOff');
  }
  if (reason === 'cloud_not_ready') {
    return t('capabilities.space.reasonCloudNotReady');
  }
  if (reason === 'machine_disabled') {
    return t('capabilities.space.reasonMachineDisabled');
  }
  return t('capabilities.space.reasonNotEntitled');
});

function onToggle(next: boolean): void {
  emit('toggle', props.item, next);
}
</script>

<style scoped lang="scss">
.wp-space-cap-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  min-height: 36px;
  padding: var(--wp-space-1) 0;
}

.wp-space-cap-row--unavailable {
  opacity: 0.85;
}

.wp-space-cap-row--busy {
  opacity: 0.7;
}

.wp-space-cap-row__main {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-2);
  min-width: 0;
  flex: 1;
}

.wp-space-cap-row__icon {
  flex: none;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.wp-space-cap-row__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wp-space-cap-row__name {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wp-space-cap-row__reason {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  line-height: 1.3;
}

.wp-space-cap-row__actions {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
}

.wp-space-cap-row__setup {
  border: none;
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>
