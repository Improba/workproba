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
        <MessagePartRenderer
          :message="message"
          :project-path="projectPath"
          :session-id="sessionId"
          :workspace-data-dir="workspaceDataDir"
          :confirming="confirming"
          :approving-plan="approvingPlan"
          :retry-disabled="!!chatStreaming || !!interactionLocked"
          :hide-retry="!isLastMessage"
          @open-file="(path) => emit('open-file', path)"
          @restored="(path) => emit('restored', path)"
          @confirm-approve="emit('confirm-approve')"
          @confirm-approve-remaining="emit('confirm-approve-remaining')"
          @confirm-deny="emit('confirm-deny')"
          @plan-approve="emit('plan-approve')"
          @plan-reject="emit('plan-reject')"
          @personas-another="(card) => emit('personas-another', card)"
          @personas-to-discussion="(card) => emit('personas-to-discussion', card)"
          @specialist-to-discussion="(card) => emit('specialist-to-discussion', card)"
          @specialist-retry="(id) => emit('specialist-retry', id)"
          @error-reconnect="(cta) => emit('error-reconnect', cta)"
        />

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
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageAttachments from '@components/chat/MessageAttachments.vue';
import MessagePartRenderer from '@components/chat/MessagePartRenderer.vue';
import { isCompactionMessageLike } from '@utils/compactionMessage';
import { getAssistantCopyText } from '@utils/messageCopy';
import type { ChatMessage } from '#types';

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
  isLastMessage?: boolean;
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
  'specialist-to-discussion': [card: import('#types').SpecialistHandoffCard];
  'specialist-retry': [messageId: string];
  regenerate: [messageId: string];
  'error-reconnect': [cta: 'login' | 'enroll'];
}>();

const copyLabel = ref('');
const { t } = useI18n();

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
