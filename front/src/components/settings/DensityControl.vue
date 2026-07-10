<template>
  <section class="density-control" :class="{ 'density-control--locked': locked }">
    <div class="density-control__head">
      <h2 class="density-control__title">Densité de l'interface</h2>
      <p class="density-control__subtitle">
        Ajuste l'espacement et la respiration des éléments de l'interface.
      </p>
    </div>

    <p v-if="locked" class="density-control__locked-msg">
      Verrouillé par votre administrateur
    </p>

    <div
      class="density-control__pills"
      role="radiogroup"
      aria-label="Densité de l'interface"
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
import { ref } from 'vue';
import { Notify } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import type { DensityMode } from '@composables/useDesktop.types';

const { density, settingsLocked, setDensity } = useAppSettings();

const locked = settingsLocked;
const saving = ref(false);

const options: { value: DensityMode; label: string }[] = [
  { value: 'compact', label: 'Compact' },
  { value: 'comfortable', label: 'Confortable' },
  { value: 'spacious', label: 'Aéré' },
];

async function onSelect(mode: DensityMode): Promise<void> {
  if (locked.value || saving.value || density.value === mode) return;
  saving.value = true;
  try {
    await setDensity(mode);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Impossible de changer la densité',
      color: 'negative',
    });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.density-control {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding-bottom: var(--wp-space-4);
  margin-bottom: var(--wp-space-4);
  border-bottom: 1px solid var(--wp-border);
}

.density-control__head {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.density-control__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  line-height: var(--wp-lh-tight);
  color: var(--wp-text);
}

.density-control__subtitle {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.density-control__locked-msg {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.density-control__pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
}

.density-pill {
  min-height: 36px;
  padding: var(--wp-space-2) var(--wp-space-4);
  border: 2px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: var(--wp-lh-tight);
  color: var(--wp-text-muted);
  cursor: pointer;
  transition: border-color var(--wp-dur) var(--wp-ease), color var(--wp-dur) var(--wp-ease),
    box-shadow var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    border-color: var(--wp-accent);
    color: var(--wp-text);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: var(--wp-focus-offset);
  }

  &--selected {
    border-color: var(--wp-accent);
    color: var(--wp-accent);
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.density-control--locked .density-control__pills {
  opacity: 0.7;
}
</style>
