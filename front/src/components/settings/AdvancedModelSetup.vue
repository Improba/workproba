<template>
  <section class="advanced-setup">
    <div class="advanced-setup__preferences">
      <h3 class="advanced-setup__preferences-title">{{ t('settings.advancedAgentPrefs') }}</h3>
      <q-toggle
        :model-value="confirmBeforeWrite"
        :disable="settingsLocked || savingConfirm"
        :label="t('settings.confirmBeforeWriteLabel')"
        @update:model-value="onConfirmBeforeWrite"
      />
      <p class="advanced-setup__preferences-hint">{{ t('settings.confirmBeforeWriteHint') }}</p>
    </div>

    <div class="advanced-setup__toolbar">
      <button type="button" class="advanced-setup__add" :disabled="formOpen" @click="onAddNew">
        <Lucide name="plus" size="16" color="wp-canard" />
        {{ t('settings.advancedAddSet') }}
      </button>
    </div>

    <div v-if="sets.length === 0 && !formOpen" class="advanced-setup__empty">
      <p>{{ t('settings.advancedNoSets') }}</p>
    </div>

    <div v-else class="advanced-setup__list">
      <article
        v-for="set in sets"
        :key="set.id"
        class="set-card"
        :class="{ 'set-card--active': set.id === activeSetId }"
      >
        <div class="set-card__head">
          <div class="set-card__title">
            <Lucide name="cpu" size="16" color="accent" />
            <span>{{ set.name }}</span>
          </div>
          <div class="set-card__badges">
            <span v-if="set.id === activeSetId" class="set-badge set-badge--active">
              {{ t('settings.advancedSetActive') }}
            </span>
            <span v-if="isCloudSet(set) && !isEnrolled" class="set-badge set-badge--warn">
              {{ t('settings.engine.notEnrolled') }}
            </span>
            <span v-if="set.isBuiltin" class="set-badge">{{ t('settings.advancedSetBuiltin') }}</span>
            <span
              v-if="set.id === 'workproba-cloud'"
              class="set-badge set-badge--recommended"
            >
              {{ t('settings.badgeRecommended') }}
            </span>
          </div>
        </div>

        <p class="set-card__desc">{{ localizedSetDescription(set, t) }}</p>
        <p
          v-if="cloudReadinessHint(set)"
          class="set-card__readiness"
          role="status"
        >
          {{ cloudReadinessHint(set) }}
        </p>

        <div class="set-card__caps">
          <span v-for="cap in capabilityLabels(set, 'advanced', t)" :key="cap" class="set-cap">{{ cap }}</span>
        </div>

        <dl class="set-card__meta">
          <div><dt>{{ t('settings.advancedSetChat') }}</dt><dd>{{ set.chat.provider }}{{ t('settings.advancedSeparator') }}{{ set.chat.model }}</dd></div>
          <div>
            <dt>{{ t('settings.advancedSetEmbeddings') }}</dt>
            <dd>{{ set.embeddings ? `${set.embeddings.provider}${t('settings.advancedSeparator')}${set.embeddings.model}` : t('settings.advancedEmptyValue') }}</dd>
          </div>
          <div>
            <dt>{{ t('settings.advancedSetOcr') }}</dt>
            <dd>{{ set.ocr ? `${set.ocr.provider} (${set.ocr.mode})` : t('settings.advancedNone') }}</dd>
          </div>
          <div>
            <dt>{{ t('settings.advancedSetVision') }}</dt>
            <dd>{{ set.vision.mode }}</dd>
          </div>
        </dl>

        <div class="set-card__actions">
          <button
            type="button"
            class="ghost-btn"
            :class="{ 'ghost-btn--on': set.id === activeSetId }"
            @click="onSetActiveClick(set)"
          >
            {{ setActiveCtaLabel(set) }}
          </button>
          <button type="button" class="ghost-btn" @click="onEdit(set)">
            <Lucide name="pencil" size="14" color="text" /> {{ t('settings.advancedEdit') }}
          </button>
          <button type="button" class="ghost-btn" :disabled="testingId === set.id" @click="onTestAll(set)">
            <Lucide name="plug-zap" size="14" color="text" />
            {{ testingId === set.id ? t('settings.advancedTesting') : t('settings.advancedTest') }}
          </button>
          <button
            v-if="!set.isBuiltin"
            type="button"
            class="ghost-btn"
            :disabled="set.id === activeSetId"
            @click="onDelete(set)"
          >
            <Lucide name="trash-2" size="14" color="danger" /> {{ t('settings.advancedDelete') }}
          </button>
        </div>

        <div v-if="testResults[set.id]" class="set-card__tests">
          <p :class="{ ok: testResults[set.id].chat.ok }">
            {{ t('settings.advancedTestChat') }}: {{ testResults[set.id].chat.detail || (testResults[set.id].chat.ok ? 'OK' : 'KO') }}
          </p>
          <p :class="{ ok: testResults[set.id].embeddings.ok }">
            {{ t('settings.advancedTestEmbeddings') }}: {{ testResults[set.id].embeddings.detail || (testResults[set.id].embeddings.ok ? 'OK' : 'KO') }}
          </p>
          <p :class="{ ok: testResults[set.id].ocr.ok }">
            {{ t('settings.advancedTestOcr') }}: {{ testResults[set.id].ocr.detail || (testResults[set.id].ocr.ok ? 'OK' : 'KO') }}
          </p>
          <p :class="{ ok: testResults[set.id].vision.ok }">
            {{ t('settings.advancedTestVision') }}: {{ testResults[set.id].vision.detail || (testResults[set.id].vision.ok ? 'OK' : 'KO') }}
          </p>
        </div>
      </article>
    </div>

    <div v-if="formOpen" class="advanced-setup__form">
      <h3 class="advanced-setup__form-title">{{ editing ? t('settings.advancedEdit') : t('settings.advancedAddSet') }}</h3>
      <div class="advanced-setup__row">
        <q-input v-model="form.name" :label="t('settings.advancedFieldLabel')" outlined dense class="advanced-setup__field" />
        <q-input v-model="form.description" :label="t('settings.advancedDescription')" outlined dense class="advanced-setup__field" />
      </div>
      <div class="advanced-setup__row">
        <q-select
          v-model="form.chat.provider"
          :options="providerOptions"
          :label="t('settings.advancedProviderLabel')"
          outlined dense emit-value map-options class="advanced-setup__field"
        />
        <q-input v-model="form.chat.model" :label="t('settings.advancedChatModel')" outlined dense class="advanced-setup__field" />
        <q-input v-model="form.chat.baseUrl" :label="t('settings.advancedBaseUrl')" outlined dense class="advanced-setup__field" />
      </div>
      <div class="advanced-setup__row">
        <q-input
          v-model="form.chat.apiKey"
          :label="t('settings.advancedApiKey')"
          outlined dense :type="showKey ? 'text' : 'password'" class="advanced-setup__field"
        />
        <q-select
          v-model="form.chat.reasoning"
          :options="reasoningOptions"
          :label="t('settings.advancedReasoning')"
          outlined dense emit-value map-options class="advanced-setup__field"
        />
      </div>
      <div class="advanced-setup__row">
        <q-input v-model="form.embeddings.provider" :label="t('settings.advancedProviderLabel') + ' (embeddings)'" outlined dense class="advanced-setup__field" />
        <q-input v-model="form.embeddings.model" :label="t('settings.advancedEmbeddingModel')" outlined dense class="advanced-setup__field" />
        <q-input v-model="form.embeddings.baseUrl" :label="t('settings.advancedEmbeddingBaseUrl')" outlined dense class="advanced-setup__field" />
      </div>
      <div class="advanced-setup__row">
        <q-select v-model="form.ocr.provider" :options="ocrProviderOptions" :label="t('settings.advancedOcrProvider')" outlined dense emit-value map-options class="advanced-setup__field" />
        <q-select v-model="form.ocr.mode" :options="ocrModeOptions" :label="t('settings.advancedOcrMode')" outlined dense emit-value map-options class="advanced-setup__field" />
        <q-select v-model="form.vision.mode" :options="visionModeOptions" :label="t('settings.advancedSetVision')" outlined dense emit-value map-options class="advanced-setup__field" />
      </div>
      <div class="advanced-setup__row">
        <q-toggle v-model="form.capabilities.vision" :label="t('settings.advancedCapVision')" />
        <q-toggle v-model="form.capabilities.tools" :label="t('settings.advancedCapTools')" />
        <q-select v-model="form.capabilities.reasoning" :options="capReasoningOptions" :label="t('settings.advancedCapReasoningLevel')" outlined dense emit-value map-options class="advanced-setup__field" />
      </div>
      <div class="advanced-setup__form-actions">
        <q-btn flat :label="t('common.cancel')" @click="onCancelForm" />
        <q-btn unelevated color="primary" :label="t('common.save')" :disable="!form.name || !form.chat.model" @click="onSaveForm" />
      </div>
    </div>

    <EnrollCloudModal v-model="enrollModalOpen" @enrolled="onCloudEnrolled" />
    <CloudLoginModal
      v-model="cloudLoginModalOpen"
      @enrolled="onCloudLoggedIn"
      @open-invitation="onOpenCloudInvitation"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import { useAppSettings, testSet, type ProviderSetTestResult } from '@composables/useAppSettings';
import type { ProviderSet, LlmProviderName } from '@composables/useDesktop.types';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useCloud } from '@composables/useCloud';
import { ProviderSetNotReadyError } from '@utils/providerSetErrors';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import {
  capabilityLabels,
  cloneProviderSet,
  emptyCustomSet,
  localizedSetDescription,
  WORKPROBA_CLOUD_BUILTIN_SET,
} from '@utils/providerSets';

const { sets, settings, setActiveSet, createSet, updateSet, deleteSet, confirmBeforeWrite, setConfirmBeforeWrite, settingsLocked } = useAppSettings();
const { getPluginDataDir } = usePlugins();
const { providerReadiness, isEnrolled, init: initCloud, refreshQuota } = useCloud();
const { t } = useI18n();

const formOpen = ref(false);
const editing = ref<ProviderSet | null>(null);
const showKey = ref(false);
const testingId = ref<string | null>(null);
const savingConfirm = ref(false);
const enrollModalOpen = ref(false);
const cloudLoginModalOpen = ref(false);
const testResults = reactive<Record<string, ProviderSetTestResult>>({});

const activeSetId = computed(() => settings.value.activeSetId ?? null);

function isCloudSet(set: ProviderSet): boolean {
  return set.id === WORKPROBA_CLOUD_BUILTIN_SET.id;
}

function cloudReadinessHint(set: ProviderSet): string {
  if (!isCloudSet(set) || isEnrolled.value) return '';
  return chatErrorMessageForReadiness('cloud_not_enrolled');
}

function setActiveCtaLabel(set: ProviderSet): string {
  if (isCloudSet(set) && !isEnrolled.value) {
    return t('settings.engine.linkDevice');
  }
  if (set.id === activeSetId.value) {
    return t('settings.advancedSetActive');
  }
  return t('settings.engine.useThisEngine');
}

function notifyActivationError(err: unknown): void {
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
}

async function activateSet(id: string): Promise<void> {
  try {
    await setActiveSet(id, { cloud: providerReadiness.value });
  } catch (err) {
    notifyActivationError(err);
  }
}

function onSetActiveClick(set: ProviderSet): void {
  if (isCloudSet(set) && !isEnrolled.value) {
    cloudLoginModalOpen.value = true;
    return;
  }
  void activateSet(set.id);
}

async function onCloudEnrolled(): Promise<void> {
  await refreshQuota();
  await activateSet(WORKPROBA_CLOUD_BUILTIN_SET.id);
}

async function onCloudLoggedIn(): Promise<void> {
  await refreshQuota();
  cloudLoginModalOpen.value = false;
  await activateSet(WORKPROBA_CLOUD_BUILTIN_SET.id);
}

function onOpenCloudInvitation(): void {
  cloudLoginModalOpen.value = false;
  enrollModalOpen.value = true;
}

onMounted(() => {
  void initCloud();
});

async function onConfirmBeforeWrite(enabled: boolean): Promise<void> {
  if (settingsLocked.value || savingConfirm.value) return;
  savingConfirm.value = true;
  try {
    await setConfirmBeforeWrite(enabled);
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.confirmBeforeWriteChangeFailed'),
      color: 'negative',
    });
  } finally {
    savingConfirm.value = false;
  }
}

const providerOptions = [
  { label: 'Mistral', value: 'mistral' },
  { label: 'OpenAI', value: 'openai' },
  { label: 'OpenAI-compat', value: 'openai_compat' },
  { label: 'Ollama', value: 'ollama' },
  { label: 'vLLM', value: 'vllm' },
  { label: 'Anthropic', value: 'anthropic' },
];

const reasoningOptions = ['auto', 'none', 'low', 'medium', 'high'].map((v) => ({ label: v, value: v }));
const ocrProviderOptions = [
  { label: 'mistral', value: 'mistral' },
  { label: 'docling', value: 'docling' },
];
const ocrModeOptions = [
  { label: 'auto', value: 'auto' },
  { label: 'none', value: 'none' },
];
const visionModeOptions = [
  { label: 'chat', value: 'chat' },
  { label: 'none', value: 'none' },
];
const capReasoningOptions = [
  { label: 'low', value: 'low' },
  { label: 'medium', value: 'medium' },
  { label: 'high', value: 'high' },
];

interface SetForm {
  id: string;
  name: string;
  description: string;
  chat: {
    provider: LlmProviderName;
    model: string;
    baseUrl: string;
    apiKey: string;
    reasoning: string;
  };
  embeddings: {
    provider: LlmProviderName;
    model: string;
    baseUrl: string;
  };
  ocr: { provider: 'mistral' | 'docling'; mode: 'auto' | 'none' };
  vision: { mode: 'chat' | 'none' };
  capabilities: { reasoning: 'low' | 'medium' | 'high'; vision: boolean; tools: boolean };
  isBuiltin: boolean;
}

const form = reactive<SetForm>(formFromSet(emptyCustomSet()));

function formFromSet(set: ProviderSet): SetForm {
  return {
    id: set.id,
    name: set.name,
    description: set.description,
    chat: {
      provider: set.chat.provider,
      model: set.chat.model,
      baseUrl: set.chat.baseUrl ?? '',
      apiKey: set.chat.apiKey ?? '',
      reasoning: set.chat.reasoning ?? 'auto',
    },
    embeddings: {
      provider: set.embeddings?.provider ?? 'mistral',
      model: set.embeddings?.model ?? '',
      baseUrl: set.embeddings?.baseUrl ?? '',
    },
    ocr: {
      provider: set.ocr?.provider ?? 'mistral',
      mode: set.ocr?.mode ?? 'auto',
    },
    vision: { mode: set.vision.mode },
    capabilities: { ...set.capabilities },
    isBuiltin: set.isBuiltin,
  };
}

function formToSet(): ProviderSet {
  return {
    id: form.id,
    name: form.name.trim(),
    description: form.description.trim(),
    badges: editing.value?.badges ?? [],
    chat: {
      provider: form.chat.provider,
      model: form.chat.model.trim(),
      baseUrl: form.chat.baseUrl.trim() || null,
      apiKey: form.chat.apiKey.trim() || null,
      reasoning: form.chat.reasoning as ProviderSet['chat']['reasoning'],
    },
    embeddings: form.embeddings.model.trim()
      ? {
          provider: form.embeddings.provider,
          model: form.embeddings.model.trim(),
          baseUrl: form.embeddings.baseUrl.trim() || null,
          apiKey: form.chat.apiKey.trim() || null,
        }
      : null,
    ocr: { provider: form.ocr.provider, mode: form.ocr.mode },
    vision: { mode: form.vision.mode },
    capabilities: { ...form.capabilities },
    isDefault: editing.value?.isDefault ?? false,
    isBuiltin: form.isBuiltin,
  };
}

function onAddNew(): void {
  editing.value = null;
  Object.assign(form, formFromSet(emptyCustomSet()));
  formOpen.value = true;
}

function onEdit(set: ProviderSet): void {
  editing.value = set;
  Object.assign(form, formFromSet(set));
  formOpen.value = true;
}

function onCancelForm(): void {
  formOpen.value = false;
  editing.value = null;
}

async function onSaveForm(): Promise<void> {
  const next = formToSet();
  try {
    if (editing.value) {
      await updateSet(next);
    } else {
      await createSet(next);
    }
    onCancelForm();
    Notify.create({ message: t('settings.advancedSetSaved'), color: 'positive', timeout: 1500 });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
  }
}

async function onDelete(set: ProviderSet): Promise<void> {
  try {
    await deleteSet(set.id);
    delete testResults[set.id];
    Notify.create({ message: t('settings.advancedSetDeleted'), color: 'positive', timeout: 1500 });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.advancedCannotDeleteBuiltin'),
      color: 'negative',
    });
  }
}

async function onTestAll(set: ProviderSet): Promise<void> {
  testingId.value = set.id;
  try {
    const cloudPluginDataDir =
      set.authMode === 'device_bearer'
        ? await getPluginDataDir(CLOUD_PLUGIN_ID)
        : null;
    testResults[set.id] = await testSet(cloneProviderSet(set), { cloudPluginDataDir });
  } catch (err) {
    testResults[set.id] = {
      chat: { ok: false, detail: err instanceof Error ? err.message : 'error' },
      embeddings: { ok: false },
      ocr: { ok: false, supported: false },
      vision: { ok: false, supported: false },
    };
  } finally {
    testingId.value = null;
  }
}
</script>

<style scoped lang="scss">
.advanced-setup {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.advanced-setup__preferences {
  padding: 12px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.advanced-setup__preferences-title {
  margin: 0 0 8px;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.advanced-setup__preferences-hint {
  margin: 6px 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  max-width: 56ch;
}

.advanced-setup__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.advanced-setup__guided-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}

.advanced-setup__add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.advanced-setup__empty {
  padding: 12px 4px;
  color: var(--wp-text-faint);
  font-size: 14px;
}

.advanced-setup__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.set-card {
  border: 1px solid var(--wp-border);
  border-left: 3px solid transparent;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.set-card--active {
  border-left-color: var(--wp-accent);
}

.set-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.set-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: 14px;
}

.set-card__badges {
  display: flex;
  gap: 6px;
}

.set-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.set-badge--active {
  background: var(--wp-accent-soft);
  color: var(--wp-accent);
}

.set-badge--warn {
  background: var(--wp-warning-soft, var(--wp-surface-2));
  color: var(--wp-warning, var(--wp-danger));
}

.set-badge--recommended {
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
}

.set-card__readiness {
  margin: 0;
  font-size: 12px;
  line-height: var(--wp-lh-normal);
  color: var(--wp-danger);
}

.set-card__desc {
  margin: 0;
  font-size: 13px;
  color: var(--wp-text-muted);
}

.set-card__caps {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.set-cap {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-faint);
  font-family: var(--wp-font-mono, monospace);
}

.set-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 6px 16px;
  margin: 0;
}

.set-card__meta div {
  display: flex;
  flex-direction: column;
}

.set-card__meta dt {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--wp-text-faint);
}

.set-card__meta dd {
  margin: 0;
  font-size: 13px;
  color: var(--wp-text);
}

.set-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: 12px;
  cursor: pointer;
}

.ghost-btn--on {
  border-color: var(--wp-accent);
  background: var(--wp-accent-soft);
}

.set-card__tests {
  font-size: 12px;
  color: var(--wp-danger);

  p.ok {
    color: var(--wp-success);
  }
}

.advanced-setup__form {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--wp-border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.advanced-setup__form-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: 14px;
  font-weight: 700;
}

.advanced-setup__row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.advanced-setup__field {
  flex: 1;
  min-width: 160px;
}

.advanced-setup__form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
