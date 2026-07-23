<template>
  <article
    class="chat-message"
    :data-message-id="message.id"
    :class="{
      'chat-message--user': message.role === 'user',
      'chat-message--assistant': message.role === 'assistant',
      'chat-message--compaction': isCompactionMessage,
    }"
    :aria-labelledby="`chat-message-role-${message.id}`"
  >
    <span
      :id="`chat-message-role-${message.id}`"
      class="wp-sr-only chat-message__role"
    >{{ roleLabel }}</span>

    <div
      v-if="isCompactionMessage"
      class="chat-message__compaction-card"
    >
      <header class="chat-message__compaction-header">
        <Lucide name="archive" size="14" color="wp-text-muted" />
        <span class="chat-message__compaction-title">{{ t('chat.compactionSummary') }}</span>
      </header>
      <p class="chat-message__compaction-body">{{ compactionBody }}</p>
    </div>

    <div v-else class="chat-message__frame">
      <div class="chat-message__body">
        <MessageAttachments
          v-if="message.role === 'user' && message.attachments?.length"
          :attachments="message.attachments"
          :attachment-statuses="attachmentStatuses"
          :settings-locked="settingsLocked"
        />
        <ThinkingCard
          v-if="showThinkingPlaceholder"
          :thinking="thinkingPlaceholderPart"
          :streaming="true"
        />

        <template v-else>
          <template v-for="part in renderParts" :key="part.id">
            <MessageTextPart
              v-if="part.type === 'text' && Boolean(part.content?.trim())"
              :content="part.content"
              :streaming="!!message.streaming"
              :show-cursor="part.id === lastTextPartId && !!message.streaming"
            />
            <ThinkingCard
              v-else-if="part.type === 'thinking'"
              :thinking="part"
              :streaming="!!message.streaming"
            />
            <div
              v-else-if="part.type === 'tool_call' && toolCallById(part.toolCallId)"
              :class="{
                'chat-message__confirmation-group':
                  message.pendingConfirmation?.toolCallId === part.toolCallId ||
                  message.preparingConfirmation?.toolCallId === part.toolCallId,
              }"
            >
              <ToolCallCard
                :tool-call="toolCallById(part.toolCallId)!"
                :project-path="projectPath"
                :session-id="sessionId"
                :confirmation-active="
                  message.pendingConfirmation?.toolCallId === part.toolCallId ||
                  message.preparingConfirmation?.toolCallId === part.toolCallId
                "
                @open-file="(path) => emit('open-file', path)"
                @restored="(path) => emit('restored', path)"
              />
              <ConfirmationCard
                v-if="message.preparingConfirmation?.toolCallId === part.toolCallId && !message.pendingConfirmation"
                :confirmation="preparingConfirmationStub(part.toolCallId)"
                preparing
                attached
              />
              <ConfirmationCard
                v-if="message.pendingConfirmation?.toolCallId === part.toolCallId"
                :confirmation="message.pendingConfirmation!"
                :busy="confirming"
                :workspace-data-dir="workspaceDataDir"
                :project-path="projectPath"
                :tool-args="toolCallById(part.toolCallId)?.args"
                attached
                @approve="emit('confirm-approve')"
                @approve-remaining="emit('confirm-approve-remaining')"
                @cancel="emit('confirm-deny')"
              />
            </div>
            <p
              v-else-if="part.type === 'tool_call'"
              class="chat-message__unknown-tool"
            >
              {{ t('chat.unknownTool') }}
            </p>
          </template>
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

        <footer
          v-if="showCopyAction || showRegenerateAction"
          class="chat-message__actions"
        >
          <button
            v-if="showRegenerateAction"
            type="button"
            class="chat-message__action"
            :aria-label="t('chat.regenerateAria')"
            @click="emit('regenerate', message.id)"
          >
            <Lucide name="rotate-ccw" size="xs" color="wp-text-muted" />
            <span>{{ t('chat.regenerate') }}</span>
          </button>
          <button
            v-if="showCopyAction"
            type="button"
            class="chat-message__action"
            :aria-label="t('chat.copyMessageAria')"
            @click="copyAssistantMessage"
          >
            <Lucide name="copy" size="xs" color="wp-text-muted" />
            <span>{{ copyLabel }}</span>
          </button>
        </footer>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import MessageAttachments from '@components/chat/MessageAttachments.vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';
import ToolCallCard from '@components/chat/ToolCallCard.vue';
import ConfirmationCard from '@components/chat/ConfirmationCard.vue';
import PlanCard from '@components/chat/PlanCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import MemoryCitationsBar from '@components/chat/MemoryCitationsBar.vue';
import WebSearchCitationsBar from '@components/chat/WebSearchCitationsBar.vue';
import { extractWebSearchCitations } from '@utils/webSearchCitations';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { collapseThinking } from '@composables/useToolCallExpansion';
import { useErrorReport } from '@composables/useErrorReport';
import { usePlugins } from '@composables/usePlugins';
import { formatOpinionMarkdown } from '@composables/usePersonas';
import { isCompactionMessageLike } from '@utils/compactionMessage';
import { chatErrorReconnectCta } from '@utils/chatCloudErrors';
import { getAssistantCopyText } from '@utils/messageCopy';
import {
  deriveThinkingSubjectDone,
  deriveThinkingSummary,
} from '@utils/thinkingPresentation';
import type { ChatConfirmation, ChatMessage, ChatMessagePart, ChatThinkingPart, ChatToolCall } from '#types';

const props = defineProps<{
  message: ChatMessage;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
  confirming?: boolean;
  approvingPlan?: boolean;
  attachmentStatuses?: Record<string, import('@composables/useChatStream').AttachmentStatusEntry>;
  settingsLocked?: boolean;
  /** Un tour est en cours dans la conversation (désactive la régénération). */
  chatStreaming?: boolean;
  /** Confirmation ou plan en attente : bloque la régénération. */
  interactionLocked?: boolean;
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
  regenerate: [messageId: string];
  'error-reconnect': [cta: 'login' | 'enroll'];
}>();

const copyLabel = ref('');
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

const roleLabel = computed(() => {
  if (isCompactionMessage.value) return t('chat.compactionSummary');
  if (props.message.role === 'user') return t('chat.roleYou');
  return t('chat.roleAssistant');
});

const isCompactionMessage = computed(() =>
  isCompactionMessageLike(
    props.message.role,
    props.message.content,
    props.message.messageKind,
  ),
);

const compactionBody = computed(() => {
  const prefix = t('chat.compactionContentPrefix');
  const content = props.message.content ?? '';
  return content.startsWith(prefix) ? content.slice(prefix.length) : content;
});

/**
 * Segments ordonnés à rendre. Si le message dispose de `parts` (messages
 * streamed ou normalisés au chargement), on les utilise tels quels : c'est ce
 * qui permet d'intercaler les appels d'outil dans le flux du texte. Sinon
 * (legacy sessions / vieilles sessions), on reconstruit un rendu legacy : texte puis outils.
 */
const renderParts = computed<ChatMessagePart[]>(() => {
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

const lastTextPartId = computed<string | null>(() => {
  const parts = renderParts.value;
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i].type === 'text') return parts[i].id;
  }
  return null;
});

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

function preparingConfirmationStub(toolCallId: string): ChatConfirmation {
  const preparing = props.message.preparingConfirmation;
  return {
    confirmationId: '',
    toolCallId,
    toolName: preparing?.toolName ?? '',
    action: 'create',
    proposedPath: '',
    humanSummary: '',
  };
}

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

const copyableText = computed(() =>
  props.message.role === 'assistant' ? getAssistantCopyText(props.message) : '',
);

const showCopyAction = computed(
  () =>
    props.message.role === 'assistant' &&
    !props.message.streaming &&
    !props.chatStreaming &&
    !props.message.error &&
    copyableText.value.length > 0,
);

const showRegenerateAction = computed(
  () =>
    props.message.role === 'assistant' &&
    !props.message.streaming &&
    !props.chatStreaming &&
    !props.message.pendingConfirmation &&
    props.message.pendingPlan?.status !== 'pending' &&
    !isCompactionMessage.value &&
    !props.interactionLocked,
);

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
        collapseThinking(preceding.id);
      }
    }
  },
  { deep: true },
);

copyLabel.value = t('chat.copyMessage');

async function copyAssistantMessage(): Promise<void> {
  const text = copyableText.value;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copyLabel.value = t('chat.copyMessageDone');
    setTimeout(() => {
      copyLabel.value = t('chat.copyMessage');
    }, 1500);
  } catch {
    copyLabel.value = t('chat.copyMessageFailed');
    setTimeout(() => {
      copyLabel.value = t('chat.copyMessage');
    }, 1500);
  }
}

function toolCallById(id: string): ChatToolCall | undefined {
  return props.message.toolCalls?.find((tc) => tc.id === id);
}
</script>

<style scoped lang="scss">
.chat-message {
  width: 100%;
  padding: var(--wp-space-2) 0;
  color: var(--wp-text);
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
}

.chat-message__frame {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-message--user {
  display: flex;
  justify-content: flex-end;

  .chat-message__frame {
    max-width: min(100%, 38rem);
    padding: var(--wp-space-3) var(--wp-space-4);
    border-radius: var(--wp-r-lg);
    border: 1px solid color-mix(in srgb, var(--wp-user-bubble-border) 55%, transparent);
    background: var(--wp-user-bubble-bg);
    box-shadow: var(--wp-shadow-1);
  }
}

.chat-message--assistant {
  .chat-message__frame {
    padding: 0;
  }
}

.chat-message--compaction {
  .chat-message__compaction-card {
    margin: 0 var(--wp-space-1);
  }
}

.chat-message__compaction-card {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-3);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.chat-message__compaction-header {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
}

.chat-message__compaction-title {
  font-weight: 600;
  color: var(--wp-text-muted);
}

.chat-message__compaction-body {
  margin: 0;
  line-height: var(--wp-lh-normal);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--wp-text);
}

.chat-message__body {
  min-width: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.chat-message__confirmation-group {
  display: flex;
  flex-direction: column;
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;

  :deep(.tool-call-card) {
    box-shadow: none;
    border-bottom: none;
    border-radius: var(--wp-r-md) var(--wp-r-md) 0 0;
  }

  :deep(.confirmation-card) {
    margin-top: 0;
    box-shadow: none;
    border-radius: 0 0 var(--wp-r-md) var(--wp-r-md);
    border-top: 1px dashed color-mix(in srgb, var(--wp-accent) 35%, var(--wp-border));
  }
}

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

.chat-message__unknown-tool {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
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

.chat-message__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-1);
}

.chat-message__action {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid transparent;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    color var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--wp-surface-3);
    border-color: var(--wp-border);
    color: var(--wp-text);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}
</style>
