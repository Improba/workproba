<template>
  <div v-if="canShow" class="chat-model-menu-content">
    <template v-if="modelOptions.length">
      <div class="chat-model-menu-content__head">{{ t('chat.modelControlModel') }}</div>
      <q-list dense>
        <q-item
          v-for="opt in modelOptions"
          :key="opt.model"
          clickable
          :active="isModelActive(opt.model)"
          class="chat-model-menu-content__item"
          @click="onModelChange(opt.model)"
        >
          <q-item-section>
            <q-item-label class="chat-model-menu-content__item-label">
              {{ opt.label }}
            </q-item-label>
            <q-item-label
              v-if="opt.hint"
              class="chat-model-menu-content__item-hint"
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

    <q-separator
      v-if="modelOptions.length && reasoningVisible"
      class="chat-model-menu-content__sep"
    />

    <template v-if="reasoningVisible">
      <div class="chat-model-menu-content__head">{{ t('chat.modelControlReasoning') }}</div>
      <q-list dense>
        <q-item
          v-for="opt in availableEffortOptions"
          :key="opt.value"
          clickable
          :active="opt.value === modelValue"
          class="chat-model-menu-content__item"
          @click="onEffortChange(opt.value)"
        >
          <q-item-section>
            <q-item-label class="chat-model-menu-content__item-label">
              {{ opt.label }}
            </q-item-label>
            <q-item-label
              v-if="hintFor(opt.value)"
              class="chat-model-menu-content__item-hint"
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
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import type { LlmProviderName, ProviderSet } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import { REASONING_EFFORT_OPTIONS } from '@utils/reasoningSupport';
import {
  clampReasoningEffortForSet,
  defaultReasoningEffortForSet,
  hasSetModelChoice,
  modelsForSet,
  supportsReasoningForSet,
  supportedReasoningEffortsForSet,
} from '@utils/providerSetModels';
import {
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

const { t } = useI18n();

const props = defineProps<{
  modelValue: ReasoningEffort;
  provider: LlmProviderName | null | undefined;
  model: string | null | undefined;
  providerSet?: ProviderSet | null;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ReasoningEffort];
  'update:model': [model: string];
}>();

const provider = computed(() => props.provider ?? null);
const model = computed(() => (props.model ?? '').trim());

const availableEffortOptions = computed(() => {
  if (!provider.value || !model.value) return [];
  const supported = props.providerSet
    ? supportedReasoningEffortsForSet(props.providerSet, model.value)
    : supportedReasoningEfforts(provider.value, model.value);
  return REASONING_EFFORT_OPTIONS.filter((opt) => supported.includes(opt.value));
});

const reasoningVisible = computed(() => {
  if (!provider.value || !model.value) return false;
  const supports = props.providerSet
    ? supportsReasoningForSet(props.providerSet, model.value)
    : supportsReasoning(provider.value, model.value);
  return supports && availableEffortOptions.value.length > 1;
});

const canShow = computed(() => {
  if (!provider.value) return false;
  if (props.providerSet) {
    return hasSetModelChoice(props.providerSet) || reasoningVisible.value;
  }
  return hasModelChoice(provider.value) || reasoningVisible.value;
});

const EFFORT_HINTS: Record<ReasoningEffort, string> = {
  none: 'Réponse rapide, sans trace de réflexion visible',
  low: 'Réflexion rapide',
  medium: 'Réflexion équilibrée',
  high: 'Réflexion approfondie visible',
};

function hintFor(effort: ReasoningEffort): string {
  return EFFORT_HINTS[effort] ?? '';
}

const modelOptions = computed<ModelOption[]>(() => {
  if (!provider.value) return [];
  const list = props.providerSet
    ? modelsForSet(props.providerSet)
    : modelsForProvider(provider.value);
  if (!model.value) return list;
  const currentLower = model.value.toLowerCase();
  const inList = list.some((m) => m.model.toLowerCase() === currentLower);
  if (inList) return list;
  return [
    {
      model: model.value,
      label: friendlyModelLabel(provider.value, model.value, props.providerSet),
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
  const nextEffort = props.providerSet
    ? defaultReasoningEffortForSet(props.providerSet, modelId)
    : defaultReasoningEffort(provider.value, modelId);
  emit('update:modelValue', nextEffort);
  emit('update:model', modelId);
}

function onEffortChange(effort: ReasoningEffort): void {
  emit('update:modelValue', effort);
}

watch(
  () => [props.provider, props.model, props.providerSet] as const,
  () => {
    if (!provider.value || !model.value) return;
    const clamped = props.providerSet
      ? clampReasoningEffortForSet(props.providerSet, model.value, props.modelValue)
      : clampReasoningEffort(provider.value, model.value, props.modelValue);
    if (clamped !== props.modelValue) {
      emit('update:modelValue', clamped);
    }
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.chat-model-menu-content__head {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-text-faint);
  padding: 6px 8px;
}

.chat-model-menu-content__sep {
  margin: 4px 0;
}

.chat-model-menu-content__item {
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

.chat-model-menu-content__item-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: 1.2;
}

.chat-model-menu-content__item-hint {
  font-size: 0.72rem;
  color: var(--wp-text-faint);
  line-height: 1.25;
  margin-top: 2px;
}
</style>
