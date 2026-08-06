<template>
  <section v-if="allowedTools.length" class="specialist-tools">
    <h4 class="specialist-tools__title">{{ t('personas.toolsPanel.title') }}</h4>
    <p class="specialist-tools__hint">{{ t('personas.toolsPanel.hint') }}</p>
    <ul class="specialist-tools__list" role="list">
      <li
        v-for="toolRef in allowedTools"
        :key="toolRefKey(toolRef)"
        class="specialist-tools__item"
      >
        <span class="specialist-tools__label">
          {{ formatToolLabel(toolRef) }}
        </span>
        <span
          v-if="effectBadge(toolRef)"
          class="specialist-tools__badge"
          :data-effect="effectBadge(toolRef)"
        >
          {{ effectLabel(toolRef) }}
        </span>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ManagedConnector, PersonaInfo } from '@services/aiSidecar';
import {
  resolveManagedToolEffect,
  specialistAllowedTools,
  toolRefKey,
  type SpecialistToolRef,
} from '@utils/specialistTools';

const props = defineProps<{
  persona: PersonaInfo;
  connectors?: ManagedConnector[];
}>();

const { t } = useI18n();

const allowedTools = computed(() => specialistAllowedTools(props.persona));

function formatToolLabel(ref: SpecialistToolRef): string {
  const connector = props.connectors?.find((item) => item.id === ref.connector_id);
  const connectorLabel = connector?.name?.trim() || ref.connector_id;
  return t('toolCalls.managedConnectorTool', { connector: connectorLabel, tool: ref.tool });
}

function effectBadge(ref: SpecialistToolRef): string | null {
  const connectors = props.connectors ?? [];
  if (!connectors.length) return null;
  return resolveManagedToolEffect(connectors, ref);
}

function effectLabel(ref: SpecialistToolRef): string {
  const effect = effectBadge(ref);
  if (effect === 'read') return t('personas.toolsPanel.effectRead');
  if (effect === 'write') return t('personas.toolsPanel.effectWrite');
  return effect ?? '';
}
</script>

<style scoped lang="scss">
.specialist-tools {
  margin-top: var(--wp-space-3);
  padding-top: var(--wp-space-2);
  border-top: 1px solid var(--wp-border);
}

.specialist-tools__title {
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.specialist-tools__hint {
  margin: 0 0 var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.specialist-tools__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.specialist-tools__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1) var(--wp-space-2);
  border-radius: var(--wp-radius-sm, 4px);
  background: var(--wp-surface-2, rgba(255, 255, 255, 0.04));
}

.specialist-tools__label {
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, monospace);
  color: var(--wp-text);
}

.specialist-tools__badge {
  font-size: var(--wp-fs-xs);
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.02em;

  &[data-effect='read'] {
    color: var(--wp-accent, #4a90d9);
    background: rgba(74, 144, 217, 0.12);
  }

  &[data-effect='write'] {
    color: var(--wp-gold, #ffcc49);
    background: rgba(255, 204, 73, 0.12);
  }
}
</style>
