<template>
  <div class="message-list">
    <q-scroll-area
      ref="scrollAreaRef"
      class="message-list__scroller"
      role="log"
      :aria-live="ariaLiveMode"
      aria-relevant="additions"
    >
      <DynamicScroller
        v-if="messages.length"
        ref="dynamicScrollerRef"
        class="message-list__virtual"
        :items="messages"
        :min-item-size="72"
        key-field="id"
      >
        <template #default="{ item, active, index }">
          <DynamicScrollerItem
            :item="item"
            :active="active"
            :data-index="index"
            :size-dependencies="[
              item.streaming ? (item._contentRev ?? 0) : item.content,
              item.toolCalls?.length,
              item.parts?.length,
              item.streaming,
              item.error?.code,
              item.pendingConfirmation?.confirmationId,
              item.preparingConfirmation?.toolCallId,
              item.pendingPlan?.planId,
              expansionEpoch,
            ]"
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
          </DynamicScrollerItem>
        </template>
        <template #after>
          <div
            v-if="spacerHeight > 0"
            class="message-list__reply-spacer"
            :style="{ height: spacerHeight + 'px' }"
            aria-hidden="true"
          />
        </template>
      </DynamicScroller>

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
import {
  DynamicScroller,
  DynamicScrollerItem,
} from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import Message from '@components/chat/Message.vue';
import { expansionEpoch } from '@composables/useToolCallExpansion';
import type { ChatMessage } from '#types';
import type { QScrollArea } from 'quasar';

type ScrollToOptions = {
  align?: 'start' | 'center' | 'end' | 'nearest';
  smooth?: boolean;
  offset?: number;
};

type DynamicScrollerExposed = {
  scrollToItem: (index: number, options?: ScrollToOptions) => void;
  scrollToPosition: (position: number, options?: ScrollToOptions) => void;
  getItemOffset: (index: number) => number;
  getItemSize: (itemOrIndex: number | ChatMessage) => number;
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
const dynamicScrollerRef = ref<DynamicScrollerExposed | null>(null);

function getScroller(): DynamicScrollerExposed | null {
  return dynamicScrollerRef.value;
}

function scrollToItem(index: number, options?: ScrollToOptions): void {
  const target = getScrollTarget();
  const scroller = dynamicScrollerRef.value;
  if (!target || !scroller) {
    dynamicScrollerRef.value?.scrollToItem(index, options);
    return;
  }
  // Scroller = q-scroll-area ; DynamicScroller n'a pas de viewport propre.
  // On positionne le container Quasar via les offsets mesurés.
  const itemOffset = scroller.getItemOffset(index);
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
  if (!target) {
    dynamicScrollerRef.value?.scrollToPosition(position, options);
    return;
  }
  target.scrollTo({
    top: Math.max(0, position),
    behavior: options?.smooth ? 'smooth' : 'auto',
  });
}

function getItemOffset(index: number): number {
  return dynamicScrollerRef.value?.getItemOffset(index) ?? 0;
}

function getItemSize(itemOrIndex: number | ChatMessage): number {
  const scroller = dynamicScrollerRef.value;
  if (!scroller) return 0;
  // DynamicScroller indexe les tailles par `id` (key-field), pas par index.
  if (typeof itemOrIndex === 'number') {
    const item = props.messages[itemOrIndex];
    if (!item) return 0;
    return scroller.getItemSize(item, itemOrIndex);
  }
  return scroller.getItemSize(itemOrIndex);
}

// Pendant le streaming, `_contentRev` remplace `item.content` dans size-dependencies
// pour limiter les re-mesures du virtual scroller à chaque flush de tokens.

/**
 * Cible de scroll = container Quasar (vrai viewport).
 * Le `.vue-recycle-scroller` sans height:100% s'étend avec le contenu et
 * n'est pas le scrollport : scroller dessus laissait scrollTop coincé à 0.
 */
function getScrollTarget(): HTMLElement | null {
  const root = scrollAreaRef.value?.$el as HTMLElement | null;
  if (!root) return null;
  return root.querySelector<HTMLElement>('.q-scrollarea__container') ?? null;
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

defineExpose({
  scrollToBottom: (smooth = false) => scrollToBottom(smooth),
  getScrollTarget,
  scrollToItem,
  scrollToPosition,
  getItemOffset,
  getItemSize,
  getScroller,
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

.message-list__virtual {
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
  padding: var(--wp-space-3) var(--wp-space-4) var(--wp-space-4);
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
