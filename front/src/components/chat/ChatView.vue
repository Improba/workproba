<template>
  <div
    class="chat-view"
    :class="{
      'chat-view--embedded': embedded || layoutMode === 'hub',
      'chat-view--hub': layoutMode === 'hub',
    }"
  >
    <div
      class="chat-view__messages"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div v-if="messages.length === 0" class="chat-view__empty">
        <h2 class="chat-view__empty-hero">{{ emptyHeroTitle }}</h2>
        <p class="chat-view__empty-hint">{{ t('chat.emptyHint') }}</p>
        <StartPrompts variant="chips" @select="applyPrompt" />
      </div>

      <MessageList
        v-else
        ref="messageListRef"
        :messages="messages"
        :streaming="streaming"
        :spacer-height="spacerHeight"
        :project-path="projectPath"
        :session-id="sessionId"
        :workspace-data-dir="workspaceDataDir"
        :confirming="confirming"
        :approving-plan="approvingPlan"
        :attachment-statuses="attachmentStatuses"
        :settings-locked="settingsLocked"
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
        @regenerate="(id) => emit('regenerate', id)"
        @error-reconnect="(cta) => emit('error-reconnect', cta)"
      />

      <Transition name="chat-scroll-fab">
        <button
          v-if="showScrollDown"
          type="button"
          class="chat-view__scroll-down"
          :aria-label="t('chat.scrollDown')"
          @click="handleScrollDownClick"
        >
          <Lucide name="arrow-down" size="sm" color="text-invert" />
        </button>
      </Transition>

      <Transition name="chat-drop-overlay">
        <div
          v-if="isDragOver"
          class="chat-view__drop-overlay"
          aria-hidden="true"
        >
          <div class="chat-view__drop-card">
            <Lucide name="plus" size="md" color="wp-accent" />
            <span class="chat-view__drop-text">{{ t('chat.dropFiles') }}</span>
            <span class="chat-view__drop-hint">{{ t('chat.dropFilesHint') }}</span>
          </div>
        </div>
      </Transition>
    </div>

    <ChatComposer
      ref="composerRef"
      :messages="messages"
      :streaming="streaming"
      :workspace-data-dir="workspaceDataDir"
      :personas-enabled="personasEnabled"
      :reasoning-effort="reasoningEffort"
      :reasoning-provider="reasoningProvider"
      :reasoning-model="reasoningModel"
      :settings-locked="settingsLocked"
      :stream-error="streamError"
      :stream-error-reconnect="streamErrorReconnect"
      @send="(text, attachments) => emit('send', text, attachments)"
      @abort="emit('abort')"
      @update:reasoning-effort="(value) => emit('update:reasoningEffort', value)"
      @update:reasoning-model="(model) => emit('update:reasoningModel', model)"
      @personas-open="emit('personas-open')"
      @personas-meeting="emit('personas-meeting')"
      @personas-discuss="emit('personas-discuss')"
      @stream-error-report="emit('stream-error-report')"
      @stream-error-retry="emit('stream-error-retry')"
      @stream-error-reconnect="emit('stream-error-reconnect')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import ChatComposer from '@components/chat/ChatComposer.vue';
import MessageList from '@components/chat/MessageList.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';
import type { LlmProviderName } from '@composables/useDesktop.types';
import type { ChatAttachment, ChatError, ChatMessage, ReasoningEffort } from '#types';
import { useChatScroll } from '@composables/useChatScroll';

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  projectPath?: string | null;
  sessionId?: string | null;
  workspaceDataDir?: string | null;
  confirming?: boolean;
  approvingPlan?: boolean;
  attachmentStatuses?: Record<string, import('@composables/useChatStream').AttachmentStatusEntry>;
  settingsLocked?: boolean;
  personasEnabled?: boolean;
  reasoningEffort?: ReasoningEffort | null;
  reasoningProvider?: LlmProviderName | null;
  reasoningModel?: string | null;
  embedded?: boolean;
  emptyHero?: string | null;
  layout?: 'chat' | 'hub';
  streamError?: ChatError | null;
  streamErrorReconnect?: 'login' | 'enroll' | null;
}>();

const emit = defineEmits<{
  send: [text: string, attachments: ChatAttachment[]];
  abort: [];
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-approve-remaining': [];
  'confirm-deny': [];
  'plan-approve': [];
  'plan-reject': [];
  'update:reasoningEffort': [value: ReasoningEffort];
  'update:reasoningModel': [model: string];
  'personas-open': [];
  'personas-meeting': [];
  'personas-discuss': [];
  'personas-another': [card: import('#types').PersonasOpinionCard];
  'personas-to-discussion': [card: import('#types').PersonasOpinionCard];
  'specialist-to-discussion': [card: import('#types').SpecialistHandoffCard];
  regenerate: [messageId: string];
  'stream-error-report': [];
  'stream-error-retry': [];
  'stream-error-reconnect': [];
  'error-reconnect': [cta: 'login' | 'enroll'];
}>();

const { t } = useI18n();

const layoutMode = computed(() => props.layout ?? 'chat');

const emptyHeroTitle = computed(
  () => props.emptyHero?.trim() || t('home.heroQuestion'),
);

const composerRef = ref<InstanceType<typeof ChatComposer> | null>(null);
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
const isDragOver = ref(false);
const dragCounter = ref(0);

const {
  spacerHeight,
  showScrollDown,
  handleScrollDownClick,
  enterAnchorMode,
  enterStickyMode,
  detachFromBottom,
  getScrollState,
  beginProgrammaticScrollForTest,
} = useChatScroll({
  listRef: messageListRef,
  messages: computed(() => props.messages),
  streaming: computed(() => props.streaming),
  sessionId: computed(() => props.sessionId),
});

function setDraft(text: string, focus = true): void {
  composerRef.value?.setDraft(text, focus);
}

defineExpose({
  setDraft,
  /** API scroll (prod + lab bureau + tests). */
  getScrollState,
  enterAnchorMode,
  enterStickyMode,
  detachFromBottom,
  handleScrollDownClick,
  /** Aliases tests historiques. */
  detachFromBottomForTest: detachFromBottom,
  beginProgrammaticScrollForTest,
  handleScrollDownClickForTest: handleScrollDownClick,
});

function applyPrompt(prompt: string): void {
  composerRef.value?.setDraft(prompt);
}

function onDragEnter(): void {
  dragCounter.value += 1;
  isDragOver.value = true;
}

function onDragLeave(): void {
  dragCounter.value = Math.max(0, dragCounter.value - 1);
  if (dragCounter.value === 0) isDragOver.value = false;
}

function onDrop(event: DragEvent): void {
  dragCounter.value = 0;
  isDragOver.value = false;
  composerRef.value?.addFiles(event.dataTransfer?.files ?? null);
}
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

  &--embedded {
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }

  &--hub {
    height: auto;
    min-height: 0;
    overflow: visible;
    width: 100%;

    .chat-view__messages {
      flex: none;
      width: 100%;
    }

    .chat-view__empty {
      flex: none;
      width: 100%;
      gap: 0.85rem;
      padding: 0 0 1rem;
      align-items: center;
    }

    .chat-view__empty-hero,
    .chat-view__empty-hint {
      width: 100%;
      max-width: none;
    }

    .chat-view__empty-hero {
      font-size: clamp(1.35rem, 2.5vw, 1.65rem);
      letter-spacing: -0.02em;
    }

    .chat-view__empty-hint {
      font-size: var(--wp-fs-sm);
      color: var(--wp-text-faint);
    }

    :deep(.chat-composer) {
      max-width: none;
      width: 100%;
      margin: 0;
      padding: 0;
      background: transparent;
    }

    :deep(.start-prompts--chips) {
      width: 100%;
    }
  }
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
  justify-content: flex-start;
  gap: 1rem;
  padding: 2.5rem 1.25rem 2rem;
}

.chat-view__empty-hero {
  margin: 0;
  max-width: 34rem;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xl);
  font-weight: 700;
  line-height: 1.25;
  color: var(--wp-text);
  text-align: center;
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
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 14px
    color-mix(in srgb, var(--wp-accent-strong) 25%, transparent);
  transition:
    transform 0.15s ease,
    opacity 0.15s ease;

  &:hover {
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-accent-strong);
    outline-offset: 2px;
  }
}

.chat-scroll-fab-enter-active,
.chat-scroll-fab-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.chat-scroll-fab-enter-from,
.chat-scroll-fab-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.chat-view__drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: color-mix(in srgb, var(--wp-surface) 80%, transparent);
  backdrop-filter: blur(2px);
}

.chat-view__drop-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 1.5rem 2.25rem;
  border: 2px dashed var(--wp-accent);
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface-2);
  box-shadow: var(--wp-shadow-1);
}

.chat-view__drop-text {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--wp-text);
}

.chat-view__drop-hint {
  font-size: 0.75rem;
  color: var(--wp-text-muted);
}

.chat-drop-overlay-enter-active,
.chat-drop-overlay-leave-active {
  transition: opacity 0.15s ease;
}

.chat-drop-overlay-enter-from,
.chat-drop-overlay-leave-to {
  opacity: 0;
}
</style>
