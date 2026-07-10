<template>
  <div v-if="canShow" class="chat-model-control">
    <button
      type="button"
      class="chat-model-control__trigger"
      :title="triggerTitle"
      :aria-label="triggerTitle"
      aria-haspopup="menu"
    >
      <span class="chat-model-control__model">{{ modelLabel }}</span>
      <span
        v-if="reasoningVisible"
        class="chat-model-control__reason"
        :class="{ 'chat-model-control__reason--active': barLevel > 0 }"
      >
        <span class="chat-model-control__reason-sep" aria-hidden="true">·</span>
        <Lucide
          :name="barLevel > 0 ? 'brain' : 'sparkles'"
          size="13"
          :color="barLevel > 0 ? 'accent' : 'text-muted'"
        />
        <span class="chat-model-control__reason-label">{{ currentEffortLabel }}</span>
      </span>
      <Lucide name="chevron-down" size="12" color="text-faint" />

      <q-menu
        anchor="bottom right"
        self="top right"
        :offset="[0, 8]"
        class="chat-model-control__menu"
        transition-show="jump-down"
        transition-hide="jump-up"
      >
        <!-- Section Modèle -->
        <template v-if="modelOptions.length">
          <div class="chat-model-control__head">Modèle</div>
          <q-list dense>
            <q-item
              v-for="opt in modelOptions"
              :key="opt.model"
              clickable
              :active="isModelActive(opt.model)"
              class="chat-model-control__item"
              @click="onModelChange(opt.model)"
            >
              <q-item-section>
                <q-item-label class="chat-model-control__item-label">
                  {{ opt.label }}
                </q-item-label>
                <q-item-label
                  v-if="opt.hint"
                  class="chat-model-control__item-hint"
                  caption
                >
                  {{ opt.hint }}
                </q-item-label>
              </q-item-section>
              <q-item-section v-if="isModelActive(opt.model)" side>
                <Lucide name="check" size="xs" color="accent" />
              </q-item-section>
            </q-item>
          </q-list>
        </template>

        <q-separator v-if="modelOptions.length && reasoningVisible" class="chat-model-control__sep" />

        <!-- Section Raisonnement -->
        <template v-if="reasoningVisible">
          <div class="chat-model-control__head">Raisonnement</div>
          <q-list dense>
            <q-item
              v-for="opt in availableEffortOptions"
              :key="opt.value"
              clickable
              :active="opt.value === modelValue"
              class="chat-model-control__item"
              @click="onEffortChange(opt.value)"
            >
              <q-item-section>
                <q-item-label class="chat-model-control__item-label">
                  {{ opt.label }}
                </q-item-label>
                <q-item-label
                  v-if="hintFor(opt.value)"
                  class="chat-model-control__item-hint"
                  caption
                >
                  {{ hintFor(opt.value) }}
                </q-item-label>
              </q-item-section>
              <q-item-section v-if="opt.value === modelValue" side>
                <Lucide name="check" size="xs" color="accent" />
              </q-item-section>
            </q-item>
          </q-list>
        </template>
      </q-menu>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import {
  REASONING_EFFORT_OPTIONS,
  clampReasoningEffort,
  defaultReasoningEffort,
  supportsReasoning,
  supportedReasoningEfforts,
} from '@utils/reasoningSupport';
import {
  friendlyModelLabel,
  hasModelChoice,
  modelsForProvider,
  type ModelOption,
} from '@utils/modelCatalog';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

const props = defineProps<{
  modelValue: ReasoningEffort;
  provider: LlmProviderName | null | undefined;
  model: string | null | undefined;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ReasoningEffort];
  'update:model': [model: string];
}>();

const provider = computed(() => props.provider ?? null);
const model = computed(() => (props.model ?? '').trim());

const availableEffortOptions = computed(() => {
  if (!provider.value || !model.value) return [];
  const supported = supportedReasoningEfforts(provider.value, model.value);
  return REASONING_EFFORT_OPTIONS.filter((opt) => supported.includes(opt.value));
});

const reasoningVisible = computed(() => {
  if (!provider.value || !model.value) return false;
  return supportsReasoning(provider.value, model.value) && availableEffortOptions.value.length > 1;
});

const canShow = computed(() => {
  if (!provider.value) return false;
  return hasModelChoice(provider.value) || reasoningVisible.value;
});

const modelLabel = computed(() => {
  if (!provider.value) return model.value || 'Modèle';
  return friendlyModelLabel(provider.value, model.value);
});

const currentEffortLabel = computed(() => {
  const match = REASONING_EFFORT_OPTIONS.find((opt) => opt.value === props.modelValue);
  return match?.label ?? 'Aucun';
});

const triggerTitle = computed(() =>
  reasoningVisible.value
    ? `Modèle : ${modelLabel.value} · Raisonnement : ${currentEffortLabel.value}`
    : `Modèle : ${modelLabel.value}`,
);

const EFFORT_HINTS: Record<ReasoningEffort, string> = {
  none: 'Réponse directe, sans réflexion',
  low: 'Réflexion rapide',
  medium: 'Réflexion équilibrée',
  high: 'Réflexion approfondie',
};

function hintFor(effort: ReasoningEffort): string {
  return EFFORT_HINTS[effort] ?? '';
}

function effortToLevel(effort: ReasoningEffort): number {
  switch (effort) {
    case 'low':
      return 1;
    case 'medium':
      return 2;
    case 'high':
      return 3;
    default:
      return 0;
  }
}

const barLevel = computed(() => effortToLevel(props.modelValue));

/** Options de modèles présentées : catalogue + modèle courant s'il n'y figure pas. */
const modelOptions = computed<ModelOption[]>(() => {
  if (!provider.value) return [];
  const list = modelsForProvider(provider.value);
  if (!model.value) return list;
  const currentLower = model.value.toLowerCase();
  const inList = list.some((m) => m.model.toLowerCase() === currentLower);
  if (inList) return list;
  return [
    {
      model: model.value,
      label: friendlyModelLabel(provider.value, model.value),
      hint: 'Modèle actuel',
    },
    ...list,
  ];
});

function isModelActive(modelId: string): boolean {
  return model.value.toLowerCase() === modelId.toLowerCase();
}

function onModelChange(modelId: string): void {
  if (!provider.value || isModelActive(modelId)) return;
  // On adapte le niveau de raisonnement au nouveau modèle (valeur par défaut
  // supportée) avant de changer, pour ne pas laisser d'effort invalide.
  const nextEffort = defaultReasoningEffort(provider.value, modelId);
  emit('update:modelValue', nextEffort);
  emit('update:model', modelId);
}

function onEffortChange(effort: ReasoningEffort): void {
  emit('update:modelValue', effort);
}

// Si le modèle change (changement global, session chargée avec un effort
// devenu invalide…), on ramène la valeur à un effort supporté pour éviter
// l'erreur 400 du provider.
watch(
  () => [props.provider, props.model] as const,
  () => {
    if (!provider.value || !model.value) return;
    const clamped = clampReasoningEffort(provider.value, model.value, props.modelValue);
    if (clamped !== props.modelValue) {
      emit('update:modelValue', clamped);
    }
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.chat-model-control {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.chat-model-control__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 8px;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-pill);
  cursor: pointer;
  color: var(--wp-text);
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-3);
  }
}

.chat-model-control__model {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-model-control__reason {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--wp-text-muted);

  &--active {
    color: var(--wp-accent-strong);
  }
}

.chat-model-control__reason-sep {
  color: var(--wp-text-faint);
  margin-right: 1px;
}

.chat-model-control__reason-label {
  font-size: var(--wp-fs-xs);
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

/* Menu compact */
.chat-model-control__menu {
  min-width: 240px;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
  padding: 4px;
}

.chat-model-control__head {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-text-faint);
  padding: 6px 8px;
}

.chat-model-control__sep {
  margin: 4px 0;
}

.chat-model-control__item {
  min-height: 40px;
  padding: 6px 8px;
  border-radius: var(--wp-r-sm);
  color: var(--wp-text);

  &:hover {
    background: var(--wp-surface-2);
  }

  &.q-item--active {
    background: var(--wp-accent-soft);
  }
}

.chat-model-control__item-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: 1.2;
}

.chat-model-control__item-hint {
  font-size: 0.72rem;
  color: var(--wp-text-faint);
  line-height: 1.25;
  margin-top: 2px;
}
</style>
