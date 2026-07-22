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
        <div
          class="wp-cap-drawer__group"
          :class="{ 'wp-cap-drawer__group--with-nested': nestedViews(view.definition.id).length }"
        >
          <CapabilityCard
            :view="view"
            :busy="busyCapabilityId === view.definition.id"
            :class="{
              'wp-cap-card--focus': focusCapabilityId === view.definition.id,
              'wp-cap-card--group-parent': nestedViews(view.definition.id).length,
            }"
            @activate-and-open="onActivateAndOpen"
            @open="onOpen"
            @deactivate="onDeactivate"
          />

          <CapabilityNestedGroup
            v-if="nestedViews(view.definition.id).length"
            :parent-id="view.definition.id"
            :views="nestedViews(view.definition.id)"
            :busy-capability-id="busyCapabilityId"
            :focus-capability-id="focusCapabilityId"
            :initially-expanded="view.definition.id === 'workproba_cloud'"
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
import { Dialog, Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import CapabilityCard from './CapabilityCard.vue';
import CapabilityNestedGroup from './CapabilityNestedGroup.vue';
import {
  getTopLevelCapabilities,
  type CapabilityId,
} from '@capabilities/capabilityCatalog';
import { useCapabilities } from '@composables/useCapabilities';
import { useShellSurfaces } from '@composables/useShellSurfaces';

const { t } = useI18n();
const {
  capabilities,
  activateAndOpen,
  open: openCapability,
  deactivate,
  refreshManaged,
} = useCapabilities();
const { capabilitiesOpen, focusCapabilityId, closeCapabilities } = useShellSurfaces();
const busyCapabilityId = ref<CapabilityId | null>(null);
const refreshingManaged = ref(false);

watch(capabilitiesOpen, async (open) => {
  if (!open || refreshingManaged.value) return;
  refreshingManaged.value = true;
  try {
    await refreshManaged();
  } catch {
    // Best-effort : le hub reste utilisable sans connecteurs.
  } finally {
    refreshingManaged.value = false;
  }
});

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

const nestedByParent = computed(() => {
  const map = new Map<CapabilityId, typeof capabilities.value>();
  for (const view of capabilities.value) {
    const parentId = view.definition.parentId;
    if (!parentId) continue;
    const list = map.get(parentId);
    if (list) {
      list.push(view);
    } else {
      map.set(parentId, [view]);
    }
  }
  return map;
});

function nestedViews(parentId: CapabilityId) {
  return nestedByParent.value.get(parentId) ?? [];
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

function confirmMachineDeactivate(): Promise<boolean> {
  return new Promise((resolve) => {
    Dialog.create({
      title: t('capabilities.actions.deactivateConfirmTitle'),
      message: t('capabilities.actions.deactivateConfirmMessage'),
      cancel: { label: t('common.cancel'), flat: true },
      ok: {
        label: t('capabilities.actions.deactivateConfirmOk'),
        color: 'negative',
      },
      persistent: true,
    })
      .onOk(() => resolve(true))
      .onCancel(() => resolve(false))
      .onDismiss(() => resolve(false));
  });
}

async function onDeactivate(id: CapabilityId): Promise<void> {
  const confirmed = await confirmMachineDeactivate();
  if (!confirmed) return;

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

.wp-cap-drawer__group {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}

.wp-cap-drawer__group--with-nested {
  :deep(.wp-cap-card--group-parent) {
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
}
</style>
