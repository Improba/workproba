<template>
  <section
    v-if="effectiveDataDir"
    class="wp-space-caps"
    :class="{ 'wp-space-caps--embedded': embedded }"
    :aria-label="t('capabilities.space.title')"
  >
    <button
      v-if="!embedded"
      type="button"
      class="wp-space-caps__toggle"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <Lucide
        :name="expanded ? 'chevron-down' : 'chevron-right'"
        size="14"
        color="text-faint"
      />
      <span class="wp-space-caps__title">{{ t('capabilities.space.title') }}</span>
    </button>

    <h3 v-else class="wp-space-caps__title wp-space-caps__title--embedded">
      {{ t('capabilities.space.title') }}
    </h3>

    <div v-if="embedded || expanded" class="wp-space-caps__body">
      <p class="wp-space-caps__lead">{{ t('capabilities.space.lead') }}</p>

      <p v-if="loading && !profile" class="wp-space-caps__hint">
        {{ t('common.loading') }}
      </p>
      <p v-else-if="error" class="wp-space-caps__error">{{ error }}</p>

      <template v-else>
        <div v-if="activeItems.length" class="wp-space-caps__section">
          <h3 class="wp-space-caps__section-title">
            {{ t('capabilities.space.sectionActive') }}
          </h3>
          <SpaceCapabilityRow
            v-for="item in activeItems"
            :key="item.id"
            :item="item"
            :busy="busyId === item.id"
            @toggle="onToggle"
          />
        </div>

        <div v-if="availableItems.length" class="wp-space-caps__section">
          <h3 class="wp-space-caps__section-title">
            {{ t('capabilities.space.sectionAvailable') }}
          </h3>
          <SpaceCapabilityRow
            v-for="item in availableItems"
            :key="item.id"
            :item="item"
            :busy="busyId === item.id"
            @toggle="onToggle"
          />
        </div>

        <div v-if="unavailableItems.length" class="wp-space-caps__section">
          <h3 class="wp-space-caps__section-title">
            {{ t('capabilities.space.sectionUnavailable') }}
          </h3>
          <SpaceCapabilityRow
            v-for="item in unavailableItems"
            :key="item.id"
            :item="item"
            :busy="busyId === item.id"
            @open-setup="onOpenSetup"
            @toggle="onToggle"
          />
        </div>

        <p
          v-if="!activeItems.length && !availableItems.length && !unavailableItems.length"
          class="wp-space-caps__hint"
        >
          {{ t('capabilities.space.empty') }}
        </p>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import SpaceCapabilityRow from './SpaceCapabilityRow.vue';
import { useSpace } from '@composables/useSpace';
import { useSpaceCapabilities } from '@composables/useSpaceCapabilities';
import { useShellSurfaces } from '@composables/useShellSurfaces';
import type { CapabilityId } from '@capabilities/capabilityCatalog';
import type { SpaceCapabilityItem } from '@services/aiSidecar';

const props = withDefaults(
  defineProps<{
    workspaceDataDir?: string | null;
    embedded?: boolean;
  }>(),
  { embedded: false },
);

const emit = defineEmits<{
  (e: 'open-setup', item: SpaceCapabilityItem): void;
}>();

const { t } = useI18n();
const { activeDataDir } = useSpace();

const effectiveDataDir = computed(
  () => props.workspaceDataDir ?? activeDataDir.value,
);

const workspaceDataDirRef = computed(() => effectiveDataDir.value);

const {
  loading,
  error,
  profile,
  activeItems,
  availableItems,
  unavailableItems,
  setWanted,
} = useSpaceCapabilities(
  props.workspaceDataDir !== undefined
    ? { workspaceDataDir: workspaceDataDirRef }
    : undefined,
);
const { openCapabilities } = useShellSurfaces();

const expanded = ref(true);
const busyId = ref<string | null>(null);

async function onToggle(item: SpaceCapabilityItem, next: boolean): Promise<void> {
  busyId.value = item.id;
  try {
    const result = await setWanted(item.id as CapabilityId, next);
    if (!result.ok) {
      Notify.create({
        message: result.error || t('capabilities.space.toggleFailed'),
        color: 'negative',
      });
      return;
    }
    if (result.autoWantedCloud) {
      Notify.create({
        message: t('capabilities.space.autoWantedCloud'),
        color: 'info',
        timeout: 3500,
      });
    }
    Notify.create({
      message: t('capabilities.space.nextTurnNote'),
      color: 'dark',
      timeout: 2800,
    });
  } finally {
    busyId.value = null;
  }
}

function onOpenSetup(item: SpaceCapabilityItem): void {
  if (props.embedded) {
    emit('open-setup', item);
    return;
  }
  openCapabilities('workproba_cloud');
}
</script>

<style scoped lang="scss">
.wp-space-caps {
  flex: none;
  max-height: 42%;
  overflow-y: auto;
  border-top: 1px solid var(--wp-border);
  padding: var(--wp-space-2) var(--wp-space-3);
}

.wp-space-caps--embedded {
  max-height: none;
  border-top: none;
  padding: 0;
}

.wp-space-caps__title--embedded {
  margin: 0;
}

.wp-space-caps__toggle {
  width: 100%;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) 0;
  border: none;
  background: transparent;
  color: var(--wp-text);
  cursor: pointer;
  text-align: left;
}

.wp-space-caps__title {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
}

.wp-space-caps__body {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding-bottom: var(--wp-space-2);
}

.wp-space-caps__lead {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.wp-space-caps__section {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.wp-space-caps__section-title {
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--wp-text-faint);
}

.wp-space-caps__hint,
.wp-space-caps__error {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.wp-space-caps__error {
  color: var(--wp-danger, #b42318);
}
</style>
