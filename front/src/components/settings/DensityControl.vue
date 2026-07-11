<template>
  <section class="density-control" :class="{ 'density-control--locked': locked }">
    <div class="density-control__head">
      <h2 class="density-control__title">{{ t('settings.densityTitle') }}</h2>
      <p class="density-control__subtitle">
        {{ t('settings.densitySubtitle') }}
      </p>
    </div>

    <p v-if="locked" class="density-control__locked-msg">
      {{ t('settings.densityLocked') }}
    </p>

    <div
      class="density-control__pills"
      role="radiogroup"
      :aria-label="t('settings.densityTitle')"
    >
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="density-pill"
        :class="{ 'density-pill--selected': density === option.value }"
        role="radio"
        :aria-checked="density === option.value"
        :disabled="locked || saving"
        @click="onSelect(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import type { DensityMode } from '@composables/useDesktop.types';

const { t } = useI18n();
const { density, settingsLocked, setDensity } = useAppSettings();

const locked = settingsLocked;
const saving = ref(false);

const options = computed<{ value: DensityMode; label: string }[]>(() => [
  { value: 'compact', label: t('settings.densityCompact') },
  { value: 'comfortable', label: t('settings.densityComfortable') },
  { value: 'spacious', label: t('settings.densitySpacious') },
]);

async function onSelect(mode: DensityMode): Promise<void> {
  if (locked.value || saving.value || density.value === mode) return;
  saving.value = true;
  try {
    await setDensity(mode);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.densityChangeFailed'),
      color: 'negative',
    });
  } finally {
    saving.value = false;
  }
}
</script>
