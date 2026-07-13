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
    <div
      v-if="isCompactionMessage"
      class="chat-message__compaction-card"
      role="note"
      :aria-label="t('chat.compactionSummary')"
    >
      <header class="chat-message__compaction-header">
        <Lucide name="archive" size="14" color="wp-text-muted" />
        <span class="chat-message__compaction-title">{{ t('chat.compactionSummary') }}</span>
      </header>
      <p class="chat-message__compaction-body">{{ compactionBody }}</p>
    </div>

    <template v-else>
    <header class="chat-message__header">
      <div class="chat-message__avatar" aria-hidden="true">
        <Lucide
          :name="message.role === 'user' ? 'user' : 'sparkles'"
          size="14"
          :color="message.role === 'user' ? 'primary' : 'accent'"
        />
      </div>
      <span
        :id="`chat-message-role-${message.id}`"
        class="chat-message__role"
      >
        {{ roleLabel }}
      </span>
    </header>

    <div class="chat-message__body">
      <MessageAttachments
        v-if="message.role === 'user' && message.attachments?.length"
        :attachments="message.attachments"
        :attachment-statuses="attachmentStatuses"
        :settings-locked="settingsLocked"
      />
      <div
        v-if="showThinkingPlaceholder"
        class="chat-message__thinking-placeholder"
        aria-live="polite"
      >
        <button
          type="button"
          class="chat-message__thinking-toggle"
          :aria-expanded="thinkingPlaceholderExpanded"
          :aria-label="thinkingPlaceholderExpanded ? t('common.hide') : t('chat.thinkingToggleShow')"
          @click="thinkingPlaceholderExpanded = !thinkingPlaceholderExpanded"
        >
          <span class="chat-message__thinking-spinner" aria-hidden="true" />
          <span class="chat-message__thinking-text">{{ t('chat.thinking') }}</span>
          <span class="chat-message__thinking-hint">
            {{ thinkingPlaceholderExpanded ? t('common.hide') : t('common.show') }}
          </span>
          <Lucide
            name="chevron-down"
            size="xs"
            color="wp-text-muted"
            :class="thinkingPlaceholderExpanded ? 'chat-message__thinking-chevron chat-message__thinking-chevron--up' : 'chat-message__thinking-chevron'"
          />
        </button>
        <div
          v-if="thinkingPlaceholderExpanded"
          class="chat-message__thinking-body"
          role="region"
          :aria-label="t('chat.reasoningDetail')"
        >
          <p class="chat-message__thinking-empty">
            {{ t('chat.thinkingEmpty') }}
          </p>
        </div>
      </div>

      <template v-else>
        <template v-for="part in renderParts" :key="part.id">
        <MessageTextPart
          v-if="part.type === 'text'"
          :content="part.content"
          :streaming="!!message.streaming"
          :show-cursor="part.id === lastTextPartId && !!message.streaming"
        />
        <ThinkingCard
          v-else-if="part.type === 'thinking'"
          :thinking="part"
          :streaming="!!message.streaming"
        />
        <ToolCallCard
          v-else-if="part.type === 'tool_call' && toolCallById(part.toolCallId)"
          :tool-call="toolCallById(part.toolCallId)!"
          :project-path="projectPath"
          :session-id="sessionId"
          @open-file="(path) => emit('open-file', path)"
          @restored="(path) => emit('restored', path)"
        />
        <p
          v-else-if="part.type === 'tool_call'"
          class="chat-message__unknown-tool"
        >
          {{ t('chat.unknownTool') }}
        </p>
        <ConfirmationCard
          v-if="
            part.type === 'tool_call' &&
            message.pendingConfirmation?.toolCallId === part.toolCallId
          "
          :confirmation="message.pendingConfirmation!"
          :busy="confirming"
          :workspace-data-dir="workspaceDataDir"
          :project-path="projectPath"
          :tool-args="toolCallById(part.toolCallId)?.args"
          @approve="emit('confirm-approve')"
          @cancel="emit('confirm-deny')"
        />
        </template>
      </template>

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
        </div>
      </div>
    </div>
    </template>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import MessageAttachments from '@components/chat/MessageAttachments.vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';
import ToolCallCard from '@components/chat/ToolCallCard.vue';
import ConfirmationCard from '@components/chat/ConfirmationCard.vue';
import PlanCard from '@components/chat/PlanCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { usePlugins } from '@composables/usePlugins';
import { formatOpinionMarkdown } from '@composables/usePersonas';
import type { ChatMessage, ChatMessagePart, ChatToolCall } from '#types';

const props = defineProps<{
  message: ChatMessage;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
  confirming?: boolean;
  approvingPlan?: boolean;
  attachmentStatuses?: Record<string, import('@composables/useChatStream').AttachmentStatusEntry>;
  settingsLocked?: boolean;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-deny': [];
  'plan-approve': [];
  'plan-reject': [];
  'personas-another': [card: import('#types').PersonasOpinionCard];
  'personas-to-discussion': [card: import('#types').PersonasOpinionCard];
}>();

const thinkingPlaceholderExpanded = ref(false);
const opinionPublishOpen = ref(false);
const { t, locale } = useI18n();
const { isProjetPluginActive } = usePlugins();

const opinionPublishMarkdown = computed(() =>
  props.message.personasOpinion
    ? formatOpinionMarkdown(props.message.personasOpinion)
    : '',
);

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
  if (props.message.role === 'user') return t('chat.roleYou');
  if (props.message.role === 'system') return t('chat.compactionSummary');
  return t('chat.roleAssistant');
});

const isCompactionMessage = computed(
  () =>
    props.message.messageKind === 'compaction' || props.message.role === 'system',
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
 * (vieilles sessions), on reconstruit un rendu legacy : texte puis outils.
 */
const renderParts = computed<ChatMessagePart[]>(() => {
  if (props.message.parts?.length) return props.message.parts;
  const fallback: ChatMessagePart[] = [];
  if (props.message.thinking) {
    fallback.push({
      type: 'thinking',
      id: `${props.message.id}__thinking`,
      thinkingId: 'think-0',
      content: props.message.thinking,
      done: true,
    });
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

function toolCallById(id: string): ChatToolCall | undefined {
  return props.message.toolCalls?.find((tc) => tc.id === id);
}
</script>

<style scoped lang="scss">
.chat-message {
  width: 100%;
  padding: var(--wp-space-4) var(--wp-space-5);
  color: var(--wp-text);
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
  border-bottom: 1px solid var(--wp-border);
}

.chat-message--user {
  background: var(--wp-user-bubble-bg);
  border-bottom-color: var(--wp-user-bubble-border);
}

.chat-message--assistant {
  background: transparent;
}

.chat-message--compaction {
  background: var(--wp-surface-2);
  border-bottom-color: var(--wp-border);
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

.chat-message__header {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
}

.chat-message__avatar {
  flex: 0 0 auto;
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-message__role {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text-muted);
  line-height: var(--wp-lh-tight, 1.2);
}

.chat-message__body {
  min-width: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.chat-message__error {
  display: flex;
  align-items: flex-start;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-radius: var(--wp-r-sm);
  border: 1px solid var(--wp-danger);
  background: var(--wp-danger-soft);
  color: var(--wp-danger);
}

.chat-message__error-body {
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
  margin-top: var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.8;
}

.chat-message__thinking-placeholder {
  display: flex;
  flex-direction: column;
  padding: var(--wp-space-1) 0;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.chat-message__thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid transparent;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-3);
    border-color: var(--wp-border);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.chat-message__thinking-spinner {
  flex: 0 0 auto;
  width: 0.9rem;
  height: 0.9rem;
  border-radius: var(--wp-r-pill);
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: chat-thinking-spin 0.7s linear infinite;
}

.chat-message__thinking-text {
  font-weight: 500;
}

.chat-message__thinking-hint {
  flex: 0 0 auto;
  padding: 0.1rem var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-3);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

.chat-message__thinking-chevron {
  flex: 0 0 auto;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.chat-message__thinking-body {
  margin-top: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-3);
}

.chat-message__thinking-empty {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.chat-message__unknown-tool {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
}

@keyframes chat-thinking-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
