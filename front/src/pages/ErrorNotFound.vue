<template>
  <div
    class="error-not-found"
    role="main"
  >
    <div class="error-not-found__content wp-fade-in">
      <span class="error-not-found__icon" aria-hidden="true">
        <Lucide name="map-pin-off" size="48" color="wp-accent" />
      </span>
      <p class="error-not-found__code" aria-hidden="true">{{ t('errors.notFoundCode') }}</p>
      <h1 class="error-not-found__title">{{ t('errors.notFoundTitle') }}</h1>
      <p class="error-not-found__message">{{ t('errors.notFoundMessage') }}</p>
      <router-link to="/" class="error-not-found__home">
        <Lucide name="home" size="16" color="wp-canard" />
        {{ t('errors.notFoundHome') }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

const { t } = useI18n();
</script>

<style scoped lang="scss">
.error-not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: var(--wp-space-6);
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  text-align: center;
}

.error-not-found__content {
  max-width: 30rem;
  padding: var(--wp-space-6);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
}

.error-not-found__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 4.5rem;
  height: 4.5rem;
  margin-bottom: var(--wp-space-3);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
}

.error-not-found__code {
  margin: 0 0 var(--wp-space-2);
  font-family: var(--wp-font-head);
  font-size: clamp(3rem, 14vw, 5.5rem);
  font-weight: 700;
  line-height: 1;
  color: var(--wp-text-faint);
  letter-spacing: -0.02em;
}

.error-not-found__title {
  margin: 0 0 var(--wp-space-2);
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xl);
  font-weight: 700;
  color: var(--wp-text);
}

.error-not-found__message {
  margin: 0 0 var(--wp-space-5);
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.error-not-found__home {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  min-height: 2.5rem;
  padding: 0 var(--wp-space-4);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  text-decoration: none;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-accent-strong);
  }
}
</style>
