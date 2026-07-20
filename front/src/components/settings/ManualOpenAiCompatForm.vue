<template>
  <div class="manual-openai-form">
    <q-input
      ref="baseUrlInputRef"
      v-model="baseUrl"
      :label="t('settings.engine.manualBaseUrl')"
      outlined
      dense
      class="manual-openai-form__field"
    />
    <q-input
      v-model="apiKey"
      :label="t('settings.engine.manualApiKey')"
      outlined
      dense
      :type="showKey ? 'text' : 'password'"
      class="manual-openai-form__field"
    >
      <template #append>
        <button type="button" class="reveal-btn" @click="showKey = !showKey">
          <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
        </button>
      </template>
    </q-input>
    <q-input
      v-model="model"
      :label="t('settings.engine.manualModel')"
      outlined
      dense
      class="manual-openai-form__field"
    />
    <p class="manual-openai-form__hint">{{ t('settings.engine.manualHint') }}</p>
    <button
      type="button"
      class="manual-openai-form__submit"
      :disabled="saving || !canSubmit"
      @click="onActivate"
    >
      {{ saving ? t('settings.engine.manualSaving') : t('settings.engine.manualActivate') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import type { QInput } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useCloud } from '@composables/useCloud';
import type { ProviderSet } from '@composables/useDesktop.types';
import { ProviderSetNotReadyError } from '@utils/providerSetErrors';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import { emptyCustomSet, newCustomSetId } from '@utils/providerSets';

const emit = defineEmits<{
  activated: [setId: string];
}>();

const { t } = useI18n();
const { createSet, setActiveSet } = useAppSettings();
const { providerReadiness } = useCloud();

const baseUrl = ref('');
const apiKey = ref('');
const model = ref('gpt-4o-mini');
const showKey = ref(false);
const saving = ref(false);
const baseUrlInputRef = ref<InstanceType<typeof QInput> | null>(null);

const canSubmit = computed(
  () => Boolean(baseUrl.value.trim() && apiKey.value.trim() && model.value.trim()),
);

function buildSet(): ProviderSet {
  const id = newCustomSetId();
  const template = emptyCustomSet();
  return {
    ...template,
    id,
    name: t('settings.engine.manualName'),
    description: t('settings.engine.manualDescription'),
    badges: [],
    chat: {
      provider: 'openai_compat',
      model: model.value.trim(),
      baseUrl: baseUrl.value.trim(),
      apiKey: apiKey.value.trim(),
      reasoning: 'auto',
    },
    embeddings: null,
    ocr: null,
    vision: { mode: 'none' },
    capabilities: {
      reasoning: 'low',
      vision: false,
      tools: true,
      webSearch: false,
    },
    isDefault: false,
    isBuiltin: false,
  };
}

async function onActivate(): Promise<void> {
  if (!baseUrl.value.trim()) {
    Notify.create({
      message: t('errors.baseUrlMissing'),
      color: 'warning',
    });
    baseUrlInputRef.value?.focus();
    return;
  }
  if (!apiKey.value.trim()) {
    Notify.create({
      message: t('errors.apiKeyMissing'),
      color: 'warning',
    });
    return;
  }
  if (!model.value.trim()) {
    Notify.create({
      message: t('settings.engine.manualModelRequired'),
      color: 'warning',
    });
    return;
  }

  saving.value = true;
  try {
    const set = buildSet();
    await createSet(set);
    await setActiveSet(set.id, { cloud: providerReadiness.value });
    emit('activated', set.id);
  } catch (err) {
    if (err instanceof ProviderSetNotReadyError) {
      Notify.create({
        message: chatErrorMessageForReadiness(err.reason),
        color: 'warning',
      });
      return;
    }
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped lang="scss">
.manual-openai-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manual-openai-form__field {
  width: 100%;
}

.manual-openai-form__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.manual-openai-form__submit {
  align-self: flex-start;
  padding: 8px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.reveal-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  padding: 2px;
}
</style>
