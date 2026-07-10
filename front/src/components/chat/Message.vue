<template>
  <div
    class="chat-message"
    :data-message-id="message.id"
    :class="{
      'chat-message--user': message.role === 'user',
      'chat-message--assistant': message.role === 'assistant',
    }"
  >
    <div class="chat-message__avatar" aria-hidden="true">
      <Lucide
        :name="message.role === 'user' ? 'user' : 'sparkles'"
        size="14"
        :color="message.role === 'user' ? 'primary' : 'accent'"
      />
    </div>

    <div class="chat-message__bubble">
      <template v-for="part in renderParts" :key="part.id">
        <MessageTextPart
          v-if="part.type === 'text'"
          :content="part.content"
          :streaming="!!message.streaming"
          :show-cursor="part.id === lastTextPartId && !!message.streaming"
        />
        <ToolCallCard
          v-else-if="toolCallById(part.toolCallId)"
          :tool-call="toolCallById(part.toolCallId) as ChatToolCall"
          :project-path="projectPath"
          :session-id="sessionId"
          @open-file="(path) => emit('open-file', path)"
          @restored="(path) => emit('restored', path)"
        />
        <ConfirmationCard
          v-if="
            part.type === 'tool_call' &&
            message.pendingConfirmation?.toolCallId === part.toolCallId
          "
          :confirmation="message.pendingConfirmation!"
          :busy="confirming"
          @approve="emit('confirm-approve')"
          @cancel="emit('confirm-deny')"
        />
      </template>

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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import ToolCallCard from '@components/chat/ToolCallCard.vue';
import ConfirmationCard from '@components/chat/ConfirmationCard.vue';
import type { ChatMessage, ChatMessagePart, ChatToolCall } from '#types';

const props = defineProps<{
  message: ChatMessage;
  projectPath?: string | null;
  sessionId?: string | null;
  confirming?: boolean;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-deny': [];
}>();

/**
 * Segments ordonnés à rendre. Si le message dispose de `parts` (messages
 * streamed ou normalisés au chargement), on les utilise tels quels : c'est ce
 * qui permet d'intercaler les appels d'outil dans le flux du texte. Sinon
 * (vieilles sessions), on reconstruit un rendu legacy : texte puis outils.
 */
const renderParts = computed<ChatMessagePart[]>(() => {
  if (props.message.parts?.length) return props.message.parts;
  const fallback: ChatMessagePart[] = [];
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

function toolCallById(id: string): ChatToolCall | undefined {
  return props.message.toolCalls?.find((tc) => tc.id === id);
}
</script>

<style scoped lang="scss">
.chat-message {
  display: flex;
  gap: 0.6rem;
  align-items: flex-start;
  max-width: 100%;

  // User à droite : on inverse l'axe pour reporter l'avatar à droite
  // et aligner la bulle sur le bord droit.
  &--user {
    flex-direction: row-reverse;
  }
}

.chat-message__avatar {
  flex: 0 0 auto;
  width: 1.6rem;
  height: 1.6rem;
  margin-top: 0.2rem;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--neutral-lower);
}

.chat-message__bubble {
  min-width: 0;
  // La bulle épouse le contenu, sans dépasser ~85% du conteneur (laisse
  // de la place pour les blocs de code tout en gardant un rendu "bulle").
  max-width: min(85%, 44rem);
  padding: 0.7rem 0.95rem;
  border-radius: 14px;
  border: 1px solid var(--wp-border);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: 0.875rem;
  line-height: 1.5;
  // Queue de bulle côté assistant (bas-gauche).
  border-bottom-left-radius: 4px;
  // Les segments d'outil s'intercalent : on aère un peu entre segments.
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.chat-message--user .chat-message__bubble {
  background: var(--primary-lowest);
  border-color: var(--primary-low);
  // Queue de bulle côté user (bas-droite).
  border-bottom-left-radius: 14px;
  border-bottom-right-radius: 4px;
}

.chat-message__error {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
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
  font-size: 0.8125rem;
  line-height: 1.4;
  word-break: break-word;
}

.chat-message__error-code {
  display: inline-block;
  margin-top: 0.2rem;
  font-size: 0.7rem;
  font-family: var(--wp-font-mono, ui-monospace, monospace);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.8;
}
</style>
