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

    <div
      class="chat-view__composer"
      :class="{ 'chat-view__composer--expanded': hasDraft }"
    >
      <form class="chat-view__composer-form" @submit.prevent="handleSubmit">
        <div class="chat-view__composer-field">
          <q-input
            ref="composerInputRef"
            v-model="draft"
            type="textarea"
            autogrow
            borderless
            class="chat-view__input"
            placeholder="Écrivez votre message…"
            :maxlength="COMPOSER_MAX_LENGTH"
            counter
            @keydown.enter.ctrl.prevent="handleSubmit"
            @keydown.enter.meta.prevent="handleSubmit"
          />
        </div>

        <div class="chat-view__composer-actions">
          <div class="chat-view__composer-actions-left">
            <ChatModelControl
              v-if="showModelControl"
              :model-value="reasoningEffort ?? 'none'"
              :provider="reasoningProvider"
              :model="reasoningModel"
              @update:model-value="(value) => emit('update:reasoningEffort', value)"
              @update:model="(value) => emit('update:reasoningModel', value)"
            />
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
        </div>
      </form>

      <p v-if="hasDraft" class="chat-view__composer-hint">
        Entrée = saut de ligne · Ctrl+Entrée pour envoyer
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useScroll } from '@vueuse/core';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import ChatModelControl from '@components/chat/ChatModelControl.vue';
import MessageList from '@components/chat/MessageList.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';
import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ChatMessage, ReasoningEffort } from '#types';
import type { QInput } from 'quasar';
import { supportsReasoning } from '@utils/reasoningSupport';
import { hasModelChoice } from '@utils/modelCatalog';

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  projectPath?: string | null;
  sessionId?: string | null;
  confirming?: boolean;
  reasoningEffort?: ReasoningEffort | null;
  reasoningProvider?: LlmProviderName | null;
  reasoningModel?: string | null;
}>();

const emit = defineEmits<{
  send: [text: string];
  abort: [];
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-deny': [];
  'update:reasoningEffort': [value: ReasoningEffort];
  'update:reasoningModel': [model: string];
}>();

const COMPOSER_MAX_LENGTH = 8000;

const showModelControl = computed(() => {
  const provider = props.reasoningProvider;
  const model = props.reasoningModel;
  if (!provider || !model) return false;
  return hasModelChoice(provider) || supportsReasoning(provider, model);
});

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
  () =>
    draft.value.trim().length > 0 &&
    draft.value.length <= COMPOSER_MAX_LENGTH &&
    !props.streaming,
);

const hasDraft = computed(() => draft.value.trim().length > 0);

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

const SCROLL_STABLE_MAX_ATTEMPTS = 4;
const SCROLL_STABLE_TIMEOUT_MS = 250;

/** Réessaie le scroll jusqu'à ce que scrollHeight se stabilise (virtual scroller). */
async function scrollToBottomStable(smooth = false): Promise<void> {
  await nextTick();
  const deadline = performance.now() + SCROLL_STABLE_TIMEOUT_MS;
  let lastHeight = -1;
  let attempts = 0;

  return new Promise<void>((resolve) => {
    const run = (): void => {
      const target = messageListRef.value?.getScrollTarget();
      if (!target) {
        if (attempts < SCROLL_STABLE_MAX_ATTEMPTS && performance.now() < deadline) {
          attempts += 1;
          requestAnimationFrame(run);
          return;
        }
        resolve();
        return;
      }

      const height = target.scrollHeight;
      scrollToBottom(smooth && attempts === 0);

      attempts += 1;
      const stable = height === lastHeight && lastHeight >= 0;
      lastHeight = height;

      if (stable || attempts >= SCROLL_STABLE_MAX_ATTEMPTS || performance.now() >= deadline) {
        resolve();
        return;
      }

      requestAnimationFrame(run);
    };

    requestAnimationFrame(run);
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
  if (!text || props.streaming || draft.value.length > COMPOSER_MAX_LENGTH) return;
  emit('send', text);
  draft.value = '';
  // L'utilisateur vient d'envoyer : on force le rappel en bas.
  isPinned.value = true;
  void scrollToBottomStable();
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
  () => {
    bindScrollTarget();
    if (isPinned.value) {
      void scrollToBottomStable();
    }
  },
);

watch(
  () => props.sessionId,
  () => {
    isPinned.value = true;
    bindScrollTarget();
    void scrollToBottomStable();
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
  void scrollToBottomStable();
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
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem 0.75rem 0.5rem;
  background: var(--wp-surface);
}

/* Pilule contenant le champ + les actions. Repliée = une ligne,
   dépliée (saisie) = le champ au-dessus, les actions en barre dessous. */
.chat-view__composer-form {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 4px 6px 4px 12px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  transition: border-color var(--wp-dur) var(--wp-ease),
    box-shadow var(--wp-dur) var(--wp-ease),
    border-radius var(--wp-dur) var(--wp-ease);

  &:focus-within {
    border-color: var(--wp-accent);
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }
}

.chat-view__composer--expanded .chat-view__composer-form {
  flex-direction: column;
  align-items: stretch;
  border-radius: var(--wp-r-lg);
  padding: 10px 10px 8px;
}

.chat-view__composer-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-view__composer--expanded .chat-view__composer-field {
  width: 100%;
}

.chat-view__composer-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: none;
}

.chat-view__composer--expanded .chat-view__composer-actions {
  width: 100%;
  justify-content: space-between;
  padding-top: 4px;
}

.chat-view__composer-actions-left {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.chat-view__composer-hint {
  margin: 0;
  padding: 0 0.4rem;
  font-size: 0.7rem;
  color: var(--wp-text-faint);
  line-height: 1.2;
}

.chat-view__input {
  flex: 1;
  min-width: 0;
  background: transparent;

  :deep(.q-field) {
    min-height: 0;
  }

  :deep(.q-field__control) {
    min-height: 0 !important;
    height: auto;
    padding: 0;
    align-items: center;
  }

  :deep(.q-field__control::before),
  :deep(.q-field__control::after) {
    display: none;
  }

  :deep(.q-field__native) {
    padding: 0;
    min-height: 0;
  }

  :deep(textarea) {
    color: var(--wp-text);
    font-size: 0.9rem;
    line-height: 1.5;
    max-height: 220px;
    resize: none;
    padding: 0;
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
  border-radius: var(--wp-r-pill);
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
  border-radius: var(--wp-r-pill);
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
