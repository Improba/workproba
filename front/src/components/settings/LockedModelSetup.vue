<template>
  <section class="locked-setup">
    <div class="locked-setup__banner">
      <Lucide name="lock" size="20" color="text-muted" />
      <p>{{ t('settings.lockedBanner') }}</p>
    </div>

    <article v-if="activeSet" class="locked-setup__engine">
      <h2 class="locked-setup__title">{{ t('settings.lockedActiveEngine') }}</h2>
      <p class="locked-setup__name">{{ displayName }}</p>
      <p class="locked-setup__desc">{{ displayDescription }}</p>

      <h3 class="locked-setup__caps-title">{{ t('settings.lockedCapabilities') }}</h3>
      <ul class="locked-setup__caps">
        <li v-for="cap in capabilities" :key="cap">{{ cap }}</li>
      </ul>

      <dl class="locked-setup__meta">
        <div>
          <dt>{{ t('settings.advancedSetChat') }}</dt>
          <dd>{{ activeSet.chat.model }}</dd>
        </div>
        <div v-if="activeSet.embeddings">
          <dt>{{ t('shell.titlebarEmbeddings') }}</dt>
          <dd>{{ activeSet.embeddings.model }}</dd>
        </div>
      </dl>
    </article>

    <button type="button" class="locked-setup__request" @click="onRequestAccess">
      {{ t('settings.lockedRequestAccess') }}
    </button>
    <p v-if="requestMessage" class="locked-setup__feedback">
      {{ requestMessage }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { capabilityLabels, localizedSetDescription, localizedSetName } from '@utils/providerSets';

const { activeSet } = useAppSettings();
const { t } = useI18n();
const requestMessage = ref('');

const capabilities = computed(() => {
  const set = activeSet.value;
  if (!set) return [];
  return capabilityLabels(set, 'guided', t);
});

const displayName = computed(() => {
  const set = activeSet.value;
  return set ? localizedSetName(set, t) : '';
});

const displayDescription = computed(() => {
  const set = activeSet.value;
  return set ? localizedSetDescription(set, t) : '';
});

function onRequestAccess(): void {
  requestMessage.value = t('settings.lockedRequestMessage');
}
</script>

<style scoped lang="scss">
.locked-setup {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.locked-setup__banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.locked-setup__engine {
  padding: 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.locked-setup__title {
  margin: 0 0 6px;
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--wp-text-faint);
}

.locked-setup__name {
  margin: 0 0 4px;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.locked-setup__desc {
  margin: 0 0 12px;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.locked-setup__caps-title {
  margin: 0 0 8px;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.locked-setup__caps {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.locked-setup__caps li {
  font-size: var(--wp-fs-xs);
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.locked-setup__meta {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}

.locked-setup__meta dt {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.locked-setup__meta dd {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.locked-setup__request {
  align-self: flex-start;
  padding: 8px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  cursor: pointer;
}

.locked-setup__feedback {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}
</style>
