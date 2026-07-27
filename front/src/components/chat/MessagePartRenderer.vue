<template>
  <template v-for="block in groupedRenderBlocks" :key="renderBlockKey(block)">
    <MessageTextPart
      v-if="block.kind === 'text' && Boolean(block.part.content?.trim())"
      :content="block.part.content"
      :streaming="!!message.streaming"
      :show-cursor="block.part.id === lastTextPartId && !!message.streaming"
    />
    <ActivityGroup
      v-else-if="block.kind === 'activity_group'"
      :group="block.group"
      :tool-calls="message.toolCalls"
      :streaming="!!message.streaming"
      :pending-confirmation="message.pendingConfirmation"
      :preparing-confirmation="message.preparingConfirmation"
      :confirming="confirming"
      :project-path="projectPath"
      :session-id="sessionId"
      :workspace-data-dir="workspaceDataDir"
      @open-file="(path) => emit('open-file', path)"
      @restored="(path) => emit('restored', path)"
      @confirm-approve="emit('confirm-approve')"
      @confirm-approve-remaining="emit('confirm-approve-remaining')"
      @confirm-deny="emit('confirm-deny')"
    />
  </template>

  <p
    v-if="showContinuationPlaceholder"
    class="chat-message__continuation"
    aria-live="polite"
    :aria-busy="true"
  >
    <span class="chat-message__continuation-spinner" aria-hidden="true" />
    {{ t('chat.continuationPlaceholder') }}
  </p>

  <PlanCard
    v-if="message.pendingPlan && message.role === 'assistant'"
    :plan="message.pendingPlan"
    :busy="approvingPlan"
    @approve="emit('plan-approve')"
    @reject="emit('plan-reject')"
  />

  <PersonasOpinionCard
    v-if="message.personasOpinion"
    :card="message.personasOpinion"
    :show-publish="isProjetPluginActive"
    @another="emit('personas-another', message.personasOpinion!)"
    @to-discussion="emit('personas-to-discussion', message.personasOpinion!)"
    @publish="openOpinionPublish"
  />

  <MemoryCitationsBar
    v-if="message.role === 'assistant' && message.memoryCitations?.length"
    :citations="message.memoryCitations"
    :expansion-key="message.id"
  />

  <WebSearchCitationsBar
    v-if="message.role === 'assistant' && webSearchCitations.length"
    :citations="webSearchCitations"
  />

  <PublishToProjectDialog
    v-if="message.personasOpinion"
    v-model:open="opinionPublishOpen"
    :content="opinionPublishMarkdown"
    :default-name="opinionPublishName"
    :workspace-data-dir="workspaceDataDir"
  />

  <div v-if="message.error" class="chat-message__error" role="alert">
    <Lucide name="alert-circle" size="sm" color="danger" />
    <div class="chat-message__error-body">
      <p class="chat-message__error-msg">{{ message.error.message }}</p>
      <span v-if="message.error.code" class="chat-message__error-code">
        {{ message.error.code }}
      </span>
      <button
        type="button"
        class="chat-message__error-report"
        @click="openMessageErrorReport"
      >
        {{ t('errors.reportOpenAction') }}
      </button>
      <button
        v-if="reconnectCta"
        type="button"
        class="chat-message__error-reconnect"
        @click="emit('error-reconnect', reconnectCta)"
      >
        {{ t('errors.cloudReconnect') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import ActivityGroup from '@components/chat/ActivityGroup.vue';
import PlanCard from '@components/chat/PlanCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import MemoryCitationsBar from '@components/chat/MemoryCitationsBar.vue';
import WebSearchCitationsBar from '@components/chat/WebSearchCitationsBar.vue';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { collapseActivityGroup } from '@composables/useToolCallExpansion';
import { useErrorReport } from '@composables/useErrorReport';
import { usePlugins } from '@composables/usePlugins';
import { formatOpinionMarkdown } from '@composables/usePersonas';
import { chatErrorReconnectCta } from '@utils/chatCloudErrors';
import { extractWebSearchCitations } from '@utils/webSearchCitations';
import {
  activityGroupIdAt,
  groupMessageParts,
  type MessageRenderBlock,
} from '@utils/activityGroup';
import {
  deriveThinkingSubjectDone,
  deriveThinkingSummary,
} from '@utils/thinkingPresentation';
import type { ChatMessage, ChatMessagePart, ChatThinkingPart } from '#types';

const props = defineProps<{
  message: ChatMessage;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
  confirming?: boolean;
  approvingPlan?: boolean;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-approve-remaining': [];
  'confirm-deny': [];
  'plan-approve': [];
  'plan-reject': [];
  'personas-another': [card: import('#types').PersonasOpinionCard];
  'personas-to-discussion': [card: import('#types').PersonasOpinionCard];
  'error-reconnect': [cta: 'login' | 'enroll'];
}>();

const opinionPublishOpen = ref(false);
const { t, locale } = useI18n();
const { openFromChatError } = useErrorReport();

function openMessageErrorReport(): void {
  if (!props.message.error) return;
  openFromChatError(props.message.error, {
    sessionId: props.sessionId ?? null,
    turnId: props.message.error.turnId ?? null,
    workId: props.message.error.workId ?? null,
  });
}

const reconnectCta = computed<'login' | 'enroll' | null>(() => {
  const code = props.message.error?.code;
  if (!code) return null;
  return chatErrorReconnectCta(code);
});
const { isProjetPluginActive } = usePlugins();

const opinionPublishMarkdown = computed(() =>
  props.message.personasOpinion
    ? formatOpinionMarkdown(props.message.personasOpinion)
    : '',
);

const webSearchCitations = computed(() => extractWebSearchCitations(props.message));

const opinionPublishName = computed(() => {
  const topic = props.message.personasOpinion?.question ?? t('personas.opinion.header', { topic: '' });
  const date = new Date().toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  return t('personas.publishToProjectNameOpinion', { topic, date });
});

function openOpinionPublish(): void {
  opinionPublishOpen.value = true;
}

/**
 * Indicateur « Le modèle réfléchit… » affiché dans le bloc assistant tant
 * qu'aucun contenu n'est encore arrivé (délai d'amorçage avant le premier
 * token ou le premier event `thinking_start`). Couvre le trou perçu entre
 * l'envoi et l'apparition du raisonnement/texte.
 */
const showThinkingPlaceholder = computed(() => {
  if (props.message.role !== 'assistant') return false;
  if (!props.message.streaming) return false;
  if (props.message.error) return false;
  const parts = props.message.parts ?? [];
  const hasText = parts.some(
    (p) => p.type === 'text' && (p as { content?: string }).content?.trim().length,
  );
  const hasThinking = parts.some((p) => p.type === 'thinking');
  const hasToolCall = parts.some((p) => p.type === 'tool_call');
  return !hasText && !hasThinking && !hasToolCall;
});

const thinkingPlaceholderPart = computed<ChatThinkingPart>(() => ({
  type: 'thinking',
  id: `${props.message.id}__thinking-placeholder`,
  thinkingId: `${props.message.id}__thinking-placeholder`,
  content: '',
  done: false,
}));

/**
 * Segments ordonnés à rendre. Si le message dispose de `parts` (messages
 * streamed ou normalisés au chargement), on les utilise tels quels : c'est ce
 * qui permet d'intercaler les appels d'outil dans le flux du texte. Sinon
 * (legacy sessions / vieilles sessions), on reconstruit un rendu legacy : texte puis outils.
 */
const renderParts = computed<ChatMessagePart[]>(() => {
  if (showThinkingPlaceholder.value) {
    return [thinkingPlaceholderPart.value];
  }

  if (props.message.parts?.length) return props.message.parts;
  const fallback: ChatMessagePart[] = [];
  if (props.message.thinking) {
    const thinkingPart: ChatThinkingPart = {
      type: 'thinking',
      id: `${props.message.id}__thinking`,
      thinkingId: 'think-0',
      content: props.message.thinking,
      done: true,
    };
    if (thinkingPart.content.trim()) {
      const subject = deriveThinkingSubjectDone(thinkingPart.content);
      if (subject) thinkingPart.subject = subject;
      const summary = deriveThinkingSummary(thinkingPart.content);
      if (summary) thinkingPart.summary = summary;
    }
    fallback.push(thinkingPart);
  }
  if (props.message.content || props.message.streaming) {
    fallback.push({ type: 'text', id: `${props.message.id}__text`, content: props.message.content });
  }
  for (const tc of props.message.toolCalls ?? []) {
    fallback.push({ type: 'tool_call', id: `${props.message.id}__tc_${tc.id}`, toolCallId: tc.id });
  }
  return fallback;
});

const groupedRenderBlocks = computed(() => groupMessageParts(renderParts.value));

function renderBlockKey(block: MessageRenderBlock): string {
  if (block.kind === 'activity_group') return block.group.id;
  return block.part.id;
}

const lastTextPartId = computed<string | null>(() => {
  const parts = renderParts.value;
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i].type === 'text') return parts[i].id;
  }
  return null;
});

const hasVisibleAssistantText = computed(() => {
  const parts = props.message.parts ?? [];
  const hasPartText = parts.some(
    (p) => p.type === 'text' && (p as { content?: string }).content?.trim().length,
  );
  if (hasPartText) return true;
  return Boolean(props.message.content?.trim());
});

const allToolCallsTerminal = computed(() => {
  const toolCalls = props.message.toolCalls ?? [];
  if (toolCalls.length === 0) return false;
  return toolCalls.every((tc) => tc.status === 'success' || tc.status === 'error');
});

const hasActiveToolCall = computed(() =>
  (props.message.toolCalls ?? []).some(
    (tc) =>
      tc.status === 'running' ||
      tc.status === 'pending_confirmation' ||
      tc.status === 'awaiting_confirmation',
  ),
);

const isThinkingDoneOrAbsent = computed(() => {
  const parts = props.message.parts ?? [];
  const thinkingParts = parts.filter(
    (p): p is ChatThinkingPart => p.type === 'thinking',
  );
  if (thinkingParts.length === 0) return true;
  return thinkingParts.every((part) => part.done);
});

/**
 * Indicateur « Suite de la génération… » affiché sous les outils terminés
 * tant que le tour stream encore sans texte assistant visible.
 */
const showContinuationPlaceholder = computed(() => {
  if (props.message.role !== 'assistant') return false;
  if (!props.message.streaming) return false;
  if (props.message.error) return false;
  if (showThinkingPlaceholder.value) return false;
  if (props.message.pendingConfirmation) return false;
  if (props.message.preparingConfirmation) return false;
  if (hasVisibleAssistantText.value) return false;
  if (hasActiveToolCall.value) return false;
  if (!isThinkingDoneOrAbsent.value) return false;
  if (allToolCallsTerminal.value) return true;
  return (props.message.toolCalls ?? []).length === 0;
});

const seenToolCallPartIds = new Set<string>();

function seedSeenToolCallPartIds(parts: ChatMessagePart[] | undefined): void {
  seenToolCallPartIds.clear();
  for (const part of parts ?? []) {
    if (part.type === 'tool_call') {
      seenToolCallPartIds.add(part.id);
    }
  }
}

watch(
  () => props.message.id,
  () => {
    seedSeenToolCallPartIds(props.message.parts);
  },
  { immediate: true },
);

/** Replie le raisonnement quand un tool_call nouveau suit immédiatement un thinking. */
watch(
  () => props.message.parts,
  (parts) => {
    if (!parts?.length) return;

    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i];
      if (part.type !== 'tool_call') continue;
      if (seenToolCallPartIds.has(part.id)) continue;

      seenToolCallPartIds.add(part.id);
      const preceding = parts[i - 1];
      if (preceding?.type === 'thinking') {
        const groupId = activityGroupIdAt(parts, i - 1);
        if (groupId) collapseActivityGroup(groupId);
      }
    }
  },
  { deep: true },
);
</script>

<style scoped lang="scss">
.chat-message__error {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border-radius: var(--wp-r-md);
  border: 1px solid color-mix(in srgb, var(--wp-danger) 45%, var(--wp-border));
  background: var(--wp-danger-soft);
  color: var(--wp-danger);
}

.chat-message__error-body {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1) var(--wp-space-2);
  align-items: baseline;
  min-width: 0;
  flex: 1;
}

.chat-message__error-msg {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  word-break: break-word;
}

.chat-message__error-code {
  display: inline-block;
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.8;
}

.chat-message__error-report {
  display: inline-flex;
  flex: 1 1 100%;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.chat-message__error-reconnect {
  display: inline-flex;
  flex: 1 1 100%;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.chat-message__continuation {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
}

.chat-message__continuation-spinner {
  flex: 0 0 auto;
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 999px;
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: chat-message-continuation-spin 0.7s linear infinite;
}

@keyframes chat-message-continuation-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
