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
    <div class="chat-message__frame">
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
      <template v-if="editing">
        <label class="visually-hidden" :for="editFieldId">{{ t('chat.editMessageLabel') }}</label>
        <textarea
          :id="editFieldId"
          ref="editFieldRef"
          v-model="editDraft"
          class="chat-message__edit-field"
          rows="3"
          :maxlength="COMPOSER_MAX_LENGTH"
          @keydown.enter.ctrl.prevent="saveEdit"
          @keydown.enter.meta.prevent="saveEdit"
          @keydown.escape.prevent="cancelEdit"
        />
        <div class="chat-message__edit-actions">
          <button
            type="button"
            class="chat-message__action chat-message__action--ghost"
            @click="cancelEdit"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="chat-message__action chat-message__action--primary"
            :disabled="!canSaveEdit"
            @click="saveEdit"
          >
            {{ t('chat.editMessageSave') }}
          </button>
        </div>
      </template>
      <template v-else>
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
        <div
          v-else-if="part.type === 'tool_call' && toolCallById(part.toolCallId)"
          :class="{
            'chat-message__confirmation-group':
              message.pendingConfirmation?.toolCallId === part.toolCallId,
          }"
        >
          <ToolCallCard
            :tool-call="toolCallById(part.toolCallId)!"
            :project-path="projectPath"
            :session-id="sessionId"
            :confirmation-active="
              message.pendingConfirmation?.toolCallId === part.toolCallId
            "
            @open-file="(path) => emit('open-file', path)"
            @restored="(path) => emit('restored', path)"
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
      </template>

      <footer
        v-if="showUserActions"
        class="chat-message__actions"
      >
        <button
          type="button"
          class="chat-message__action"
          :aria-label="t('chat.editMessageAria')"
          @click="startEdit"
        >
          <Lucide name="pencil" size="xs" color="wp-text-muted" />
          <span>{{ t('chat.editMessage') }}</span>
        </button>
      </footer>

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
    </template>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
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
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { usePlugins } from '@composables/usePlugins';
import { formatOpinionMarkdown } from '@composables/usePersonas';
import { isCompactionMessageLike } from '@utils/compactionMessage';
import { getAssistantCopyText } from '@utils/messageCopy';
import type { ChatMessage, ChatMessagePart, ChatThinkingPart, ChatToolCall } from '#types';

const props = defineProps<{
  message: ChatMessage;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
  confirming?: boolean;
  approvingPlan?: boolean;
  attachmentStatuses?: Record<string, import('@composables/useChatStream').AttachmentStatusEntry>;
  settingsLocked?: boolean;
  /** Un tour est en cours dans la conversation (désactive édition / régénération). */
  chatStreaming?: boolean;
  /** Confirmation ou plan en attente : bloque édition / régénération. */
  interactionLocked?: boolean;
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
  edit: [messageId: string, newText: string];
  regenerate: [messageId: string];
}>();

const COMPOSER_MAX_LENGTH = 32_000;
const editing = ref(false);
const editDraft = ref('');
const editFieldRef = ref<HTMLTextAreaElement | null>(null);
const editFieldId = computed(() => `chat-edit-${props.message.id}`);

const copyLabel = ref('');
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

const thinkingPlaceholderPart = computed<ChatThinkingPart>(() => ({
  type: 'thinking',
  id: `${props.message.id}__thinking-placeholder`,
  thinkingId: `${props.message.id}__thinking-placeholder`,
  content: '',
  done: false,
}));

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

const showUserActions = computed(
  () =>
    props.message.role === 'user' &&
    !props.message.streaming &&
    !props.chatStreaming &&
    !isCompactionMessage.value &&
    !editing.value &&
    !props.interactionLocked,
);

const canSaveEdit = computed(
  () =>
    editDraft.value.trim().length > 0 &&
    editDraft.value.length <= COMPOSER_MAX_LENGTH &&
    editDraft.value.trim() !== props.message.content.trim(),
);

function startEdit(): void {
  editDraft.value = props.message.content;
  editing.value = true;
  void nextTick(() => {
    const field = editFieldRef.value;
    if (!field) return;
    field.focus();
    field.setSelectionRange(field.value.length, field.value.length);
  });
}

function cancelEdit(): void {
  editing.value = false;
  editDraft.value = '';
}

watch(
  () => props.message.id,
  () => {
    editing.value = false;
    editDraft.value = '';
  },
);

function saveEdit(): void {
  if (!canSaveEdit.value) return;
  emit('edit', props.message.id, editDraft.value.trim());
  editing.value = false;
  editDraft.value = '';
}

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
  gap: var(--wp-space-2);
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

  .chat-message__role {
    color: var(--wp-user-bubble-text);
  }
}

.chat-message--assistant {
  .chat-message__frame {
    padding: var(--wp-space-1) 0;
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

.chat-message__header {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
}

.chat-message__avatar {
  flex: 0 0 auto;
  width: 1.625rem;
  height: 1.625rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
}

.chat-message--user .chat-message__avatar {
  background: color-mix(in srgb, var(--wp-primary) 10%, var(--wp-user-bubble-bg));
}

.chat-message--assistant .chat-message__avatar {
  background: var(--wp-accent-soft);
}

.chat-message--assistant .chat-message__role {
  color: var(--wp-text-muted);
}

.chat-message__role {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--wp-text-faint);
  line-height: var(--wp-lh-tight, 1.2);
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

.chat-message__unknown-tool {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
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

  &--primary {
    color: var(--text-invert);
    background: var(--primary);
    border-color: transparent;

    &:hover:not(:disabled) {
      background: var(--primary-hover, var(--primary));
      color: var(--text-invert);
      border-color: transparent;
    }
  }

  &--ghost {
    border-color: var(--wp-border);
  }
}

.chat-message__edit-field {
  width: 100%;
  min-height: 4.5rem;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  color: var(--wp-text);
  font: inherit;
  line-height: var(--wp-lh-relaxed);
  resize: vertical;

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.chat-message__edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-2);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
