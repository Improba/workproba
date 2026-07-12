<template>
  <div class="chat-page">
    <header class="chat-page__header">
      <div class="chat-page__heading">
        <h1 class="chat-page__title">{{ sessionTitle }}</h1>
        <div v-if="metaParts.length || streaming" class="chat-page__meta">
          <template v-for="(part, i) in metaParts" :key="i">
            <span v-if="i > 0" class="chat-page__meta-sep" aria-hidden="true">{{
              t('chat.page.metaSep')
            }}</span>
            <span
              class="chat-page__meta-item"
              :class="
                part.modifier
                  ? `chat-page__meta-item--${part.modifier}`
                  : undefined
              "
              >{{ part.text }}</span
            >
          </template>
          <span v-if="streaming" class="chat-page__meta-live">
            <span class="chat-page__meta-dot" aria-hidden="true" />
            {{ t('chat.page.generating') }}
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
            {{ t('common.retry') }}
          </button>
        </div>
      </div>
    </header>

    <section class="chat-page__body">
      <PersonasMeetingView
        v-if="personasView === 'meeting'"
        :personas="personasList"
        :loading="personasLoading"
        :meeting-state="meetingState"
        :relaunch-config="relaunchMeetingConfig"
        :plugin-data-dir="personasDataDir"
        :workspace-data-dir="activeDataDir"
        :projet-plugin-active="isProjetPluginActive"
        @close="closePersonasView"
        @start="onMeetingStart"
        @relaunch="onMeetingRelaunch"
        @to-discussion="openDiscussionFromMeeting"
      />
      <ChatView
        v-else
        ref="chatViewRef"
        :messages="messages"
        :streaming="streaming"
        :project-path="activePath"
        :session-id="sessionId"
        :workspace-data-dir="activeDataDir"
        :confirming="confirming"
        :approving-plan="approvingPlan"
        :attachment-statuses="attachmentStatuses"
        :settings-locked="settingsLocked"
        :personas-enabled="isPersonasPluginActive"
        :reasoning-effort="displayReasoningEffort"
        :reasoning-provider="activeChatRouting?.provider ?? null"
        :reasoning-model="displayReasoningModel"
        @send="(text, atts) => send(text, { attachments: atts })"
        @abort="abort"
        @open-file="handleOpenFile"
        @update:reasoning-effort="(value) => (displayReasoningEffort = value)"
        @update:reasoning-model="(value) => onReasoningModelChange(value)"
        @confirm-approve="() => confirm('approve')"
        @confirm-deny="() => confirm('deny')"
        @plan-approve="() => approvePlan(true)"
        @plan-reject="() => approvePlan(false)"
        @personas-ask="openOpinionPicker"
        @personas-meeting="openMeetingView"
        @personas-discuss="openDiscussionView"
        @personas-another="(card) => openOpinionPicker(card.question)"
        @personas-to-discussion="openDiscussionFromOpinion"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, toRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { Notify } from 'quasar';
import { useDebounceFn } from '@vueuse/core';
import ChatView from '@components/chat/ChatView.vue';
import PersonasMeetingView from '@components/personas/PersonasMeetingView.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useChatActivity } from '@composables/useChatActivity';
import { useChatStream } from '@composables/useChatStream';
import {
  useAppSettings,
} from '@composables/useAppSettings';
import { setLlmSessionContext } from '@composables/useLlmSessionContext';
import { buildSessionAwareLlmConfigs } from '@utils/llmRouting';
import { openLocalFile } from '@composables/useDesktop';
import { useProject } from '@composables/useProject';
import { clearExpansionState } from '@composables/useToolCallExpansion';
import { createSessionLoadGuard } from '@composables/useSessionLoadGuard';
import { bumpSessions } from '@composables/useSessionSync';
import {
  resolveUiMode,
  requestTitle,
  requestSummary,
} from '@services/aiSidecar';
import { getSession, saveSession } from '@services/workspaceSession';
import { contextWindowFor } from '@utils/modelCatalog';
import { estimateMessagesTokens } from '@utils/tokenEstimate';
import {
  defaultReasoningEffort,
  supportsReasoning,
} from '@utils/reasoningSupport';
import { isModelApplicable } from '@utils/modelCatalog';
import type { ChatMessage, PersonasOpinionCard, ReasoningEffort } from '#types';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { usePersonasNavigation } from '@composables/usePersonasNavigation';
import {
  toolResultToOpinionCard,
  usePersonas,
  meetingStateToStored,
  type MeetingState,
} from '@composables/usePersonas';
import { useSideChat } from '@composables/useSideChat';
import { useBrowser } from '@composables/useBrowser';

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const sessionId = computed(() => String(route.params.id ?? ''));
const sessionTitle = ref(t('chat.page.defaultTitle'));
const sessionSummary = ref<string | null>(null);
const autoTitleStarted = ref(false);
const autoSummaryRunning = ref(false);
const lastSummaryTurn = ref(0);
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null);
const sessionLoadGuard = createSessionLoadGuard();

const { activePath, activeDataDir, documents } = useProject();
const { settingsMode, settingsLocked, activeChatRouting } = useAppSettings();
const { setStreaming, setSidecarState } = useChatActivity();
const { isPersonasPluginActive, isProjetPluginActive, getPluginDataDir } = usePlugins();
const { consumeAction } = usePersonasNavigation();
const {
  personas: personasList,
  loading: personasLoading,
  refresh: refreshPersonas,
  startMeeting,
  saveMeeting,
} = usePersonas();
const { openSideChat } = useSideChat();
const { applyToolResult: applyBrowserToolResult } = useBrowser();

const personasView = ref<'meeting' | null>(null);
const meetingState = ref<MeetingState | null>(null);
const relaunchMeetingConfig = ref<{
  personaIds: string[];
  topic: string;
  rounds: number;
} | null>(null);
const personasDataDir = ref<string | null>(null);

const sessionReasoningOverride = ref<ReasoningEffort | null>(null);
const sessionModelOverride = ref<string | null>(null);

const displayReasoningModel = computed<string | null>(
  () => sessionModelOverride.value ?? activeChatRouting.value?.model ?? null,
);

const displayReasoningEffort = computed<ReasoningEffort>({
  get() {
    if (sessionReasoningOverride.value != null) {
      return sessionReasoningOverride.value;
    }
    const routing = activeChatRouting.value;
    if (!routing) return 'none';
    const model = displayReasoningModel.value ?? routing.model;
    return routing.defaultReasoning ?? defaultReasoningEffort(routing.provider, model);
  },
  set(effort: ReasoningEffort) {
    void onReasoningEffortChange(effort);
  },
});

function sessionLlmConfigs() {
  return buildSessionAwareLlmConfigs(
    sessionModelOverride.value,
    sessionReasoningOverride.value,
  );
}

watch(
  [sessionId, sessionModelOverride, sessionReasoningOverride],
  ([id, model, reasoning]) => {
    if (id) setLlmSessionContext(id, model, reasoning);
  },
  { immediate: true },
);

const uiMode = computed(() =>
  resolveUiMode(settingsLocked.value, settingsMode.value),
);

const {
  messages,
  streaming,
  error: streamError,
  confirming,
  approvingPlan,
  lastUsage,
  completedTurns,
  lastCompaction,
  attachmentStatuses,
  send,
  confirm,
  approvePlan,
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
  onPersonasToolCall: (toolName, payload) => {
    void handlePersonasToolCall(toolName, payload);
  },
  onBrowserToolCall: (toolName, result) => {
    applyBrowserToolResult(toolName, result);
  },
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
  const routing = activeChatRouting.value;
  const parts: ChatMetaPart[] = [];
  if (routing) {
    const model = displayReasoningModel.value ?? routing.model;
    parts.push({ text: routing.label || model });
    if (
      supportsReasoning(routing.provider, model) &&
      displayReasoningEffort.value !== 'none'
    ) {
      const effort = displayReasoningEffort.value;
      const levelLabel = t(`chat.page.reasoningEffort.${effort}`);
      parts.push({
        text: t('chat.page.reasoningLevel', { level: levelLabel.toLowerCase() }),
      });
    }
    const contextWindow = contextWindowFor(routing.provider, model);
    const usedTokens =
      lastUsage.value.inputTokens ?? estimateMessagesTokens(messages.value);
    const pct = Math.round((usedTokens / contextWindow) * 100);
    let modifier: ChatMetaPart['modifier'];
    if (pct >= 90) modifier = 'danger';
    else if (pct >= 75) modifier = 'warning';
    parts.push({
      text: t('chat.page.usageGauge', {
        used: formatTokenCount(usedTokens),
        total: formatTokenCount(contextWindow),
        pct,
      }),
      modifier,
    });
  } else {
    parts.push({ text: t('chat.page.noModelConfigured') });
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
      ? t('chat.page.compactionTruncated', { count: info.droppedCount })
      : t('chat.page.compactionSummarized', { count: info.droppedCount }),
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
    sessionSummary.value = null;

    const session = await getSession(id);
    if (sessionLoadGuard.isStale(loadGen)) return;

    if (!session) {
      Notify.create({
        message: t('chat.page.sessionNotFound'),
        classes: 'bg-danger text-neutral-lowest',
      });
      void router.push({ name: 'home' });
      return;
    }
    sessionTitle.value = session.title || t('chat.page.defaultTitle');
    sessionSummary.value = session.summary ?? null;
    sessionReasoningOverride.value = session.reasoningEffort ?? null;
    // On ne restaure le modèle sauvegardé que s'il est toujours utilisable par
    // le provider actif (l'utilisateur a pu changer de provider entre-temps).
    const chatProvider = activeChatRouting.value?.provider;
    sessionModelOverride.value =
      chatProvider &&
      session.model &&
      isModelApplicable(chatProvider, session.model)
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

// Sauvegarde debouncée : un seul writer pour messages, titre, résumé,
// modèle et raisonnement (évite les races read-modify-write).
async function saveSessionNow(items: ChatMessage[]): Promise<void> {
  if (!activePath.value) return;
  const session = await getSession(sessionId.value);
  if (!session) return;
  await saveSession({
    ...session,
    title: sessionTitle.value.trim() || session.title,
    summary: sessionSummary.value ?? session.summary ?? null,
    messages: items.filter((m) => !m.streaming),
    reasoningEffort: sessionReasoningOverride.value ?? null,
    model: sessionModelOverride.value ?? null,
  });
}

const persistSession = useDebounceFn(saveSessionNow, 500);

async function flushPersistSession(): Promise<void> {
  await saveSessionNow(messages.value);
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
    (m) =>
      !m.streaming &&
      (m.role === 'user' || m.role === 'assistant') &&
      m.content?.trim(),
  );
  if (transcript.length < SUMMARY_MIN_MESSAGES) return;

  autoSummaryRunning.value = true;
  lastSummaryTurn.value = turns;

  try {
    const result = await requestSummary({
      messages: transcript,
      chatConfig: sessionLlmConfigs().chat,
      utilityConfig: null,
      focus: t('chat.page.summaryFocus'),
    });
    if (!result.summary.trim()) return;
    sessionSummary.value = result.summary.trim();
    await flushPersistSession();
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
  if (currentTitle && currentTitle !== t('chat.page.defaultTitle')) return;

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
      chatConfig: sessionLlmConfigs().chat,
      utilityConfig: null,
    });
    if (!title.trim()) return;
    sessionTitle.value = title;
    await flushPersistSession();
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
  () => activeChatRouting.value?.provider ?? null,
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
      message: t('shell.openFileFailed', { name: path.split(/[/\\]/).pop() ?? path }),
      classes: 'bg-danger text-neutral-lowest',
    });
  }
}

async function ensurePersonasDataDir(): Promise<string | null> {
  if (personasDataDir.value) return personasDataDir.value;
  try {
    personasDataDir.value = await getPluginDataDir(PERSONAS_PLUGIN_ID);
    return personasDataDir.value;
  } catch {
    return null;
  }
}

async function loadPersonasIfNeeded(): Promise<void> {
  if (!isPersonasPluginActive.value) return;
  const dir = await ensurePersonasDataDir();
  if (dir) await refreshPersonas(dir);
}

watch(isPersonasPluginActive, () => {
  void loadPersonasIfNeeded();
}, { immediate: true });

function applyPersonasNavigation(): void {
  const action = consumeAction();
  if (!action) return;
  if (action === 'opinion') openOpinionPicker();
  else if (action === 'meeting') openMeetingView();
  else if (action === 'discuss') {
    const raw = sessionStorage.getItem('workproba.personas.resume');
    if (raw) {
      try {
        const payload = JSON.parse(raw) as {
          discussionId: string;
          personaIds: string[];
          messages: Array<{
            id: string;
            role: 'user' | 'persona';
            content: string;
            personaId?: string;
            personaName?: string;
          }>;
        };
        sessionStorage.removeItem('workproba.personas.resume');
        sessionStorage.setItem('workproba.personas.resumeMessages', JSON.stringify(payload));
        openSideChat(PERSONAS_PLUGIN_ID, {
          mode: 'discussion',
          personaIds: payload.personaIds,
        });
        return;
      } catch {
        sessionStorage.removeItem('workproba.personas.resume');
      }
    }
    openDiscussionView();
  }
}

watch(
  () => route.params.id,
  () => {
    applyPersonasNavigation();
  },
  { immediate: true },
);

function closePersonasView(): void {
  personasView.value = null;
  meetingState.value = null;
  relaunchMeetingConfig.value = null;
}

function openOpinionPicker(question?: string): void {
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      mode: 'avis',
      draft: question,
    });
  });
}

function openMeetingView(): void {
  void loadPersonasIfNeeded().then(() => {
    const raw = sessionStorage.getItem('workproba.personas.relaunchMeeting');
    if (raw) {
      try {
        relaunchMeetingConfig.value = JSON.parse(raw) as {
          personaIds: string[];
          topic: string;
          rounds: number;
        };
        sessionStorage.removeItem('workproba.personas.relaunchMeeting');
      } catch {
        sessionStorage.removeItem('workproba.personas.relaunchMeeting');
      }
    }
    personasView.value = 'meeting';
    meetingState.value = null;
  });
}

function onMeetingRelaunch(config: {
  personaIds: string[];
  topic: string;
  rounds: number;
}): void {
  relaunchMeetingConfig.value = config;
  meetingState.value = null;
}

function openDiscussionView(personaIds?: string[]): void {
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      mode: 'discussion',
      personaIds: personaIds ?? [],
    });
  });
}

function openDiscussionFromOpinion(card: PersonasOpinionCard): void {
  const ids = card.opinions.map((o) => o.personaId);
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      mode: 'discussion',
      personaIds: ids,
      discussionSeed: card.question,
    });
  });
}

function openDiscussionFromMeeting(): void {
  const ids = meetingState.value?.personaIds ?? [];
  openDiscussionView(ids);
}

function createOpinionMessage(card: PersonasOpinionCard): ChatMessage {
  return {
    id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    role: 'assistant',
    content: '',
    personasOpinion: card,
    createdAt: new Date().toISOString(),
  };
}

async function onMeetingStart(payload: {
  personaIds: string[];
  topic: string;
  rounds: number;
  includeMemory: boolean;
  meetingId?: string | null;
}): Promise<void> {
  const dir = await ensurePersonasDataDir();
  if (!dir) {
    Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
    return;
  }
  meetingState.value = {
    topic: payload.topic,
    personaIds: payload.personaIds,
    rounds: payload.rounds,
    turns: [],
    summary: '',
    meetingId: payload.meetingId ?? undefined,
    streaming: true,
    error: null,
  };
  meetingState.value = await startMeeting(
    dir,
    payload.personaIds,
    payload.topic,
    payload.rounds,
    (state) => {
      meetingState.value = state;
    },
    activeDataDir.value,
    payload.includeMemory,
    payload.meetingId,
  );
  if (meetingState.value && !meetingState.value.streaming && !meetingState.value.error) {
    saveMeeting(meetingStateToStored(meetingState.value));
  }
}

async function handlePersonasToolCall(
  toolName: 'ask_personas' | 'simulate_meeting',
  payload: { args: Record<string, unknown>; result: unknown },
): Promise<void> {
  await loadPersonasIfNeeded();
  const dir = await ensurePersonasDataDir();
  if (!dir) return;

  if (toolName === 'ask_personas') {
    const question = String(payload.args.question ?? '');
    const card = toolResultToOpinionCard(question, payload.result);
    if (!card) return;
    messages.value.push(createOpinionMessage(card));
  } else if (toolName === 'simulate_meeting') {
    const result =
      payload.result && typeof payload.result === 'object'
        ? (payload.result as Record<string, unknown>)
        : null;
    if (result?.action !== 'open_meeting_view') return;
    const personaIds = Array.isArray(result.persona_ids)
      ? result.persona_ids.map(String)
      : Array.isArray(payload.args.persona_ids)
        ? payload.args.persona_ids.map(String)
        : [];
    const topic = String(result.topic ?? payload.args.topic ?? '');
    const rounds = Math.min(Number(result.rounds ?? payload.args.rounds ?? 3) || 3, 5);
    const meetingId =
      typeof result.meeting_id === 'string' && result.meeting_id
        ? result.meeting_id
        : null;
    personasView.value = 'meeting';
    await onMeetingStart({
      personaIds,
      topic,
      rounds,
      includeMemory: false,
      meetingId,
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
