<template>
  <div class="models-settings" :class="{ 'models-settings--locked': settingsLocked }">
    <header class="models-settings__header">
      <div>
        <h1 class="models-settings__title">Modèles IA</h1>
        <p class="models-settings__subtitle">
          Configurez l'accès aux modèles (clé API, endpoint, modèle). La clé est
          stockée localement sur cette machine, dans les données de l'app.
        </p>
      </div>
    </header>

    <section v-if="loading" class="models-settings__empty">Chargement…</section>

    <template v-else>
      <DensityControl />

      <LockedModelSetup v-if="settingsLocked" />

      <fieldset v-else class="models-settings__body">
        <AdvancedModelSetup
          v-if="settingsMode === 'advanced'"
          @switch-to-guided="onSwitchToGuided"
        />
        <GuidedModelSetup v-else @switch-to-advanced="onSwitchToAdvanced" />
      </fieldset>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { Notify } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import GuidedModelSetup from '@components/settings/GuidedModelSetup.vue';
import AdvancedModelSetup from '@components/settings/AdvancedModelSetup.vue';
import LockedModelSetup from '@components/settings/LockedModelSetup.vue';
import DensityControl from '@components/settings/DensityControl.vue';

const {
  load,
  setSettingsMode,
  settingsMode,
  settingsLocked,
} = useAppSettings();

const loading = ref(true);

async function onSwitchToAdvanced(): Promise<void> {
  try {
    await setSettingsMode('advanced');
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Bascule impossible',
      color: 'negative',
    });
  }
}

async function onSwitchToGuided(): Promise<void> {
  try {
    await setSettingsMode('guided');
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Bascule impossible',
      color: 'negative',
    });
  }
}

onMounted(async () => {
  try {
    await load();
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped lang="scss">
.models-settings {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  box-sizing: border-box;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  overflow-y: auto;
}

.models-settings__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
  margin-bottom: 1rem;
}

.models-settings__title {
  margin: 0 0 0.25rem;
  font-family: var(--wp-font-head);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wp-text);
}

.models-settings__subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.models-settings__empty {
  padding: 24px 4px;
  color: var(--wp-text-faint);
  font-size: 14px;
}

.models-settings__body {
  border: none;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.models-settings--locked .models-settings__header {
  opacity: 0.6;
}
</style>
