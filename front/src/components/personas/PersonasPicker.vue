<template>
  <q-dialog :model-value="open" @update:model-value="(v: boolean) => emit('update:open', v)">
    <div class="personas-picker" role="dialog" :aria-label="title">
      <header class="personas-picker__head">
        <div class="personas-picker__head-text">
          <h2 class="personas-picker__title">{{ title }}</h2>
          <span
            v-if="provenance"
            class="personas-picker__provenance"
            :data-provenance="provenance"
          >
            {{ provenanceLabel }}
          </span>
        </div>
        <button
          type="button"
          class="personas-picker__close"
          :aria-label="t('common.close')"
          @click="emit('update:open', false)"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p v-if="subtitle" class="personas-picker__subtitle">{{ subtitle }}</p>

      <PersonasConfidentialityHint class="personas-picker__privacy" />

      <section v-if="loading" class="personas-picker__empty">
        {{ t('common.loading') }}
      </section>

      <section v-else-if="personas.length === 0" class="personas-picker__empty">
        <Lucide name="users" size="24" color="text-faint" />
        <p>{{ t('personas.picker.empty') }}</p>
      </section>

      <ul v-else class="personas-picker__list" role="list">
        <li v-for="persona in personas" :key="persona.id">
          <button
            type="button"
            class="personas-picker__card"
            :class="{ 'personas-picker__card--selected': selectedIds.includes(persona.id) }"
            @click="toggle(persona.id)"
          >
            <PersonaAvatar :name="persona.name" :color="persona.avatar_color" :icon="persona.avatar_icon" />
            <div class="personas-picker__info">
              <span class="personas-picker__name">{{ persona.name }}</span>
              <span class="personas-picker__role">{{ persona.role }}</span>
            </div>
            <Lucide
              v-if="selectedIds.includes(persona.id)"
              name="check"
              size="16"
              color="wp-gold"
            />
          </button>
        </li>
      </ul>

      <div v-if="showTopic" class="personas-picker__field">
        <label :for="topicInputId">{{ topicLabel }}</label>
        <textarea
          :id="topicInputId"
          v-model="topicDraft"
          class="personas-picker__textarea"
          rows="3"
          :placeholder="topicPlaceholder"
        />
      </div>

      <div v-if="showRounds" class="personas-picker__field">
        <label :for="roundsInputId">{{ t('personas.meeting.roundsLabel') }}</label>
        <input
          :id="roundsInputId"
          v-model.number="roundsDraft"
          type="number"
          min="1"
          max="5"
          class="personas-picker__input"
        />
        <p class="personas-picker__hint">{{ costHint }}</p>
      </div>

      <label v-if="showIncludeMemory" class="personas-picker__memory">
        <input v-model="includeMemoryDraft" type="checkbox" />
        <span>{{ t('personas.includeMemory') }}</span>
        <Lucide
          name="info"
          size="14"
          color="text-faint"
          :title="t('personas.includeMemoryTooltip')"
        />
      </label>

      <section v-if="estimateMode && selectedIds.length > 0" class="personas-picker__estimate">
        <p v-if="estimateLoading" class="personas-picker__estimate-loading">
          {{ t('personas.estimate.loading') }}
        </p>
        <template v-else-if="estimate">
          <p class="personas-picker__estimate-line">
            {{ t('personas.estimate.summary', {
              calls: estimate.estimated_calls,
              tokens: estimate.estimated_tokens,
            }) }}
          </p>
          <p v-if="estimate.warning" class="personas-picker__estimate-warning">
            {{ estimate.warning }}
          </p>
        </template>
      </section>

      <section v-if="confirmStep" class="personas-picker__confirm">
        <p class="personas-picker__confirm-text">{{ t('personas.estimate.confirmText') }}</p>
      </section>

      <footer class="personas-picker__foot">
        <button type="button" class="personas-picker__btn" @click="emit('update:open', false)">
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="personas-picker__btn personas-picker__btn--primary"
          :disabled="!canConfirm || busy || estimateLoading"
          @click="onConfirm"
        >
          {{ confirmButtonLabel }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useDebounceFn } from '@vueuse/core';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import PersonasConfidentialityHint from '@components/personas/PersonasConfidentialityHint.vue';
import { personaSetProvenanceLabel, usePersonas } from '@composables/usePersonas';
import type {
  PersonaInfo,
  PersonaSetProvenance,
  PersonasCostEstimate,
  PersonasEstimateMode,
} from '@services/aiSidecar';

const props = withDefaults(
  defineProps<{
    open: boolean;
    personas: PersonaInfo[];
    loading?: boolean;
    title: string;
    subtitle?: string;
    provenance?: PersonaSetProvenance | null;
    confirmLabel: string;
    showTopic?: boolean;
    topicLabel?: string;
    topicPlaceholder?: string;
    showRounds?: boolean;
    showIncludeMemory?: boolean;
    busy?: boolean;
    multiple?: boolean;
    maxSelection?: number;
    estimateMode?: PersonasEstimateMode | null;
    pluginDataDir?: string | null;
    initialPersonaIds?: string[];
    initialTopic?: string;
    initialRounds?: number;
  }>(),
  {
    loading: false,
    showTopic: true,
    showRounds: false,
    showIncludeMemory: true,
    busy: false,
    multiple: true,
    maxSelection: 5,
    estimateMode: null,
    pluginDataDir: null,
    initialPersonaIds: () => [],
    initialTopic: '',
    initialRounds: 3,
    provenance: null,
  },
);

const provenanceLabel = computed(() => personaSetProvenanceLabel(props.provenance ?? undefined));

const emit = defineEmits<{
  'update:open': [value: boolean];
  confirm: [payload: { personaIds: string[]; topic: string; rounds: number; includeMemory: boolean }];
}>();

const { t } = useI18n();
const { estimateCost } = usePersonas();

const selectedIds = ref<string[]>([]);
const topicDraft = ref('');
const roundsDraft = ref(3);
const includeMemoryDraft = ref(false);
const estimate = ref<PersonasCostEstimate | null>(null);
const estimateLoading = ref(false);
const confirmStep = ref(false);
const topicInputId = `personas-topic-${Math.random().toString(36).slice(2, 7)}`;
const roundsInputId = `personas-rounds-${Math.random().toString(36).slice(2, 7)}`;

function applyInitialValues(): void {
  selectedIds.value = props.initialPersonaIds?.length ? [...props.initialPersonaIds] : [];
  topicDraft.value = props.initialTopic ?? '';
  roundsDraft.value = props.initialRounds ?? 3;
  includeMemoryDraft.value = false;
  estimate.value = null;
  confirmStep.value = false;
}

const fetchEstimate = useDebounceFn(async () => {
  if (!props.estimateMode || !props.pluginDataDir || selectedIds.value.length === 0) {
    estimate.value = null;
    return;
  }
  estimateLoading.value = true;
  try {
    estimate.value = await estimateCost(
      props.pluginDataDir,
      selectedIds.value,
      props.estimateMode,
      props.showRounds ? Math.min(roundsDraft.value || 3, 5) : undefined,
    );
  } finally {
    estimateLoading.value = false;
  }
}, 400);

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      applyInitialValues();
    }
  },
);

onMounted(() => {
  if (props.open) applyInitialValues();
});

watch(
  () => [props.initialPersonaIds, props.initialTopic, props.initialRounds] as const,
  () => {
    if (props.open) applyInitialValues();
  },
  { deep: true },
);

watch([selectedIds, roundsDraft, () => props.estimateMode, () => props.pluginDataDir], () => {
  confirmStep.value = false;
  void fetchEstimate();
}, { deep: true });

const canConfirm = computed(() => {
  if (selectedIds.value.length === 0) return false;
  if (props.showTopic && !topicDraft.value.trim()) return false;
  return true;
});

const costHint = computed(() => {
  const count = selectedIds.value.length;
  const rounds = Math.min(roundsDraft.value || 3, 5);
  return t('personas.meeting.costHint', { personas: count, rounds });
});

const confirmButtonLabel = computed(() => {
  if (props.busy) return t('common.inProgress');
  if (confirmStep.value) return t('personas.estimate.confirm');
  if (props.estimateMode && estimate.value?.warning) return t('personas.estimate.confirmWithWarning');
  return props.confirmLabel;
});

function toggle(id: string): void {
  if (props.multiple) {
    if (selectedIds.value.includes(id)) {
      selectedIds.value = selectedIds.value.filter((x) => x !== id);
    } else if (selectedIds.value.length < props.maxSelection) {
      selectedIds.value = [...selectedIds.value, id];
    }
  } else {
    selectedIds.value = [id];
  }
}

function onConfirm(): void {
  if (props.busy) return;
  if (props.estimateMode && estimate.value?.warning && !confirmStep.value) {
    confirmStep.value = true;
    return;
  }
  emit('confirm', {
    personaIds: [...selectedIds.value],
    topic: topicDraft.value.trim(),
    rounds: Math.min(roundsDraft.value || 3, 5),
    includeMemory: includeMemoryDraft.value,
  });
}
</script>

<style scoped lang="scss">
.personas-picker {
  width: 420px;
  max-width: 92vw;
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  padding: var(--wp-space-4);
}

.personas-picker__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--wp-space-2);
}

.personas-picker__head-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.personas-picker__provenance {
  align-self: flex-start;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);

  &[data-provenance='managed'] {
    color: var(--wp-gold);
    background: var(--wp-gold-soft);
  }
}

.personas-picker__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.personas-picker__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.personas-picker__subtitle {
  margin: 0 0 var(--wp-space-3);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.personas-picker__privacy {
  margin-bottom: var(--wp-space-3);
}

.personas-picker__empty {
  padding: var(--wp-space-4) 0;
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--wp-space-2);
}

.personas-picker__list {
  list-style: none;
  margin: 0 0 var(--wp-space-3);
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  max-height: 240px;
  overflow-y: auto;
}

.personas-picker__card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--wp-dur) var(--wp-ease), background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }

  &--selected {
    border-color: var(--wp-gold);
    background: var(--wp-gold-soft);
  }
}

.personas-picker__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.personas-picker__name {
  font-weight: 600;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-picker__role {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-picker__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  margin-bottom: var(--wp-space-3);

  label {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
}

.personas-picker__textarea,
.personas-picker__input {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);
  resize: vertical;

  &:focus {
    outline: none;
    border-color: var(--wp-gold);
  }
}

.personas-picker__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-warning, var(--wp-text-faint));
}

.personas-picker__memory {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-3);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  cursor: pointer;

  input {
    accent-color: var(--wp-gold);
  }
}

.personas-picker__estimate {
  margin-bottom: var(--wp-space-3);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
}

.personas-picker__estimate-loading,
.personas-picker__estimate-line {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-picker__estimate-warning {
  margin: var(--wp-space-1) 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-warning, var(--wp-gold));
  font-weight: 600;
}

.personas-picker__confirm {
  margin-bottom: var(--wp-space-3);
}

.personas-picker__confirm-text {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-picker__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.personas-picker__btn {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &--primary {
    background: var(--wp-gold);
    color: var(--wp-canard);
    border-color: var(--wp-gold);
    font-weight: 600;

    &:hover:not(:disabled) {
      filter: brightness(0.95);
    }
  }
}
</style>
