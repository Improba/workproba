<template>
  <section class="managed-connectors cloud-panel__section">
    <h3 class="cloud-panel__section-title">{{ t('cloud.connectors.title') }}</h3>

    <p class="cloud-panel__hint">{{ t('cloud.connectors.hint') }}</p>

    <p v-if="error" class="cloud-panel__error" role="alert">
      {{ error }}
    </p>

    <p v-else-if="loading && !connectors.length" class="cloud-panel__loading">
      {{ t('common.loading') }}
    </p>

    <p v-else-if="!connectors.length" class="cloud-panel__empty">
      {{ t('cloud.connectors.empty') }}
    </p>

    <ul v-else class="managed-connectors__list" role="list">
      <li
        v-for="connector in connectors"
        :key="connector.id"
        class="managed-connectors__item"
      >
        <div class="managed-connectors__main">
          <span class="managed-connectors__name">{{ connector.name }}</span>
          <span v-if="showIds" class="managed-connectors__id">{{ connector.id }}</span>
          <p v-if="connector.description" class="managed-connectors__description">
            {{ connector.description }}
          </p>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { ManagedConnector } from '@services/aiSidecar';

withDefaults(
  defineProps<{
    connectors: ManagedConnector[];
    loading: boolean;
    error: string | null;
    showIds?: boolean;
  }>(),
  { showIds: false },
);

const { t } = useI18n();
</script>

<style scoped lang="scss">
.managed-connectors__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.managed-connectors__item {
  padding: var(--wp-space-2) 0;
  border-bottom: 1px solid var(--wp-border);

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  &:first-child {
    padding-top: 0;
  }
}

.managed-connectors__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.managed-connectors__name {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  font-weight: 500;
}

.managed-connectors__id {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  font-family: var(--wp-font-mono, monospace);
  word-break: break-all;
}

.managed-connectors__description {
  margin: 4px 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}
</style>
