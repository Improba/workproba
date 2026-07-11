<template>
  <section v-if="!localeLocked" class="language-control">
    <div class="language-control__head">
      <h2 class="language-control__title">{{ t('settings.languageTitle') }}</h2>
      <p class="language-control__subtitle">{{ t('settings.languageSubtitle') }}</p>
    </div>

    <div
      class="language-control__pills"
      role="radiogroup"
      :aria-label="t('settings.languageTitle')"
    >
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="language-pill"
        :class="{ 'language-pill--selected': locale === option.value }"
        role="radio"
        :aria-checked="locale === option.value"
        :disabled="saving"
        @click="onSelect(option.value)"
      >
        {{ option.label }}
      </button>
    </div>
  </section>
  <section v-else class="language-control language-control--locked">
    <div class="language-control__head">
      <h2 class="language-control__title">{{ t('settings.languageTitle') }}</h2>
      <p class="language-control__locked-msg">
        {{ t('settings.languageLocked') }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import type { AppLocale } from '@composables/useDesktop.types';

const { t } = useI18n();
const { locale, localeLocked, setLocale } = useAppSettings();
const saving = ref(false);

const options: { value: AppLocale; label: string }[] = [
  { value: 'fr', label: t('common.languageFr') },
  { value: 'en-US', label: t('common.languageEn') },
];

async function onSelect(nextLocale: AppLocale): Promise<void> {
  if (localeLocked.value || saving.value || locale.value === nextLocale) return;
  saving.value = true;
  try {
    await setLocale(nextLocale);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('common.switchFailed'),
      color: 'negative',
    });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.language-control {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
  padding-bottom: var(--wp-space-4);
  margin-bottom: var(--wp-space-4);
  border-bottom: 1px solid var(--wp-border);
}

.language-control__head {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.language-control__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  line-height: var(--wp-lh-tight);
  color: var(--wp-text);
}

.language-control__subtitle {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.language-control__locked-msg {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.language-control__pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
}

.language-pill {
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

.language-control--locked .language-control__pills {
  opacity: 0.7;
}
</style>
