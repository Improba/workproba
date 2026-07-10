<template>
  <div class="chat-view">
    <div class="chat-view__messages">
      <div v-if="messages.length === 0" class="chat-view__empty">
        <p class="chat-view__empty-hint">
          Posez une question sur vos documents, ou choisissez un point de départ :
        </p>
        <StartPrompts @select="applyPrompt" />
      </div>

      <MessageList
        v-else
        ref="messageListRef"
        :messages="messages"
        :project-path="projectPath"
        :session-id="sessionId"
        :confirming="confirming"
        @open-file="(path) => emit('open-file', path)"
        @restored="(path) => emit('restored', path)"
        @confirm-approve="emit('confirm-approve')"
        @confirm-deny="emit('confirm-deny')"
      />

      <Transition name="chat-scroll-fab">
        <button
          v-if="showScrollDown"
          type="button"
          class="chat-view__scroll-down"
          aria-label="Aller en bas"
          @click="scrollToBottom(true)"
        >
          <Lucide name="arrow-down" size="sm" color="text-invert" />
        </button>
      </Transition>
    </div>

    <form class="chat-view__composer" @submit.prevent="handleSubmit">
      <div class="chat-view__composer-field">
        <q-input
          ref="composerInputRef"
          v-model="draft"
          type="textarea"
          autogrow
          borderless
          class="chat-view__input"
          placeholder="Écrivez votre message…"
          @keydown.enter.ctrl.prevent="handleSubmit"
          @keydown.enter.meta.prevent="handleSubmit"
        />
        <p class="chat-view__composer-hint">
          Entrée = saut de ligne · Ctrl+Entrée pour envoyer
        </p>
      </div>
      <button
        v-if="streaming"
        type="button"
        class="chat-view__stop"
        aria-label="Arrêter"
        title="Arrêter"
        @click="emit('abort')"
      >
        <Lucide name="square" size="16" color="wp-canard" />
      </button>
      <button
        v-else
        type="submit"
        class="chat-view__send"
        :disabled="!canSend"
        aria-label="Envoyer"
      >
        <Lucide name="arrow-up" size="18" color="wp-canard" />
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useScroll } from '@vueuse/core';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import MessageList from '@components/chat/MessageList.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';
import type { ChatMessage } from '#types';
import type { QInput } from 'quasar';

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  projectPath?: string | null;
  sessionId?: string | null;
  confirming?: boolean;
}>();

const emit = defineEmits<{
  send: [text: string];
  abort: [];
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-deny': [];
}>();

const draft = ref('');
const composerInputRef = ref<QInput | null>(null);
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
const scrollTarget = ref<HTMLElement | null>(null);
const isPinned = ref(true);
let scrollRaf: number | null = null;

const { arrivedState } = useScroll(scrollTarget, { offset: { bottom: 80 } });

const showScrollDown = computed(
  () => !arrivedState.bottom && props.messages.length > 0,
);

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.streaming,
);

function applyPrompt(prompt: string): void {
  draft.value = prompt;
  void nextTick(() => {
    composerInputRef.value?.focus();
  });
}

function setDraft(text: string, focus = true): void {
  draft.value = text;
  if (focus) {
    void nextTick(() => {
      composerInputRef.value?.focus();
    });
  }
}

defineExpose({ setDraft });

function bindScrollTarget(): void {
  scrollTarget.value = messageListRef.value?.getScrollTarget() ?? null;
}

function scrollToBottom(smooth = false): void {
  const target = messageListRef.value?.getScrollTarget();
  if (!target) return;
  target.scrollTo({
    top: target.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto',
  });
}

// Scroll batché par rAF pendant le streaming : on évite les layout thrash
// (scrollTo à chaque flush de tokens) tout en restant collé au bas.
function scheduleScrollToBottom(): void {
  if (scrollRaf !== null) return;
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = null;
    scrollToBottom();
  });
}

function handleSubmit(): void {
  const text = draft.value.trim();
  if (!text || props.streaming) return;
  emit('send', text);
  draft.value = '';
  // L'utilisateur vient d'envoyer : on force le rappel en bas.
  isPinned.value = true;
  void nextTick(() => scrollToBottom());
}

// L'utilisateur scroll : on mémorise son intention (collé au bas ou non).
// isPinned est lu par les watches de contenu AVANT que arrivedState ne se
// mette à jour suite à la croissance du contenu, ce qui permet de rester
// collé tant que l'utilisateur n'est pas remonté.
watch(
  () => arrivedState.bottom,
  (bottom) => {
    isPinned.value = bottom;
  },
  { immediate: true },
);

watch(
  () => props.messages.length,
  async () => {
    bindScrollTarget();
    if (isPinned.value) {
      await nextTick();
      scrollToBottom();
    }
  },
);

watch(
  () => props.messages[props.messages.length - 1]?.content,
  () => {
    if (isPinned.value) scheduleScrollToBottom();
  },
);

onMounted(() => {
  bindScrollTarget();
  void nextTick(() => scrollToBottom());
});

onUnmounted(() => {
  if (scrollRaf !== null) {
    cancelAnimationFrame(scrollRaf);
    scrollRaf = null;
  }
  messageListRef.value = null;
  scrollTarget.value = null;
});
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--wp-surface);
  border-radius: var(--wp-r-lg);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;
}

.chat-view__messages {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-view__empty {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 1.5rem 1.25rem 2rem;
}

.chat-view__empty-hint {
  margin: 0;
  max-width: 34rem;
  text-align: center;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--wp-text-muted);
}

.chat-view__scroll-down {
  position: absolute;
  right: 1rem;
  bottom: 1rem;
  z-index: 2;
  width: 2.25rem;
  height: 2.25rem;
  border: none;
  border-radius: 999px;
  background: var(--primary);
  color: var(--text-invert);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--primary-highest) 25%, transparent);
  transition: transform 0.15s ease, opacity 0.15s ease;

  &:hover {
    transform: translateY(-1px);
  }
}

.chat-scroll-fab-enter-active,
.chat-scroll-fab-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.chat-scroll-fab-enter-from,
.chat-scroll-fab-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.chat-view__composer {
  display: flex;
  align-items: flex-end;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.chat-view__composer-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.chat-view__composer-hint {
  margin: 0;
  padding: 0 0.1rem;
  font-size: 0.7rem;
  color: var(--wp-text-faint);
  line-height: 1.2;
}

.chat-view__input {
  flex: 1;
  min-width: 0;
  padding: 0.3rem 0.7rem;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
  transition: border-color var(--wp-dur) var(--wp-ease),
    box-shadow var(--wp-dur) var(--wp-ease);

  &:focus-within {
    border-color: var(--wp-accent);
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }

  :deep(.q-field__native) {
    padding: 4px 0;
    min-height: 0;
  }

  :deep(textarea) {
    color: var(--wp-text);
    font-size: 0.875rem;
    line-height: 1.4;
    max-height: 140px;
  }

  :deep(textarea::placeholder) {
    color: var(--wp-text-muted);
    opacity: 1;
  }
}

.chat-view__send {
  flex: 0 0 auto;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 1px 2px color-mix(in srgb, var(--wp-accent) 35%, transparent);
  transition: background-color var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease), opacity var(--wp-dur) var(--wp-ease);

  &:disabled {
    background: var(--wp-surface-3);
    color: var(--wp-text-faint);
    box-shadow: none;
    opacity: 0.7;
    cursor: not-allowed;
  }

  &:not(:disabled):hover {
    background: var(--wp-accent-strong);
    transform: translateY(-1px);
  }

  &:not(:disabled):active {
    transform: translateY(0);
  }
}

.chat-view__stop {
  flex: 0 0 auto;
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-3);
  color: var(--wp-canard);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-danger-soft);
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0);
  }
}
</style>
