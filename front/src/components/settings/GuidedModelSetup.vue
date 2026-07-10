<template>
  <section class="guided-setup">
    <h2 class="guided-setup__section-title">Choisir un fournisseur</h2>

    <div class="guided-setup__cards" role="radiogroup" aria-label="Choisir un fournisseur">
      <button
        v-for="card in cards"
        :key="card.id"
        type="button"
        class="guided-card"
        :class="{ 'guided-card--selected': selectedCard === card.id }"
        role="radio"
        :aria-checked="selectedCard === card.id"
        @click="onSelectCard(card.id)"
      >
        <span class="guided-card__badge" :class="`guided-card__badge--${card.badgeTone}`">
          {{ card.badge }}
        </span>
        <span class="guided-card__title">{{ card.title }}</span>
        <span class="guided-card__subtitle">{{ card.subtitle }}</span>
      </button>
    </div>

    <div v-if="selectedCard === 'mistral'" class="guided-setup__fields">
      <q-input
        v-model="apiKey"
        label="Clé API Mistral"
        outlined
        dense
        :type="showKey ? 'text' : 'password'"
        class="guided-setup__field"
        @update:model-value="onFieldChange"
      >
        <template #append>
          <button type="button" class="reveal-btn" @click="showKey = !showKey">
            <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
          </button>
        </template>
      </q-input>
      <p class="guided-setup__hint">
        Le modèle (Small, Medium, Large) se choisit ensuite dans chaque conversation.
      </p>
    </div>

    <div v-else-if="selectedCard === 'ollama'" class="guided-setup__fields">
      <q-input
        v-model="baseUrl"
        label="URL Ollama"
        outlined
        dense
        class="guided-setup__field"
        @update:model-value="onFieldChange"
      />
      <div class="guided-setup__row">
        <q-select
          v-if="ollamaModels.length > 0"
          v-model="model"
          :options="ollamaModels"
          label="Modèle détecté"
          outlined
          dense
          class="guided-setup__field"
          @update:model-value="onFieldChange"
        />
        <q-input
          v-else
          v-model="model"
          label="Modèle"
          outlined
          dense
          hint="Saisissez le nom du modèle Ollama"
          class="guided-setup__field"
          @update:model-value="onFieldChange"
        />
        <button
          type="button"
          class="guided-setup__refresh"
          :disabled="refreshingOllama"
          @click="onRefreshOllama"
        >
          <Lucide name="refresh-cw" size="14" color="text" />
          {{ refreshingOllama ? 'Rafraîchissement…' : 'Rafraîchir' }}
        </button>
      </div>
    </div>

    <div v-else class="guided-setup__fields">
      <q-select
        v-model="cloudProvider"
        :options="cloudProviderOptions"
        label="Fournisseur"
        outlined
        dense
        emit-value
        map-options
        class="guided-setup__field"
        @update:model-value="onCloudProviderChange"
      />
      <q-input
        v-model="apiKey"
        :label="cloudApiKeyLabel"
        outlined
        dense
        :type="showKey ? 'text' : 'password'"
        class="guided-setup__field"
        @update:model-value="onFieldChange"
      >
        <template #append>
          <button type="button" class="reveal-btn" @click="showKey = !showKey">
            <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
          </button>
        </template>
      </q-input>
      <p class="guided-setup__hint">
        Le modèle se choisit ensuite dans chaque conversation.
      </p>
    </div>

    <div class="guided-setup__actions">
      <button
        type="button"
        class="guided-setup__test"
        :disabled="testing || !canTest"
        @click="onTest"
      >
        <Lucide name="plug-zap" size="14" color="wp-canard" />
        {{ testing ? 'Test en cours…' : 'Tester la connexion' }}
      </button>
      <p
        v-if="testStatus"
        class="guided-setup__status"
        :class="{ 'guided-setup__status--ok': testStatus.ok }"
      >
        <Lucide
          :name="testStatus.ok ? 'check-circle-2' : 'alert-circle'"
          size="14"
          :color="testStatus.ok ? 'success' : 'danger'"
        />
        {{ testStatus.label }}
      </p>
    </div>

    <button type="button" class="guided-setup__advanced-link" @click="emit('switch-to-advanced')">
      Réglages avancés
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import {
  useAppSettings,
  toChatLlmConfig,
  testLlmConfig,
  type LlmTestResult,
} from '@composables/useAppSettings';
import type { AppSettings, LlmProviderEntry } from '@composables/useDesktop.types';
import { fetchOllamaModels } from '@services/ollamaModels';
import {
  applyGuidedCard,
  inferCloudProvider,
  inferGuidedCard,
  type CloudProviderName,
  type GuidedCardId,
} from '@utils/guidedModelSetup';

const emit = defineEmits<{
  'switch-to-advanced': [];
}>();

const { settings, activeChatProvider, load, save } = useAppSettings();

const cards = [
  {
    id: 'mistral' as const,
    title: 'Mistral',
    subtitle: 'Service cloud Mistral AI. Requiert une clé API.',
    badge: 'Recommandé',
    badgeTone: 'recommended',
  },
  {
    id: 'ollama' as const,
    title: 'Local (Ollama)',
    subtitle: 'Modèle exécuté sur votre machine via Ollama. Aucune donnée transmise. Requiert Ollama installé.',
    badge: 'Local',
    badgeTone: 'local',
  },
  {
    id: 'cloud' as const,
    title: 'Cloud tiers (OpenAI / Anthropic)',
    subtitle: 'Services cloud OpenAI ou Anthropic. Requiert une clé API. Données transmises au fournisseur.',
    badge: 'Cloud',
    badgeTone: 'cloud',
  },
];

const selectedCard = ref<GuidedCardId>('mistral');
const cloudProvider = ref<CloudProviderName>('openai');
const apiKey = ref('');
const baseUrl = ref('http://localhost:11434');
const model = ref('mistral-small-latest');
const showKey = ref(false);
const testing = ref(false);
const refreshingOllama = ref(false);
const ollamaModels = ref<string[]>([]);
const testStatus = ref<{ ok: boolean; label: string } | null>(null);

const cloudProviderOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
];

const cloudApiKeyLabel = computed(() =>
  cloudProvider.value === 'anthropic' ? 'Clé API Anthropic' : 'Clé API OpenAI',
);

const canTest = computed(() => {
  if (selectedCard.value === 'ollama') return Boolean(model.value.trim());
  return Boolean(model.value.trim() && apiKey.value.trim());
});

function newId(): string {
  return `prov_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function getPrimaryEntry(): LlmProviderEntry | null {
  return activeChatProvider.value ?? settings.value.providers[0] ?? null;
}

function hydrateFromEntry(entry: LlmProviderEntry | null): void {
  selectedCard.value = inferGuidedCard(entry);
  if (selectedCard.value === 'cloud') {
    cloudProvider.value = inferCloudProvider(entry);
  }
  apiKey.value = entry?.apiKey ?? '';
  baseUrl.value = entry?.baseUrl?.trim() || 'http://localhost:11434';
  model.value = entry?.model ?? applyGuidedCard(selectedCard.value, cloudProvider.value).model;
}

function buildEntryFromForm(existing: LlmProviderEntry | null): LlmProviderEntry {
  const preset = applyGuidedCard(selectedCard.value, cloudProvider.value);
  // Les réglages définissent un provider/preset, pas un modèle spécifique :
  // pour les providers catalogués (Mistral, OpenAI, Anthropic), on utilise le
  // modèle par défaut du preset. Le choix fin du modèle se fait par
  // conversation dans le compositeur. Ollama (pas de catalogue) garde la
  // saisie libre, car il n'y a pas d'autre endroit pour la définir.
  const resolvedModel =
    selectedCard.value === 'ollama' ? model.value.trim() || preset.model : preset.model;
  return {
    id: existing?.id ?? newId(),
    label: preset.label,
    provider: preset.provider,
    model: resolvedModel,
    baseUrl:
      selectedCard.value === 'ollama'
        ? baseUrl.value.trim() || 'http://localhost:11434'
        : preset.baseUrl || null,
    apiKey: selectedCard.value === 'ollama' ? null : apiKey.value.trim() || null,
    temperature: existing?.temperature ?? null,
    maxTokens: existing?.maxTokens ?? null,
    extraHeaders: existing?.extraHeaders ?? {},
    embeddingModel: preset.embeddingModel || existing?.embeddingModel || null,
    embeddingBaseUrl: existing?.embeddingBaseUrl ?? null,
  };
}

async function persistEntry(entry: LlmProviderEntry): Promise<void> {
  const current = settings.value;
  const providers = current.providers.some((p) => p.id === entry.id)
    ? current.providers.map((p) => (p.id === entry.id ? entry : p))
    : [...current.providers, entry];

  const next: AppSettings = {
    ...current,
    providers,
    activeChatProviderId: entry.id,
    activeEmbeddingProviderId: entry.embeddingModel ? entry.id : current.activeEmbeddingProviderId,
  };

  await save(next);
}

async function onFieldChange(): Promise<void> {
  testStatus.value = null;
  try {
    const existing = getPrimaryEntry();
    await persistEntry(buildEntryFromForm(existing));
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : 'Enregistrement impossible',
      color: 'negative',
    });
  }
}

async function onSelectCard(card: GuidedCardId): Promise<void> {
  selectedCard.value = card;
  const preset = applyGuidedCard(card, cloudProvider.value);
  model.value = preset.model;
  if (card === 'ollama') {
    baseUrl.value = preset.baseUrl;
    apiKey.value = '';
  } else if (card === 'mistral') {
    apiKey.value = getPrimaryEntry()?.apiKey ?? '';
  } else {
    apiKey.value = getPrimaryEntry()?.apiKey ?? '';
  }
  testStatus.value = null;
  await onFieldChange();
}

async function onCloudProviderChange(value: CloudProviderName): Promise<void> {
  cloudProvider.value = value;
  const preset = applyGuidedCard('cloud', value);
  model.value = preset.model;
  testStatus.value = null;
  await onFieldChange();
}

function humanizeTestResult(result: LlmTestResult): string {
  if (result.ok) return 'Connexion OK';
  const detail = result.detail.toLowerCase();
  if (detail.includes('401') || detail.includes('invalide')) return 'Clé invalide';
  if (detail.includes('ollama') || detail.includes('connexion impossible')) return 'Ollama injoignable';
  return result.detail || 'Échec de connexion';
}

async function onTest(): Promise<void> {
  testing.value = true;
  testStatus.value = null;
  try {
    const entry = buildEntryFromForm(getPrimaryEntry());
    const config = toChatLlmConfig(entry);
    if (!config) {
      testStatus.value = { ok: false, label: 'Configuration incomplète' };
      return;
    }
    const result = await testLlmConfig(config);
    testStatus.value = { ok: result.ok, label: humanizeTestResult(result) };
  } catch {
    testStatus.value = { ok: false, label: 'Sidecar injoignable' };
  } finally {
    testing.value = false;
  }
}

async function onRefreshOllama(): Promise<void> {
  refreshingOllama.value = true;
  try {
    const models = await fetchOllamaModels(baseUrl.value);
    ollamaModels.value = models;
    if (models.length > 0 && !models.includes(model.value)) {
      model.value = models[0];
      await onFieldChange();
    }
  } catch (err) {
    ollamaModels.value = [];
    Notify.create({
      message: err instanceof Error ? err.message : 'Ollama injoignable',
      color: 'warning',
    });
  } finally {
    refreshingOllama.value = false;
  }
}

onMounted(async () => {
  await load();
  hydrateFromEntry(getPrimaryEntry());
  if (selectedCard.value === 'ollama') {
    void onRefreshOllama();
  }
});

watch(activeChatProvider, (entry) => {
  hydrateFromEntry(entry);
});
</script>

<style scoped lang="scss">
.guided-setup {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.guided-setup__section-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.guided-setup__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.guided-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px;
  border: 2px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:hover {
    border-color: var(--wp-accent);
  }
}

.guided-card--selected {
  border-color: var(--wp-accent);
  box-shadow: 0 0 0 3px var(--wp-accent-soft);
}

.guided-card__badge {
  font-size: var(--wp-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: var(--wp-r-pill);
}

.guided-card__badge--recommended {
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
}

.guided-card__badge--local {
  background: var(--wp-success-soft, var(--wp-accent-soft));
  color: var(--wp-success);
}

.guided-card__badge--cloud {
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.guided-card__title {
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.guided-card__subtitle {
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.guided-setup__fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.guided-setup__row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.guided-setup__field {
  flex: 1;
  min-width: 200px;
}

.guided-setup__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.guided-setup__refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-top: 2px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.guided-setup__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guided-setup__test {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-sm);
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

.guided-setup__status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-danger);

  &--ok {
    color: var(--wp-success);
  }
}

.guided-setup__advanced-link {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-decoration: underline;
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
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
