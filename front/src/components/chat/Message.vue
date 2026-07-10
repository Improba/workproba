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
      <span class="sr-only">{{ roleLabel }}</span>
      <Lucide
        :name="message.role === 'user' ? 'user' : 'sparkles'"
        size="14"
        :color="message.role === 'user' ? 'primary' : 'accent'"
      />
    </div>

    <div class="chat-message__bubble">
      <div
        v-if="showThinkingPlaceholder"
        class="chat-message__thinking-placeholder"
        aria-live="polite"
      >
        <button
          type="button"
          class="chat-message__thinking-toggle"
          :aria-expanded="thinkingPlaceholderExpanded"
          :aria-label="thinkingPlaceholderExpanded ? 'Masquer' : 'Voir ce que fait le modèle'"
          @click="thinkingPlaceholderExpanded = !thinkingPlaceholderExpanded"
        >
          <span class="chat-message__thinking-spinner" aria-hidden="true" />
          <span class="chat-message__thinking-text">Le modèle réfléchit…</span>
          <span class="chat-message__thinking-hint">
            {{ thinkingPlaceholderExpanded ? 'Masquer' : 'Voir le détail' }}
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
          aria-label="Détail du raisonnement"
        >
          <p class="chat-message__thinking-empty">
            Le modèle prépare sa réponse. Le détail du raisonnement apparaîtra ici
            dès qu’il sera disponible.
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
          Appel d'outil indisponible
        </p>
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
import { computed, ref } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';
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

const thinkingPlaceholderExpanded = ref(false);

const roleLabel = computed(() =>
  props.message.role === 'user' ? 'Vous' : 'Assistant',
);

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
 * Indicateur « Le modèle réfléchit… » affiché dans la bulle assistant tant
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

.chat-message__thinking-placeholder {
  display: flex;
  flex-direction: column;
  padding: 0.15rem 0;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.chat-message__thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.4rem;
  border: 1px solid transparent;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
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
  border-radius: 999px;
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: chat-thinking-spin 0.7s linear infinite;
}

.chat-message__thinking-text {
  font-weight: 500;
}

.chat-message__thinking-hint {
  flex: 0 0 auto;
  padding: 0.1rem 0.5rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
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
  margin-top: 0.4rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
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

.sr-only {
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

@keyframes chat-thinking-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
