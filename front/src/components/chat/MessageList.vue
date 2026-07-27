<template>
  <div class="message-list">
    <q-scroll-area
      ref="scrollAreaRef"
      class="message-list__scroller"
      role="log"
      :aria-live="ariaLiveMode"
      aria-relevant="additions"
    >
      <div
        v-if="messages.length"
        ref="contentRef"
        class="message-list__content"
      >
        <div
          v-for="(item, index) in messages"
          :key="item.id"
          :data-index="index"
          class="message-list__item-wrapper"
        >
          <Message
            :message="item"
            :project-path="projectPath"
            :session-id="sessionId"
            :workspace-data-dir="workspaceDataDir"
            :confirming="confirming"
            :approving-plan="approvingPlan"
            :attachment-statuses="attachmentStatuses"
            :settings-locked="settingsLocked"
            :chat-streaming="streaming"
            :interaction-locked="interactionLocked"
            class="message-list__item"
            @open-file="(path) => emit('open-file', path)"
            @restored="(path) => emit('restored', path)"
            @confirm-approve="emit('confirm-approve')"
            @confirm-approve-remaining="emit('confirm-approve-remaining')"
            @confirm-deny="emit('confirm-deny')"
            @plan-approve="emit('plan-approve')"
            @plan-reject="emit('plan-reject')"
            @personas-another="(card) => emit('personas-another', card)"
            @personas-to-discussion="(card) => emit('personas-to-discussion', card)"
            @regenerate="(id) => emit('regenerate', id)"
            @error-reconnect="(cta) => emit('error-reconnect', cta)"
          />
        </div>
        <div
          v-if="spacerHeight > 0"
          class="message-list__reply-spacer"
          :style="{ height: spacerHeight + 'px' }"
          aria-hidden="true"
        />
      </div>

      <div v-else class="message-list__empty">
        <Lucide name="messages-square" size="lg" color="neutral-medium" />
        <p>{{ t('chat.emptyConversation') }}</p>
      </div>
    </q-scroll-area>
    <p
      class="message-list__sr-status"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {{ streamStatusMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import Message from '@components/chat/Message.vue';
import type { ChatMessage } from '#types';
import type { QScrollArea } from 'quasar';

type ScrollToOptions = {
  align?: 'start' | 'center' | 'end' | 'nearest';
  smooth?: boolean;
  offset?: number;
};

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[];
    streaming?: boolean;
    /** Réserve dynamique sous le tour user (turn-anchor). 0 hors mode anchor. */
    spacerHeight?: number;
    projectPath?: string | null;
    sessionId?: string | null;
    workspaceDataDir?: string | null;
    confirming?: boolean;
    approvingPlan?: boolean;
    attachmentStatuses?: Record<string, import('@composables/useChatStream').AttachmentStatusEntry>;
    settingsLocked?: boolean;
  }>(),
  { spacerHeight: 0 },
);

const interactionLocked = computed(
  () =>
    !!props.confirming ||
    !!props.approvingPlan ||
    props.messages.some(
      (m) =>
        m.pendingConfirmation ||
        m.pendingPlan?.status === 'pending',
    ),
);

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

const { t } = useI18n();

const ariaLiveMode = computed<'off' | 'polite'>(() =>
  props.streaming ? 'off' : 'polite',
);

const streamStatusMessage = ref('');
let streamStatusTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.streaming,
  (streaming, wasStreaming) => {
    if (wasStreaming && !streaming) {
      streamStatusMessage.value = t('chat.streamCompleteAria');
      if (streamStatusTimer) clearTimeout(streamStatusTimer);
      streamStatusTimer = setTimeout(() => {
        streamStatusMessage.value = '';
        streamStatusTimer = null;
      }, 1500);
    }
  },
);

onUnmounted(() => {
  if (streamStatusTimer) {
    clearTimeout(streamStatusTimer);
    streamStatusTimer = null;
  }
});

const scrollAreaRef = ref<QScrollArea | null>(null);
const contentRef = ref<HTMLElement | null>(null);

function getMessageElement(index: number): HTMLElement | null {
  const content = contentRef.value;
  if (!content) return null;
  return content.querySelector<HTMLElement>(`[data-index="${index}"]`);
}

function getScrollTarget(): HTMLElement | null {
  const area = scrollAreaRef.value;
  if (!area) return null;
  if (typeof area.getScrollTarget === 'function') {
    const target = area.getScrollTarget();
    return target instanceof HTMLElement ? target : null;
  }
  const root = area.$el as HTMLElement | null;
  if (!root) return null;
  return root.querySelector<HTMLElement>('.q-scrollarea__container') ?? null;
}

function scrollToItem(index: number, options?: ScrollToOptions): void {
  const target = getScrollTarget();
  if (!target) return;
  const itemOffset = getItemOffset(index);
  const itemSize = getItemSize(index);
  const align = options?.align ?? 'start';
  const extra = options?.offset ?? 0;
  let top = itemOffset + extra;
  if (align === 'end') {
    top = itemOffset + itemSize - target.clientHeight + extra;
  } else if (align === 'center') {
    top = itemOffset + itemSize / 2 - target.clientHeight / 2 + extra;
  }
  target.scrollTo({
    top: Math.max(0, top),
    behavior: options?.smooth ? 'smooth' : 'auto',
  });
}

function scrollToPosition(position: number, options?: ScrollToOptions): void {
  const target = getScrollTarget();
  if (!target) return;
  target.scrollTo({
    top: Math.max(0, position),
    behavior: options?.smooth ? 'smooth' : 'auto',
  });
}

function getItemOffset(index: number): number {
  return getMessageElement(index)?.offsetTop ?? 0;
}

function getItemSize(itemOrIndex: number | ChatMessage): number {
  let index: number;
  if (typeof itemOrIndex === 'number') {
    index = itemOrIndex;
  } else {
    index = props.messages.findIndex((m) => m.id === itemOrIndex.id);
    if (index < 0) return 0;
  }
  return getMessageElement(index)?.offsetHeight ?? 0;
}

function scrollToBottom(smooth = false): void {
  const target = getScrollTarget();
  if (!target) return;
  if (smooth && 'scrollTo' in target) {
    target.scrollTo({ top: target.scrollHeight, behavior: 'smooth' });
  } else {
    target.scrollTop = target.scrollHeight;
  }
}

/** Legacy no-op : pré-virtualisation, les tests appelaient getScroller sur le DynamicScroller. */
function getScroller(): null {
  return null;
}

defineExpose({
  scrollToBottom: (smooth = false) => scrollToBottom(smooth),
  getScrollTarget,
  getScroller,
  scrollToItem,
  scrollToPosition,
  getItemOffset,
  getItemSize,
});
</script>

<style scoped lang="scss">
.message-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

.message-list__scroller {
  flex: 1;
  min-height: 0;
}

.message-list__content {
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
  padding: var(--wp-space-3) var(--wp-space-4) var(--wp-space-4);
}

.message-list__item-wrapper {
  width: 100%;
}

.message-list__item {
  width: 100%;
}

.message-list__reply-spacer {
  display: block;
  width: 100%;
  flex-shrink: 0;
  pointer-events: none;
  /* Hauteur inline (turn-anchor) ; pas de min-height pour pouvoir retomber à 0. */
}

.message-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  min-height: 240px;
  padding: 2rem 1.5rem;
  text-align: center;
  color: var(--wp-text-muted);

  p {
    margin: 0;
    max-width: 34rem;
    font-size: 1rem;
    line-height: 1.55;
  }
}

.message-list__sr-status {
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
