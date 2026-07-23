<template>
  <div class="chat-page">
    <header v-if="messages.length > 0" class="chat-page__header">
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
    </header>

    <CloudLoginModal
      v-model="cloudLoginModalOpen"
      @open-invitation="onOpenCloudInvitation"
      @enrolled="onCloudReconnected"
    />
    <EnrollCloudModal v-model="enrollCloudModalOpen" @enrolled="onCloudEnrolled" />

    <section class="chat-page__body">
      <PersonasMeetingView
        v-if="personasView === 'meeting'"
        :personas="selectablePersonasList"
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
        :stream-error="streamError"
        :stream-error-reconnect="streamErrorReconnectCta"
        @send="(text, atts) => send(text, { attachments: atts })"
        @abort="abort"
        @open-file="handleOpenFile"
        @update:reasoning-effort="(value) => (displayReasoningEffort = value)"
        @update:reasoning-model="(value) => onReasoningModelChange(value)"
        @stream-error-report="openStreamErrorReport"
        @stream-error-retry="retry"
        @stream-error-reconnect="onStreamErrorReconnect"
        @error-reconnect="openCloudReconnect"
        @confirm-approve="() => confirm('approve')"
        @confirm-approve-remaining="() => confirm('approve_remaining')"
        @confirm-deny="() => confirm('deny')"
        @plan-approve="() => approvePlan(true)"
        @plan-reject="() => approvePlan(false)"
        @personas-open="openExpertsPanel"
        @personas-meeting="openMeetingView"
        @personas-discuss="openDiscussionView"
        @personas-another="(card) => openOpinionPicker(card.question)"
        @personas-to-discussion="openDiscussionFromOpinion"
        @regenerate="(id) => regenerateFrom(id)"
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
import { toSidecarLocale } from '@boot/i18n';
import ChatView from '@components/chat/ChatView.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import PersonasMeetingView from '@components/personas/PersonasMeetingView.vue';
import { useChatActivity } from '@composables/useChatActivity';
import { useChatStream } from '@composables/useChatStream';
import { useErrorReport } from '@composables/useErrorReport';
import {
  useAppSettings,
} from '@composables/useAppSettings';
import { setLlmSessionContext } from '@composables/useLlmSessionContext';
import {
  buildSessionAwareLlmConfigs,
  buildUtilityLlmConfig,
  buildRoutedProviderSet,
} from '@utils/llmRouting';
import { isProvisionalConversationTitle } from '@utils/conversationTitle';
import { openLocalFile } from '@composables/useDesktop';
import { useSpace } from '@composables/useSpace';
import { clearExpansionState } from '@composables/useToolCallExpansion';
import { createSessionLoadGuard } from '@composables/useSessionLoadGuard';
import { bumpSessions } from '@composables/useSessionSync';
import { consumePendingChatLaunch } from '@composables/usePendingChatLaunch';
import {
  resolveUiMode,
  requestTitle,
  requestSummary,
  promoteSessionMemory,
  sanitizeChatMessagesForPersistence,
} from '@services/aiSidecar';
import { getSession, saveSession } from '@services/workspaceSession';
import { contextWindowFor, isModelApplicable } from '@utils/modelCatalog';
import { estimateMessagesTokens } from '@utils/tokenEstimate';
import {
  isModelApplicableForSet,
  supportsReasoningForSet,
} from '@utils/providerSetModels';
import { effectiveReasoningEffortFromSet } from '@utils/providerSets';
import { defaultReasoningEffort, supportsReasoning } from '@utils/reasoningSupport';
import type { ChatMessage, PersonasOpinionCard, ReasoningEffort } from '#types';
import { CLOUD_PLUGIN_ID, PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useCloud } from '@composables/useCloud';
import { usePersonasNavigation } from '@composables/usePersonasNavigation';
import {
  toolResultToOpinionCard,
  usePersonas,
  meetingStateToStored,
  type MeetingState,
} from '@composables/usePersonas';
import { formatMainChatContext } from '@utils/mainChatContext';
import { useSideChat } from '@composables/useSideChat';
import { useMainChatContext } from '@composables/useMainChatContext';
import { useBrowser } from '@composables/useBrowser';
import { isProviderSetReadinessIssue } from '@utils/providerSetErrors';
import { chatErrorReconnectCta, clearReconnectableChatErrors } from '@utils/chatCloudErrors';

const route = useRoute();
const router = useRouter();
const { t, locale } = useI18n();

const sessionId = computed(() => String(route.params.id ?? ''));
const sessionTitle = ref(t('chat.page.defaultTitle'));
const sessionSummary = ref<string | null>(null);
const autoTitleStarted = ref(false);
const autoSummaryRunning = ref(false);
const lastSummaryTurn = ref(0);
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null);
const sessionLoadGuard = createSessionLoadGuard();

const { activePath, activeDataDir, spaceTitle, documents } = useSpace();
const { settingsLocked, activeChatRouting, effectiveActiveSet } = useAppSettings();
const { setStreaming, setSidecarState } = useChatActivity();
const { isPersonasPluginActive, isProjetPluginActive, getPluginDataDir } = usePlugins();
const { consumeAction, pendingAction } = usePersonasNavigation();
  const {
  selectablePersonas: selectablePersonasList,
  loading: personasLoading,
  refresh: refreshPersonas,
  startMeeting,
  saveMeeting,
} = usePersonas();
const { openSideChat, closeSideChat } = useSideChat();
const { setMessages: syncMainChatContext } = useMainChatContext();
const { applyToolResult: applyBrowserToolResult, pilotagePaused, setAgentTurnActive } = useBrowser();

const personasView = ref<'meeting' | null>(null);
const meetingState = ref<MeetingState | null>(null);
const relaunchMeetingConfig = ref<{
  personaIds: string[];
  topic: string;
  rounds: number;
} | null>(null);
const personasDataDir = ref<string | null>(null);
const meetingAbort = ref<AbortController | null>(null);
let meetingRunId = 0;

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
    const model = displayReasoningModel.value;
    const routing = activeChatRouting.value;
    if (!routing || !model) return 'none';
    if (effectiveActiveSet.value) {
      return effectiveReasoningEffortFromSet(
        effectiveActiveSet.value,
        sessionModelOverride.value,
        null,
      );
    }
    return defaultReasoningEffort(routing.provider, model);
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
  resolveUiMode(settingsLocked.value),
);

const { openFromChatError } = useErrorReport();
const { disconnect, refreshQuota } = useCloud();

const cloudLoginModalOpen = ref(false);
const enrollCloudModalOpen = ref(false);

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
  streamCorrelation,
  send,
  confirm,
  approvePlan,
  retry,
  regenerateFrom,
  abort,
  loadMessages,
} = useChatStream({
  sessionId: toRef(() => sessionId.value),
  projectPath: activePath,
  workspaceDataDir: activeDataDir,
  workspaceTitle: spaceTitle,
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
  browserPilotagePaused: pilotagePaused,
});

const streamErrorReconnectCta = computed<'login' | 'enroll' | null>(() => {
  const code = streamError.value?.code;
  if (!code) return null;
  return chatErrorReconnectCta(code);
});

async function openCloudReconnect(cta: 'login' | 'enroll'): Promise<void> {
  if (cta === 'login') {
    await disconnect();
    cloudLoginModalOpen.value = true;
    return;
  }
  enrollCloudModalOpen.value = true;
}

async function onStreamErrorReconnect(): Promise<void> {
  const cta = streamErrorReconnectCta.value;
  if (!cta) return;
  await openCloudReconnect(cta);
}

function onOpenCloudInvitation(): void {
  cloudLoginModalOpen.value = false;
  enrollCloudModalOpen.value = true;
}

function retryStreamErrorIfNeeded(): void {
  const err = streamError.value;
  if (err?.retryable) {
    void retry().catch(() => {
      // Ne pas bloquer la reconnexion cloud si le retry échoue.
    });
    return;
  }
  if (streamErrorReconnectCta.value) {
    streamError.value = null;
  }
}

async function onCloudReconnected(): Promise<void> {
  await refreshQuota();
  cloudLoginModalOpen.value = false;
  retryStreamErrorIfNeeded();
  clearReconnectableChatErrors(messages.value);
}

async function onCloudEnrolled(): Promise<void> {
  await refreshQuota();
  enrollCloudModalOpen.value = false;
  retryStreamErrorIfNeeded();
  clearReconnectableChatErrors(messages.value);
}

function openStreamErrorReport(): void {
  if (!streamError.value) return;
  openFromChatError(
    streamError.value,
    {
      ...streamCorrelation.value,
      sessionId: sessionId.value,
    },
    streamError.value.retryable ? () => retry() : undefined,
  );
}

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
      (effectiveActiveSet.value
        ? supportsReasoningForSet(effectiveActiveSet.value, model)
        : supportsReasoning(routing.provider, model)) &&
      displayReasoningEffort.value !== 'none'
    ) {
      const effort = displayReasoningEffort.value;
      const levelLabel = t(`chat.page.reasoningEffort.${effort}`);
      parts.push({
        text: t('chat.page.reasoningLevel', { level: levelLabel.toLowerCase() }),
      });
    }
    const contextWindow = contextWindowFor(routing.provider, model, effectiveActiveSet.value);
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
    setAgentTurnActive(isStreaming);
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
    closePersonasView();
    closeSideChat();
    clearExpansionState();

    sessionReasoningOverride.value = null;
    sessionModelOverride.value = null;

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
      (effectiveActiveSet.value
        ? isModelApplicableForSet(effectiveActiveSet.value, session.model)
        : isModelApplicable(chatProvider, session.model))
        ? session.model
        : null;
    if (sessionLoadGuard.isStale(loadGen)) return;
    loadMessages(session.messages ?? []);
    await afterSessionLoaded(loadGen);
  },
  { immediate: true },
);

async function afterSessionLoaded(loadGen: number): Promise<void> {
  const state = history.state as {
    initialPrompt?: string;
    focusComposer?: boolean;
  } | null;
  const pending = consumePendingChatLaunch();

  await nextTick();
  if (sessionLoadGuard.isStale(loadGen)) return;

  if (pending) {
    if (pending.reasoningEffort != null) {
      sessionReasoningOverride.value = pending.reasoningEffort;
    }
    if (pending.model) {
      sessionModelOverride.value = pending.model;
    }
    await send(pending.text, { attachments: pending.attachments });
    void tryAutoTitle(loadGen);
    return;
  }

  const prompt = state?.initialPrompt?.trim();

  if (prompt) {
    chatViewRef.value?.setDraft(prompt);
    history.replaceState({ ...history.state, initialPrompt: undefined }, '');
    void tryAutoTitle(loadGen);
    return;
  }

  if (messages.value.length === 0 || state?.focusComposer) {
    chatViewRef.value?.setDraft('', true);
    if (state?.focusComposer) {
      history.replaceState({ ...history.state, focusComposer: undefined }, '');
    }
  }

  void tryAutoTitle(loadGen);
}

async function tryAutoTitle(loadGen?: number): Promise<void> {
  if (autoTitleStarted.value) return;
  if (!isProvisionalConversationTitle(sessionTitle.value, t)) return;

  const firstUser = messages.value.find((m) => m.role === 'user');
  const firstAssistant = messages.value.find(
    (m) => m.role === 'assistant' && m.content?.trim() && !m.streaming,
  );
  const firstUserMessage = firstUser?.content?.trim();
  if (!firstUserMessage) return;
  const firstAssistantReply = firstAssistant?.content?.trim();

  const targetSessionId = sessionId.value;
  autoTitleStarted.value = true;

  try {
    const providerSet = buildRoutedProviderSet();
    const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    const title = await requestTitle({
      firstUserMessage,
      ...(firstAssistantReply ? { firstAssistantReply } : {}),
      chatConfig: sessionLlmConfigs().chat,
      utilityConfig: buildUtilityLlmConfig(),
      providerSet,
      cloudPluginDataDir,
      locale: toSidecarLocale(locale.value),
    });
    if (loadGen !== undefined && sessionLoadGuard.isStale(loadGen)) return;
    if (sessionId.value !== targetSessionId) return;
    if (!title.trim()) return;
    if (!isProvisionalConversationTitle(sessionTitle.value, t)) return;
    sessionTitle.value = title;
    await flushPersistSession();
    bumpSessions();
  } catch {
    // Titre auto en arrière-plan : on garde le titre par défaut sans notifier.
  }
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
    messages: sanitizeChatMessagesForPersistence(items.filter((m) => !m.streaming)),
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
    const providerSet = buildRoutedProviderSet();
    const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    const result = await requestSummary({
      messages: transcript,
      chatConfig: sessionLlmConfigs().chat,
      utilityConfig: buildUtilityLlmConfig(),
      providerSet,
      cloudPluginDataDir,
      focus: t('chat.page.summaryFocus'),
      locale: toSidecarLocale(locale.value),
    });
    if (!result.summary.trim()) return;
    sessionSummary.value = result.summary.trim();
    await flushPersistSession();
    bumpSessions();

    const dataDir = activeDataDir.value;
    if (dataDir) {
      void promoteSessionMemory({
        workspaceDataDir: dataDir,
        sessionId: sessionId.value,
        summary: sessionSummary.value,
        chatConfig: sessionLlmConfigs().chat,
        utilityConfig: buildUtilityLlmConfig(),
        providerSet,
        cloudPluginDataDir,
        locale: toSidecarLocale(locale.value),
      }).catch(() => {
        // Promotion mémoire en arrière-plan : échec silencieux.
      });
    }
  } catch {
    // Résumé en arrière-plan : on ignore l'échec sans notifier l'utilisateur.
  } finally {
    autoSummaryRunning.value = false;
  }
});

const firstUserMessageForTitle = computed(() => {
  const user = messages.value.find((m) => m.role === 'user');
  return user?.content?.trim() || '';
});

watch(firstUserMessageForTitle, (text) => {
  if (!text) return;
  void tryAutoTitle();
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
    if (override && !(
      effectiveActiveSet.value
        ? isModelApplicableForSet(effectiveActiveSet.value, override)
        : isModelApplicable(providerName, override)
    )) {
      sessionModelOverride.value = null;
      sessionReasoningOverride.value = null;
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

watch(
  messages,
  (items) => {
    syncMainChatContext(items, sessionId.value);
  },
  { deep: true, immediate: true },
);

function applyPersonasNavigation(): void {
  const payload = consumeAction();
  if (!payload) return;
  const { action, personaIds, resume } = payload;
  if (action === 'opinion') openOpinionPicker(undefined, personaIds);
  else if (action === 'meeting') openMeetingView();
  else if (action === 'discuss') {
    if (resume) {
      void loadPersonasIfNeeded().then(() => {
        openSideChat(PERSONAS_PLUGIN_ID, {
          mode: 'discussion',
          personaIds: resume.personaIds,
          conversationContext: buildConversationContext(),
          resume,
        });
      });
    } else {
      openDiscussionView(personaIds);
    }
  }
}

watch(
  () => route.params.id,
  () => {
    applyPersonasNavigation();
  },
  { immediate: true },
);

watch(pendingAction, (action) => {
  if (action) applyPersonasNavigation();
}, { immediate: true });

function closePersonasView(): void {
  abortActiveMeeting();
  personasView.value = null;
  meetingState.value = null;
  relaunchMeetingConfig.value = null;
}

function abortActiveMeeting(): void {
  meetingRunId += 1;
  meetingAbort.value?.abort();
  meetingAbort.value = null;
}

function buildConversationContext(): string {
  return formatMainChatContext(messages.value, { locale: locale.value });
}

function openExpertsPanel(): void {
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      conversationContext: buildConversationContext(),
    });
  });
}

function openOpinionPicker(
  question?: string,
  personaIds?: string[],
  options?: { autoAsk?: boolean },
): void {
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      mode: 'avis',
      draft: question,
      personaIds: personaIds ?? [],
      conversationContext: buildConversationContext(),
      autoAsk: options?.autoAsk ?? (personaIds?.length ?? 0) > 0,
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
        relaunchMeetingConfig.value = null;
      }
    } else {
      relaunchMeetingConfig.value = null;
    }
    abortActiveMeeting();
    personasView.value = 'meeting';
    meetingState.value = null;
  });
}

function onMeetingRelaunch(config: {
  personaIds: string[];
  topic: string;
  rounds: number;
}): void {
  abortActiveMeeting();
  relaunchMeetingConfig.value = config;
  meetingState.value = null;
}

function openDiscussionView(personaIds?: string[]): void {
  void loadPersonasIfNeeded().then(() => {
    openSideChat(PERSONAS_PLUGIN_ID, {
      mode: 'discussion',
      personaIds: personaIds ?? [],
      conversationContext: buildConversationContext(),
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
      conversationContext: buildConversationContext(),
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
  abortActiveMeeting();

  relaunchMeetingConfig.value = null;

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

  const dir = await ensurePersonasDataDir();
  if (!dir) {
    meetingState.value = {
      topic: payload.topic,
      personaIds: payload.personaIds,
      rounds: payload.rounds,
      turns: [],
      summary: '',
      meetingId: payload.meetingId ?? undefined,
      streaming: false,
      error: 'unavailable',
    };
    Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
    return;
  }

  const runId = meetingRunId;
  const controller = new AbortController();
  meetingAbort.value = controller;

  const result = await startMeeting(
    dir,
    payload.personaIds,
    payload.topic,
    payload.rounds,
    (state) => {
      if (runId !== meetingRunId || controller.signal.aborted) return;
      meetingState.value = state;
    },
    activeDataDir.value,
    payload.includeMemory,
    payload.meetingId,
    controller.signal,
    buildConversationContext(),
  );

  if (runId !== meetingRunId || controller.signal.aborted) {
    meetingAbort.value = null;
    return;
  }

  meetingAbort.value = null;
  meetingState.value = result;

  if (meetingState.value?.error) {
    if (!isProviderSetReadinessIssue(meetingState.value.error)) {
      Notify.create({ message: t('personas.errors.meetingFailed'), color: 'negative' });
    }
    return;
  }
  if (meetingState.value && !meetingState.value.streaming) {
    saveMeeting(meetingStateToStored(meetingState.value));
  }
}

async function handlePersonasToolCall(
  toolName: 'ask_personas' | 'simulate_meeting',
  payload: { args: Record<string, unknown>; result: unknown },
): Promise<void> {
  await loadPersonasIfNeeded();
  const dir = await ensurePersonasDataDir();
  if (!dir) {
    Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
    return;
  }

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
  closePersonasView();
  closeSideChat();
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

.chat-page__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
