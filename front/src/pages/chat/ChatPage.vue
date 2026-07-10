<template>
  <div class="chat-page">
    <header class="chat-page__header">
      <div class="chat-page__heading">
        <h1 class="chat-page__title">{{ sessionTitle }}</h1>
        <div v-if="metaParts.length || streaming" class="chat-page__meta">
          <template v-for="(part, i) in metaParts" :key="i">
            <span v-if="i > 0" class="chat-page__meta-sep" aria-hidden="true">·</span>
            <span
              class="chat-page__meta-item"
              :class="part.modifier ? `chat-page__meta-item--${part.modifier}` : undefined"
            >{{ part.text }}</span>
          </template>
          <span v-if="streaming" class="chat-page__meta-live">
            <span class="chat-page__meta-dot" aria-hidden="true" />
            Génération…
          </span>
        </div>
      </div>
      <div class="chat-page__header-actions">
        <div v-if="streamError" class="chat-page__error" role="alert">
        <Lucide name="alert-circle" size="sm" color="danger" />
        <span class="chat-page__error-msg">{{ streamError.message }}</span>
        <button
          v-if="streamError.retryable"
          type="button"
          class="chat-page__retry"
          @click="retry"
        >
          <Lucide name="rotate-ccw" size="xs" color="primary" />
          Réessayer
        </button>
        </div>
      </div>
    </header>

    <section class="chat-page__body">
      <ChatView
        ref="chatViewRef"
        :messages="messages"
        :streaming="streaming"
        :project-path="activePath"
        :session-id="sessionId"
        :confirming="confirming"
        :reasoning-effort="displayReasoningEffort"
        :reasoning-provider="activeChatProvider?.provider ?? null"
        :reasoning-model="displayReasoningModel"
        @send="send"
        @abort="abort"
        @open-file="handleOpenFile"
        @update:reasoning-effort="(value) => (displayReasoningEffort = value)"
        @update:reasoning-model="(value) => onReasoningModelChange(value)"
        @confirm-approve="() => confirm('approve')"
        @confirm-deny="() => confirm('deny')"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, toRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Notify } from 'quasar';
import { useDebounceFn } from '@vueuse/core';
import ChatView from '@components/chat/ChatView.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useChatActivity } from '@composables/useChatActivity';
import { useChatStream } from '@composables/useChatStream';
import { useAppSettings, buildActiveLlmConfigs } from '@composables/useAppSettings';
import { openLocalFile } from '@composables/useDesktop';
import { useProject } from '@composables/useProject';
import { clearExpansionState } from '@composables/useToolCallExpansion';
import { createSessionLoadGuard } from '@composables/useSessionLoadGuard';
import { bumpSessions } from '@composables/useSessionSync';
import { resolveUiMode, requestTitle, requestSummary } from '@services/aiSidecar';
import { getSession, saveSession } from '@services/workspaceSession';
import { contextWindowFor } from '@utils/modelCatalog';
import { estimateMessagesTokens } from '@utils/tokenEstimate';
import { defaultReasoningEffort, REASONING_EFFORT_OPTIONS, supportsReasoning } from '@utils/reasoningSupport';
import { isModelApplicable } from '@utils/modelCatalog';
import type { ChatMessage, ReasoningEffort } from '#types';

const route = useRoute();
const router = useRouter();

const sessionId = computed(() => String(route.params.id ?? ''));
const sessionTitle = ref('Conversation');
const autoTitleStarted = ref(false);
const autoSummaryRunning = ref(false);
const lastSummaryTurn = ref(0);
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null);
const sessionLoadGuard = createSessionLoadGuard();

const { activePath, activeDataDir, documents } = useProject();
const { settingsMode, settingsLocked, activeChatProvider } = useAppSettings();
const { setStreaming, setSidecarState } = useChatActivity();

const sessionReasoningOverride = ref<ReasoningEffort | null>(null);
const sessionModelOverride = ref<string | null>(null);

const displayReasoningModel = computed<string | null>(
  () => sessionModelOverride.value ?? activeChatProvider.value?.model ?? null,
);

const displayReasoningEffort = computed<ReasoningEffort>({
  get() {
    if (sessionReasoningOverride.value != null) {
      return sessionReasoningOverride.value;
    }
    const provider = activeChatProvider.value;
    if (!provider) return 'none';
    const model = displayReasoningModel.value ?? provider.model;
    return (
      provider.reasoningEffort ??
      defaultReasoningEffort(provider.provider, model)
    );
  },
  set(effort: ReasoningEffort) {
    void onReasoningEffortChange(effort);
  },
});

const uiMode = computed(() =>
  resolveUiMode(settingsLocked.value, settingsMode.value),
);

const {
  messages,
  streaming,
  error: streamError,
  confirming,
  lastUsage,
  completedTurns,
  lastCompaction,
  send,
  confirm,
  retry,
  abort,
  loadMessages,
} = useChatStream({
  sessionId: toRef(() => sessionId.value),
  projectPath: activePath,
  workspaceDataDir: activeDataDir,
  documents,
  uiMode,
  reasoningEffort: sessionReasoningOverride,
  sessionModel: sessionModelOverride,
});

interface ChatMetaPart {
  text: string;
  modifier?: 'warning' | 'danger';
}

function formatTokenCount(n: number): string {
  if (n < 1000) return String(n);
  const k = n / 1000;
  if (n < 100_000) {
    const rounded = Math.round(k * 10) / 10;
    return rounded % 1 === 0 ? `${rounded}k` : `${rounded.toFixed(1)}k`;
  }
  return `${Math.round(k)}k`;
}

const metaParts = computed<ChatMetaPart[]>(() => {
  const provider = activeChatProvider.value;
  const parts: ChatMetaPart[] = [];
  if (provider) {
    const model = displayReasoningModel.value ?? provider.model;
    parts.push({ text: provider.label || model });
    if (
      supportsReasoning(provider.provider, model) &&
      displayReasoningEffort.value !== 'none'
    ) {
      const label =
        REASONING_EFFORT_OPTIONS.find((o) => o.value === displayReasoningEffort.value)?.label ??
        '';
      if (label) parts.push({ text: `Raisonnement ${label.toLowerCase()}` });
    }
    const contextWindow = contextWindowFor(provider.provider, model);
    const usedTokens =
      lastUsage.value.inputTokens ?? estimateMessagesTokens(messages.value);
    const pct = Math.round((usedTokens / contextWindow) * 100);
    let modifier: ChatMetaPart['modifier'];
    if (pct >= 90) modifier = 'danger';
    else if (pct >= 75) modifier = 'warning';
    parts.push({
      text: `Contexte ≈ ${formatTokenCount(usedTokens)} / ${formatTokenCount(contextWindow)} (${pct}%)`,
      modifier,
    });
  } else {
    parts.push({ text: 'Aucun modèle configuré' });
  }
  return parts;
});

watch(
  [streaming, streamError],
  ([isStreaming, err]) => {
    setStreaming(isStreaming);
    if (err) {
      setSidecarState('error');
    } else if (isStreaming) {
      setSidecarState('working');
    } else {
      setSidecarState('connected');
    }
  },
  { immediate: true },
);

watch(lastCompaction, (info) => {
  if (!info) return;
  Notify.create({
    message: info.truncated
      ? `Contexte proche du maximum : ${info.droppedCount} messages anciens écartés pour continuer.`
      : `Conversation résumée : ${info.droppedCount} messages anciens compressés pour continuer.`,
    classes: 'bg-neutral-high text-neutral-lowest',
    timeout: 4000,
  });
});

watch(
  sessionId,
  async (id) => {
    if (!id) return;

    const loadGen = sessionLoadGuard.next();

    // Couper d'abord un éventuel stream en cours (changement de conversation
    // pendant une réponse) pour ne pas écrire dans la mauvaise session.
    abort();
    clearExpansionState();

    autoTitleStarted.value = false;
    autoSummaryRunning.value = false;
    lastSummaryTurn.value = 0;

    const session = await getSession(id);
    if (sessionLoadGuard.isStale(loadGen)) return;

    if (!session) {
      Notify.create({
        message: 'Session introuvable',
        classes: 'bg-danger text-neutral-lowest',
      });
      void router.push({ name: 'home' });
      return;
    }
    sessionTitle.value = session.title || 'Conversation';
    sessionReasoningOverride.value = session.reasoningEffort ?? null;
    // On ne restaure le modèle sauvegardé que s'il est toujours utilisable par
    // le provider actif (l'utilisateur a pu changer de provider entre-temps).
    const provider = activeChatProvider.value;
    sessionModelOverride.value =
      provider && session.model && isModelApplicable(provider.provider, session.model)
        ? session.model
        : null;
    if (sessionLoadGuard.isStale(loadGen)) return;
    loadMessages(session.messages ?? []);
    await applyInitialPrompt();
  },
  { immediate: true },
);

async function applyInitialPrompt(): Promise<void> {
  const state = history.state as { initialPrompt?: string } | null;
  const prompt = state?.initialPrompt?.trim();
  if (!prompt) return;

  await nextTick();
  chatViewRef.value?.setDraft(prompt);
  history.replaceState({ ...history.state, initialPrompt: undefined }, '');
}

// Sauvegarde debouncée : on évite la rafale d'écritures pendant le streaming
// (le watch deep se déclenche à chaque flush de tokens) et les races
// read-modify-write concurrentes sur le fichier de session. Un seul writer
// pour messages + modèle + raisonnement = pas d'écrasement croisé.
const persistSession = useDebounceFn(async (items: ChatMessage[]) => {
  if (!activePath.value) return;
  const session = await getSession(sessionId.value);
  if (!session) return;
  await saveSession({
    ...session,
    messages: items.filter((m) => !m.streaming),
    reasoningEffort: sessionReasoningOverride.value ?? null,
    model: sessionModelOverride.value ?? null,
  });
}, 500);

async function persistSessionTitle(title: string): Promise<void> {
  if (!activePath.value) return;
  const session = await getSession(sessionId.value);
  if (!session) return;
  await saveSession({ ...session, title });
}

async function persistSessionSummary(summary: string): Promise<void> {
  if (!activePath.value) return;
  const session = await getSession(sessionId.value);
  if (!session) return;
  await saveSession({ ...session, summary });
}

// Rafraîchissement du résumé cross-conversation : on régénère un résumé
// concis tous les SUMMARY_EVERY_TURNS tours complétés, en arrière-plan et
// sans notification (silencieux). Ce résumé est persisté sur la session et
// consommé par l'outil backend `recall_project_sessions` pour les autres
// conversations du même projet.
const SUMMARY_EVERY_TURNS = 3;
const SUMMARY_MIN_MESSAGES = 4;

watch(completedTurns, async (turns) => {
  if (turns < SUMMARY_EVERY_TURNS || turns % SUMMARY_EVERY_TURNS !== 0) return;
  if (autoSummaryRunning.value || turns === lastSummaryTurn.value) return;
  // On résume la conversation entière (messages persistés hors streaming).
  const transcript = messages.value.filter(
    (m) => !m.streaming && (m.role === 'user' || m.role === 'assistant') && m.content?.trim(),
  );
  if (transcript.length < SUMMARY_MIN_MESSAGES) return;

  autoSummaryRunning.value = true;
  lastSummaryTurn.value = turns;

  try {
    const result = await requestSummary({
      messages: transcript,
      chatConfig: buildActiveLlmConfigs().chat,
      utilityConfig: null,
      focus:
        'Décris brièvement le sujet, les décisions prises, les fichiers concernés et les questions encore ouvertes.',
    });
    if (!result.summary.trim()) return;
    await persistSessionSummary(result.summary.trim());
    bumpSessions();
  } catch {
    // Résumé en arrière-plan : on ignore l'échec sans notifier l'utilisateur.
  } finally {
    autoSummaryRunning.value = false;
  }
});

watch(completedTurns, async (turns) => {
  if (turns < 1 || autoTitleStarted.value) return;
  const currentTitle = sessionTitle.value.trim();
  if (currentTitle && currentTitle !== 'Conversation') return;

  const firstUser = messages.value.find((m) => m.role === 'user');
  const firstAssistant = messages.value.find(
    (m) => m.role === 'assistant' && m.content?.trim(),
  );
  const firstUserMessage = firstUser?.content?.trim();
  const firstAssistantReply = firstAssistant?.content?.trim();
  if (!firstUserMessage || !firstAssistantReply) return;

  autoTitleStarted.value = true;

  try {
    const title = await requestTitle({
      firstUserMessage,
      firstAssistantReply,
      chatConfig: buildActiveLlmConfigs().chat,
      utilityConfig: null,
    });
    if (!title.trim()) return;
    sessionTitle.value = title;
    await persistSessionTitle(title);
    bumpSessions();
  } catch {
    // Titre auto en arrière-plan : on garde le titre par défaut sans notifier.
  }
});

function onReasoningEffortChange(effort: ReasoningEffort): void {
  sessionReasoningOverride.value = effort;
  void persistSession(messages.value);
}

function onReasoningModelChange(model: string): void {
  const trimmed = model.trim();
  if (!trimmed) return;
  sessionModelOverride.value = trimmed;
  void persistSession(messages.value);
}

// Si l'utilisateur change de provider (depuis les réglages) pendant qu'une
// conversation est ouverte, le modèle persisté par session peut ne plus être
// utilisable par le nouveau provider. On l'invalide pour retomber sur le
// modèle par défaut du provider actif.
watch(
  () => activeChatProvider.value?.provider ?? null,
  (providerName) => {
    if (!providerName) return;
    const override = sessionModelOverride.value;
    if (override && !isModelApplicable(providerName, override)) {
      sessionModelOverride.value = null;
      void persistSession(messages.value);
    }
  },
);

watch(
  messages,
  (items) => {
    void persistSession(items);
  },
  { deep: true },
);

async function handleOpenFile(path: string): Promise<void> {
  try {
    await openLocalFile(path, activePath.value);
  } catch {
    Notify.create({
      message: `Impossible d'ouvrir ${path}`,
      classes: 'bg-danger text-neutral-lowest',
    });
  }
}

onUnmounted(() => {
  abort();
  setStreaming(false);
});
</script>

<style scoped lang="scss">
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
}

.chat-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-shrink: 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
  margin-bottom: 0.75rem;
}

.chat-page__heading {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.chat-page__header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
  min-width: 0;
}

.chat-page__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-page__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-tight);
  color: var(--wp-text-muted);
  min-width: 0;
}

.chat-page__meta-item {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  &--warning {
    color: var(--wp-accent-high);
    font-weight: 600;
  }

  &--danger {
    color: var(--wp-danger);
    font-weight: 600;
  }
}

.chat-page__meta-sep {
  color: var(--wp-text-faint);
  flex: none;
}

.chat-page__meta-live {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex: none;
  color: var(--wp-accent-high);
  font-weight: 600;
}

.chat-page__meta-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent);
  animation: wp-breathe 1.4s ease-in-out infinite;
}

.chat-page__error {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
  max-width: 60%;
  font-size: 0.8125rem;
  color: var(--wp-danger);
  background: var(--wp-danger-soft);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-sm);
  padding: 0.35rem 0.55rem;
}

.chat-page__error-msg {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-page__retry {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
  border: 1px solid var(--primary-low);
  border-radius: 6px;
  background: var(--primary-lowest);
  color: var(--text-link);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: var(--primary-lower);
  }
}

.chat-page__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
