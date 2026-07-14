<template>
  <div
    class="plan-card"
    data-testid="plan-card"
    role="region"
    :aria-label="t('chat.plan.proposed')"
  >
    <header class="plan-card__header">
      <Lucide name="list-checks" size="16" color="accent" />
      <h3 class="plan-card__title">{{ t('chat.plan.proposed') }}</h3>
    </header>

    <p v-if="plan.rationale" class="plan-card__rationale">
      <span class="plan-card__label">{{ t('chat.plan.rationale') }}</span>
      {{ plan.rationale }}
    </p>

    <ol class="plan-card__steps" role="list">
      <li
        v-for="(step, index) in plan.steps"
        :key="`${step.tool}-${index}`"
        class="plan-card__step"
      >
        <span class="plan-card__step-index" aria-hidden="true">{{ index + 1 }}</span>
        <div class="plan-card__step-body">
          <p class="plan-card__step-summary">{{ step.summary }}</p>
          <p v-if="step.target" class="plan-card__step-target">
            <span class="plan-card__label">{{ t('chat.plan.target') }}</span>
            {{ step.target }}
          </p>
        </div>
      </li>
    </ol>

    <div class="plan-card__actions">
      <button
        type="button"
        class="plan-card__btn plan-card__btn--deny"
        :disabled="busy"
        @click="emit('reject')"
      >
        {{ busy ? t('common.inProgress') : t('chat.plan.refuse') }}
      </button>
      <button
        type="button"
        class="plan-card__btn plan-card__btn--approve"
        :disabled="busy"
        @click="emit('approve')"
      >
        {{ busy ? t('common.inProgress') : t('chat.plan.approve') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import type { ChatProposedPlan } from '#types';

defineProps<{
  plan: ChatProposedPlan;
  busy?: boolean;
}>();

const emit = defineEmits<{
  approve: [];
  reject: [];
}>();

const { t } = useI18n();
</script>

<style scoped lang="scss">
.plan-card {
  width: 100%;
  margin: var(--wp-space-2) 0 0;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--wp-border-strong);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
}

.plan-card__header {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: 0.65rem;
}

.plan-card__title {
  margin: 0;
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.plan-card__label {
  font-weight: 600;
  color: var(--wp-text-muted);
}

.plan-card__rationale {
  margin: 0 0 0.75rem;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
}

.plan-card__steps {
  list-style: none;
  margin: 0 0 0.85rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.plan-card__step {
  display: flex;
  gap: 0.55rem;
  align-items: flex-start;
  padding: 0.55rem 0.65rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
}

.plan-card__step-index {
  flex: 0 0 auto;
  width: 1.35rem;
  height: 1.35rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-xs);
  font-weight: 700;
}

.plan-card__step-body {
  flex: 1;
  min-width: 0;
}

.plan-card__step-summary {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
}

.plan-card__step-target {
  margin: 0.25rem 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  word-break: break-word;
}

.plan-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.plan-card__btn {
  flex: 1 1 8rem;
  min-height: 2.5rem;
  padding: 0.55rem 1rem;
  border-radius: var(--wp-r-md);
  font-size: var(--wp-fs-base);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    opacity var(--wp-dur) var(--wp-ease);

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }
}

.plan-card__btn--deny {
  border: 1px solid var(--wp-border-strong);
  background: var(--wp-surface);
  color: var(--wp-text);

  &:not(:disabled):hover {
    background: var(--wp-surface-2);
  }
}

.plan-card__btn--approve {
  border: 1px solid var(--wp-accent);
  background: var(--wp-accent);
  color: var(--wp-canard);

  &:not(:disabled):hover {
    background: var(--wp-accent-strong);
  }
}
</style>
