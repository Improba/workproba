<template>
  <aside
    v-if="capabilitiesOpen"
    class="wp-cap-drawer"
    role="complementary"
    :aria-label="t('capabilities.drawerTitle')"
  >
    <header class="wp-cap-drawer__head">
      <h2 class="wp-cap-drawer__title">{{ t('capabilities.drawerTitle') }}</h2>
      <button
        type="button"
        class="wp-cap-drawer__close"
        :aria-label="t('common.close')"
        @click="closeCapabilities()"
      >
        <Lucide name="x" size="16" color="text-muted" />
      </button>
    </header>

    <p class="wp-cap-drawer__lead">{{ t('capabilities.drawerLead') }}</p>

    <div class="wp-cap-drawer__list">
      <template v-for="view in topLevelViews" :key="view.definition.id">
        <CapabilityCard
          :view="view"
          :busy="busyCapabilityId === view.definition.id"
          :class="{ 'wp-cap-drawer__focus': focusCapabilityId === view.definition.id }"
          @activate-and-open="onActivateAndOpen"
          @open="onOpen"
          @deactivate="onDeactivate"
        />

        <div
          v-if="nestedViews(view.definition.id).length"
          class="wp-cap-drawer__nested"
        >
          <CapabilityCard
            v-for="nested in nestedViews(view.definition.id)"
            :key="nested.definition.id"
            :view="nested"
            nested
            :busy="busyCapabilityId === nested.definition.id"
            :class="{ 'wp-cap-drawer__focus': focusCapabilityId === nested.definition.id }"
            @activate-and-open="onActivateAndOpen"
            @open="onOpen"
            @deactivate="onDeactivate"
          />
        </div>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import CapabilityCard from './CapabilityCard.vue';
import {
  getNestedCapabilities,
  getTopLevelCapabilities,
  type CapabilityId,
} from '@capabilities/capabilityCatalog';
import { useCapabilities } from '@composables/useCapabilities';
import { useShellSurfaces } from '@composables/useShellSurfaces';

const { t } = useI18n();
const { capabilities, activateAndOpen, open: openCapability, deactivate } = useCapabilities();
const { capabilitiesOpen, focusCapabilityId, closeCapabilities } = useShellSurfaces();
const busyCapabilityId = ref<CapabilityId | null>(null);

watch(focusCapabilityId, async (id) => {
  if (!id || !capabilitiesOpen.value) return;
  await nextTick();
  document
    .querySelector(`[data-capability-id="${id}"]`)
    ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
});

const topLevelViews = computed(() => {
  const topIds = new Set(getTopLevelCapabilities().map((cap) => cap.id));
  return capabilities.value.filter((view) => topIds.has(view.definition.id));
});

function nestedViews(parentId: CapabilityId) {
  const nestedIds = new Set(getNestedCapabilities(parentId).map((cap) => cap.id));
  return capabilities.value.filter((view) => nestedIds.has(view.definition.id));
}

async function onActivateAndOpen(id: CapabilityId): Promise<void> {
  busyCapabilityId.value = id;
  try {
    await activateAndOpen(id);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('capabilities.actions.activateFailed'),
      color: 'negative',
    });
  } finally {
    busyCapabilityId.value = null;
  }
}

function onOpen(id: CapabilityId): void {
  closeCapabilities();
  openCapability(id);
}

async function onDeactivate(id: CapabilityId): Promise<void> {
  busyCapabilityId.value = id;
  try {
    await deactivate(id);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('capabilities.actions.deactivateFailed'),
      color: 'negative',
    });
  } finally {
    busyCapabilityId.value = null;
  }
}
</script>

<style scoped lang="scss">
.wp-cap-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  width: clamp(400px, 38vw, 460px);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding: var(--wp-space-4);
  background: var(--wp-surface);
  border-left: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
  overflow-y: auto;
  animation: wp-cap-drawer-in var(--wp-dur) var(--wp-ease);
}

@keyframes wp-cap-drawer-in {
  from {
    opacity: 0;
    transform: translateX(12px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.wp-cap-drawer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-3);
}

.wp-cap-drawer__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
}

.wp-cap-drawer__close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-cap-drawer__lead {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.wp-cap-drawer__list {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.wp-cap-drawer__nested {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.wp-cap-drawer__focus {
  outline: 2px solid var(--wp-accent);
  outline-offset: 2px;
}
</style>
