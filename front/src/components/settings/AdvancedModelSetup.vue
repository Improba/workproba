<template>
  <section class="advanced-setup">
    <div class="advanced-setup__toolbar">
      <button type="button" class="advanced-setup__guided-link" @click="emit('switch-to-guided')">
        Retour au mode guidé
      </button>
      <button
        type="button"
        class="advanced-setup__add"
        :disabled="editing !== null"
        @click="onAddNew"
      >
        <Lucide name="plus" size="16" color="wp-canard" />
        Ajouter un provider
      </button>
    </div>

    <q-expansion-item
      v-model="providersOpen"
      icon="dns"
      label="Providers"
      header-class="advanced-setup__accordion-head"
      default-opened
    >
      <div v-if="providers.length === 0 && editing === null" class="advanced-setup__empty">
        <p>Aucun provider configuré.</p>
      </div>

      <div v-else class="advanced-setup__list">
        <article
          v-for="entry in providers"
          :key="entry.id"
          class="provider-card"
          :class="{
            'provider-card--active-chat': entry.id === activeChatId,
            'provider-card--active-embed': entry.id === activeEmbeddingId,
          }"
        >
          <div class="provider-card__head">
            <div class="provider-card__title">
              <Lucide name="cpu" size="16" color="accent" />
              <span>{{ entry.label }}</span>
            </div>
            <div class="provider-card__badges">
              <span v-if="entry.id === activeChatId" class="provider-badge provider-badge--chat">
                Chat actif
              </span>
              <span
                v-if="entry.id === activeEmbeddingId && entry.embeddingModel"
                class="provider-badge provider-badge--embed"
              >
                Embeddings actif
              </span>
            </div>
          </div>

          <dl class="provider-card__meta">
            <div><dt>Provider</dt><dd>{{ entry.provider }}</dd></div>
            <div><dt>Modèle</dt><dd>{{ entry.model }}</dd></div>
            <div v-if="entry.baseUrl"><dt>Base URL</dt><dd>{{ entry.baseUrl }}</dd></div>
            <div><dt>Clé API</dt><dd>{{ entry.apiKey ? '••••••' + maskKey(entry.apiKey) : 'non définie' }}</dd></div>
            <div v-if="entry.embeddingModel"><dt>Embeddings</dt><dd>{{ entry.embeddingModel }}</dd></div>
          </dl>

          <div class="provider-card__actions">
            <button
              type="button"
              class="ghost-btn"
              :class="{ 'ghost-btn--on': entry.id === activeChatId }"
              @click="onSetActiveChat(entry)"
            >
              <Lucide name="message-square" size="14" :color="entry.id === activeChatId ? 'accent' : 'text'" />
              {{ entry.id === activeChatId ? 'Chat actif' : 'Pour le chat' }}
            </button>
            <button
              v-if="entry.embeddingModel"
              type="button"
              class="ghost-btn"
              :class="{ 'ghost-btn--on': entry.id === activeEmbeddingId }"
              @click="onSetActiveEmbedding(entry)"
            >
              <Lucide name="database" size="14" :color="entry.id === activeEmbeddingId ? 'success' : 'text'" />
              {{ entry.id === activeEmbeddingId ? 'Embeddings actif' : 'Pour le RAG' }}
            </button>
            <button type="button" class="ghost-btn" @click="onEdit(entry)">
              <Lucide name="pencil" size="14" color="text" /> Éditer
            </button>
            <button
              type="button"
              class="ghost-btn"
              :disabled="testingId === entry.id"
              @click="onTest(entry)"
            >
              <Lucide name="plug-zap" size="14" color="text" />
              {{ testingId === entry.id ? 'Test…' : 'Tester' }}
            </button>
            <button
              type="button"
              class="ghost-btn"
              :disabled="entry.id === activeChatId || entry.id === activeEmbeddingId"
              @click="onDelete(entry)"
            >
              <Lucide name="trash-2" size="14" color="danger" /> Supprimer
            </button>
          </div>

          <p v-if="testResults[entry.id]" class="provider-card__test" :class="{ ok: testResults[entry.id].ok }">
            <Lucide
              :name="testResults[entry.id].ok ? 'check-circle-2' : 'alert-circle'"
              size="14"
              :color="testResults[entry.id].ok ? 'success' : 'danger'"
            />
            {{ testResults[entry.id].detail }}
          </p>
        </article>
      </div>
    </q-expansion-item>

    <q-expansion-item
      v-model="modelParamsOpen"
      icon="tune"
      label="Paramètres modèle"
      header-class="advanced-setup__accordion-head"
      :disable="!formOpen"
    >
      <div v-if="!formOpen" class="advanced-setup__hint">
        Ajoutez ou éditez un provider pour configurer les paramètres modèle.
      </div>
      <div v-else class="advanced-setup__form-block">
        <div class="advanced-setup__row">
          <q-input
            v-model="form.label"
            label="Libellé"
            outlined
            dense
            class="advanced-setup__field"
          />
          <q-select
            v-model="form.provider"
            :options="providerOptions"
            label="Provider"
            outlined
            dense
            emit-value
            map-options
            class="advanced-setup__field"
            @update:model-value="onProviderPreset"
          />
        </div>
        <div class="advanced-setup__row">
          <q-input
            v-model="form.model"
            label="Modèle (chat)"
            outlined
            dense
            hint="ex. mistral-small-latest"
            class="advanced-setup__field"
          />
          <q-input
            v-model.number="form.temperature"
            type="number"
            label="Température"
            outlined
            dense
            step="0.1"
            min="0"
            max="2"
            class="advanced-setup__field"
          />
          <q-input
            v-model.number="form.maxTokens"
            type="number"
            label="Max tokens"
            outlined
            dense
            min="1"
            class="advanced-setup__field"
          />
          <q-select
            v-if="formSupportsReasoning"
            v-model="form.reasoningEffort"
            :options="reasoningEffortOptions"
            label="Raisonnement"
            outlined
            dense
            emit-value
            map-options
            class="advanced-setup__field"
          />
        </div>
        <div class="advanced-setup__row">
          <q-input
            v-model="form.embeddingModel"
            label="Modèle d'embeddings (RAG)"
            outlined
            dense
            hint="Laisser vide pour désactiver le RAG"
            class="advanced-setup__field"
          />
        </div>
      </div>
    </q-expansion-item>

    <q-expansion-item
      v-model="networkOpen"
      icon="lan"
      label="Réseau"
      header-class="advanced-setup__accordion-head"
      :disable="!formOpen"
    >
      <div v-if="!formOpen" class="advanced-setup__hint">
        Ajoutez ou éditez un provider pour configurer le réseau et les clés API.
      </div>
      <div v-else class="advanced-setup__form-block">
        <q-input
          v-model="form.baseUrl"
          label="Base URL"
          outlined
          dense
          :hint="form.provider === 'ollama' ? 'Laisser vide = local' : 'Endpoint API'"
          class="advanced-setup__field"
        />
        <q-input
          v-model="form.apiKey"
          label="Clé API"
          outlined
          dense
          :type="showKey ? 'text' : 'password'"
          class="advanced-setup__field"
          hint="Stockée localement (app-data). Peut être changée à tout moment."
        >
          <template #append>
            <button type="button" class="reveal-btn" @click="showKey = !showKey">
              <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
            </button>
          </template>
        </q-input>
        <q-input
          v-model="form.embeddingBaseUrl"
          label="Base URL embeddings"
          outlined
          dense
          hint="Par défaut = base URL du provider"
          class="advanced-setup__field"
        />
      </div>
    </q-expansion-item>

    <div v-if="formOpen" class="advanced-setup__form-actions">
      <q-btn flat label="Annuler" @click="onCancelForm" />
      <q-btn
        unelevated
        color="primary"
        label="Enregistrer"
        :disable="!form.label || !form.model"
        @click="onSaveForm"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import {
  useAppSettings,
  toChatLlmConfig,
  testLlmConfig,
  type LlmTestResult,
} from '@composables/useAppSettings';
import type { AppSettings, LlmProviderEntry, LlmProviderName } from '@composables/useDesktop.types';
import type { ReasoningEffort } from '#types';
import {
  defaultReasoningEffort,
  REASONING_EFFORT_OPTIONS,
  supportsReasoning,
} from '@utils/reasoningSupport';

const emit = defineEmits<{
  'switch-to-guided': [];
}>();

const { providers, settings, save } = useAppSettings();

const editing = ref<LlmProviderEntry | null>(null);
const formOpen = ref(false);
const showKey = ref(false);
const testingId = ref<string | null>(null);
const testResults = reactive<Record<string, LlmTestResult>>({});
const providersOpen = ref(true);
const modelParamsOpen = ref(false);
const networkOpen = ref(false);

const activeChatId = computed(() => settings.value.activeChatProviderId ?? null);
const activeEmbeddingId = computed(() => settings.value.activeEmbeddingProviderId ?? null);

const providerOptions = [
  { label: 'Mistral', value: 'mistral' },
  { label: 'OpenAI', value: 'openai' },
  { label: 'OpenAI-compat (vLLM, LM Studio…)', value: 'openai_compat' },
  { label: 'Ollama (local)', value: 'ollama' },
  { label: 'vLLM', value: 'vllm' },
  { label: 'Anthropic', value: 'anthropic' },
];

interface ProviderForm {
  id: string;
  label: string;
  provider: LlmProviderName;
  model: string;
  baseUrl: string;
  apiKey: string;
  temperature: number | null;
  maxTokens: number | null;
  reasoningEffort: ReasoningEffort | null;
  embeddingModel: string;
  embeddingBaseUrl: string;
}

const PRESETS: Record<LlmProviderName, Partial<ProviderForm>> = {
  mistral: {
    model: 'mistral-small-latest',
    baseUrl: 'https://api.mistral.ai/v1',
    embeddingModel: 'mistral-embed',
  },
  openai: { model: 'gpt-4o-mini', baseUrl: '', embeddingModel: 'text-embedding-3-small' },
  openai_compat: { model: '', baseUrl: '', embeddingModel: '' },
  ollama: { model: 'mistral', baseUrl: '', embeddingModel: 'nomic-embed-text' },
  vllm: { model: '', baseUrl: '', embeddingModel: '' },
  anthropic: { model: 'claude-3-5-sonnet-latest', baseUrl: '', embeddingModel: '' },
};

const form = reactive<ProviderForm>(emptyForm());

const reasoningEffortOptions = REASONING_EFFORT_OPTIONS;

const formSupportsReasoning = computed(() =>
  supportsReasoning(form.provider, form.model),
);

function emptyForm(): ProviderForm {
  return {
    id: '',
    label: '',
    provider: 'mistral',
    model: '',
    baseUrl: '',
    apiKey: '',
    temperature: null,
    maxTokens: null,
    reasoningEffort: null,
    embeddingModel: '',
    embeddingBaseUrl: '',
  };
}

function newId(): string {
  return `prov_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function maskKey(key: string): string {
  return key.length > 4 ? key.slice(-4) : '';
}

function onProviderPreset(value: LlmProviderName): void {
  const preset = PRESETS[value] ?? {};
  if (!form.model) form.model = preset.model ?? '';
  if (!form.baseUrl) form.baseUrl = preset.baseUrl ?? '';
  if (!form.embeddingModel) form.embeddingModel = preset.embeddingModel ?? '';
}

function openFormSections(): void {
  modelParamsOpen.value = true;
  networkOpen.value = true;
}

function onAddNew(): void {
  editing.value = null;
  Object.assign(form, emptyForm());
  onProviderPreset('mistral');
  form.provider = 'mistral';
  showKey.value = false;
  formOpen.value = true;
  openFormSections();
}

function onEdit(entry: LlmProviderEntry): void {
  editing.value = entry;
  Object.assign(form, {
    id: entry.id,
    label: entry.label,
    provider: entry.provider,
    model: entry.model,
    baseUrl: entry.baseUrl ?? '',
    apiKey: entry.apiKey ?? '',
    temperature: entry.temperature ?? null,
    maxTokens: entry.maxTokens ?? null,
    reasoningEffort:
      entry.reasoningEffort ??
      defaultReasoningEffort(entry.provider, entry.model),
    embeddingModel: entry.embeddingModel ?? '',
    embeddingBaseUrl: entry.embeddingBaseUrl ?? '',
  });
  showKey.value = false;
  formOpen.value = true;
  openFormSections();
}

function onCancelForm(): void {
  formOpen.value = false;
  editing.value = null;
  Object.assign(form, emptyForm());
  modelParamsOpen.value = false;
  networkOpen.value = false;
}

function formToEntry(): LlmProviderEntry {
  const reasoningEffort =
    form.reasoningEffort ??
    defaultReasoningEffort(form.provider, form.model);
  return {
    id: form.id || newId(),
    label: form.label.trim(),
    provider: form.provider,
    model: form.model.trim(),
    baseUrl: form.baseUrl.trim() || null,
    apiKey: form.apiKey.trim() || null,
    temperature: form.temperature ?? null,
    maxTokens: form.maxTokens ?? null,
    reasoningEffort: supportsReasoning(form.provider, form.model)
      ? reasoningEffort
      : null,
    extraHeaders: {},
    embeddingModel: form.embeddingModel.trim() || null,
    embeddingBaseUrl: form.embeddingBaseUrl.trim() || null,
  };
}

async function persist(next: AppSettings): Promise<void> {
  await save(next);
}

async function onSaveForm(): Promise<void> {
  const entry = formToEntry();
  const current = settings.value;
  const nextProviders = current.providers.some((p) => p.id === entry.id)
    ? current.providers.map((p) => (p.id === entry.id ? entry : p))
    : [...current.providers, entry];

  let activeChatId = current.activeChatProviderId ?? null;
  let activeEmbeddingId = current.activeEmbeddingProviderId ?? null;

  if (nextProviders.length === 1) {
    activeChatId = nextProviders[0].id;
    if (nextProviders[0].embeddingModel) activeEmbeddingId = nextProviders[0].id;
  }

  try {
    await persist({
      ...current,
      providers: nextProviders,
      activeChatProviderId: activeChatId,
      activeEmbeddingProviderId: activeEmbeddingId,
    });
    onCancelForm();
    Notify.create({ message: 'Provider enregistré', color: 'positive', timeout: 1500 });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Enregistrement impossible',
      color: 'negative',
    });
  }
}

async function onDelete(entry: LlmProviderEntry): Promise<void> {
  const nextProviders = settings.value.providers.filter((p) => p.id !== entry.id);
  const activeChatProviderId =
    settings.value.activeChatProviderId === entry.id ? null : settings.value.activeChatProviderId;
  const activeEmbeddingProviderId =
    settings.value.activeEmbeddingProviderId === entry.id
      ? null
      : settings.value.activeEmbeddingProviderId;
  try {
    await persist({
      ...settings.value,
      providers: nextProviders,
      activeChatProviderId,
      activeEmbeddingProviderId,
    });
    delete testResults[entry.id];
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Suppression impossible',
      color: 'negative',
    });
  }
}

async function onSetActiveChat(entry: LlmProviderEntry): Promise<void> {
  try {
    await persist({
      ...settings.value,
      activeChatProviderId: entry.id,
    });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Activation impossible',
      color: 'negative',
    });
  }
}

async function onSetActiveEmbedding(entry: LlmProviderEntry): Promise<void> {
  try {
    await persist({
      ...settings.value,
      activeEmbeddingProviderId: entry.id,
    });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Activation impossible',
      color: 'negative',
    });
  }
}

async function onTest(entry: LlmProviderEntry): Promise<void> {
  testingId.value = entry.id;
  try {
    const result = await testLlmConfig(toChatLlmConfig(entry)!);
    testResults[entry.id] = result;
  } catch (err) {
    testResults[entry.id] = {
      ok: false,
      detail: err instanceof Error ? err.message : 'Sidecar injoignable',
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
  gap: 8px;
}

.advanced-setup__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.advanced-setup__guided-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
  }
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

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }
  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.advanced-setup__accordion-head {
  font-family: var(--wp-font-head);
  font-weight: 600;
}

.advanced-setup__empty {
  padding: 12px 4px;
  color: var(--wp-text-faint);
  font-size: 14px;
}

.advanced-setup__hint {
  padding: 8px 4px 12px;
  font-size: 13px;
  color: var(--wp-text-muted);
}

.advanced-setup__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
}

.advanced-setup__form-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0 12px;
}

.advanced-setup__row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.advanced-setup__field {
  flex: 1;
  min-width: 180px;
}

.advanced-setup__form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 8px 0 4px;
  border-top: 1px solid var(--wp-border);
}

.provider-card {
  border: 1px solid var(--wp-border);
  border-left: 3px solid transparent;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-card--active-chat {
  border-left-color: var(--wp-accent);
}

.provider-card--active-embed {
  box-shadow: inset 2px 0 0 var(--wp-success);
}

.provider-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.provider-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: 14px;
  color: var(--wp-text);
}

.provider-card__badges {
  display: flex;
  gap: 6px;
}

.provider-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
}

.provider-badge--chat {
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
}

.provider-badge--embed {
  background: var(--wp-success-soft, var(--wp-accent-soft));
  color: var(--wp-success);
}

.provider-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 6px 16px;
  margin: 0;
}

.provider-card__meta div {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.provider-card__meta dt {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--wp-text-faint);
}

.provider-card__meta dd {
  margin: 0;
  font-size: 13px;
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.provider-card__actions {
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
  color: var(--wp-text);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.ghost-btn--on {
  border-color: var(--wp-accent);
  background: var(--wp-accent-soft);
}

.provider-card__test {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  color: var(--wp-danger);

  &.ok {
    color: var(--wp-success);
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
