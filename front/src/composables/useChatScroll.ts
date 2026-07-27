import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue';
import { useScroll } from '@vueuse/core';
import type { ChatMessage } from '#types';
import {
  type ChatScrollMode,
  clampAnchorPeek,
  computeDynamicSpacer,
  messageHasAnchorableContent,
  messageHasThinking,
  scrollToItemOffsetForPeek,
  shouldPromoteAnchorToSticky,
  shouldSuspendAnchorForCollapsedThinking,
} from '@composables/chatScrollAnchor';
import {
  expansionEpoch,
  isThinkingPartExpanded,
} from '@composables/useToolCallExpansion';

type ScrollToOptions = {
  align?: 'start' | 'center' | 'end' | 'nearest';
  smooth?: boolean;
  offset?: number;
};

export type ChatMessageListExposed = {
  getScrollTarget: () => HTMLElement | null;
  scrollToItem: (index: number, options?: ScrollToOptions) => void;
  scrollToPosition: (position: number, options?: ScrollToOptions) => void;
  getItemOffset: (index: number) => number;
  getItemSize: (itemOrIndex: number | ChatMessage) => number;
  scrollToBottom: (smooth?: boolean) => void;
};

export function useChatScroll(options: {
  listRef: Ref<ChatMessageListExposed | null>;
  messages: ComputedRef<ChatMessage[]>;
  streaming: ComputedRef<boolean>;
  sessionId: ComputedRef<string | null | undefined>;
}) {
  const { listRef, messages, streaming, sessionId } = options;

  const scrollTarget = ref<HTMLElement | null>(null);
  const scrollMode = ref<ChatScrollMode>('sticky');
  const spacerHeight = ref(0);
  const anchorUserIndex = ref<number | null>(null);
  const isPinned = ref(true);
  const userDetached = ref(false);
  const scrollReady = ref(false);
  let scrollRaf: number | null = null;
  let anchorRaf: number | null = null;
  let scrollListenersTarget: HTMLElement | null = null;
  let lastTouchY: number | null = null;
  let programmaticScrollDepth = 0;
  let programmaticReleaseTimer: ReturnType<typeof setTimeout> | null = null;
  let lastAppliedAnchorTop: number | null = null;
  let suppressNextLengthAnchor = false;
  let previousMessageCount = messages.value.length;

  const { arrivedState } = useScroll(scrollTarget, { offset: { bottom: 80 } });

  const showScrollDown = computed(
    () =>
      userDetached.value ||
      scrollMode.value === 'detached' ||
      (!isPinned.value && messages.value.length > 0),
  );

  function beginProgrammaticScroll(): void {
    programmaticScrollDepth += 1;
  }

  function endProgrammaticScroll(): void {
    programmaticScrollDepth = Math.max(0, programmaticScrollDepth - 1);
  }

  function isProgrammaticScroll(): boolean {
    return programmaticScrollDepth > 0;
  }

  function cancelProgrammaticReleaseTimer(): void {
    if (programmaticReleaseTimer !== null) {
      clearTimeout(programmaticReleaseTimer);
      programmaticReleaseTimer = null;
    }
  }

  function releaseProgrammaticScrollAfter(ms: number): void {
    cancelProgrammaticReleaseTimer();
    programmaticReleaseTimer = setTimeout(() => {
      programmaticReleaseTimer = null;
      endProgrammaticScroll();
    }, ms);
  }

  function bindScrollTarget(): void {
    scrollTarget.value = listRef.value?.getScrollTarget() ?? null;
    if (scrollTarget.value) scrollReady.value = true;
    bindScrollListeners();
  }

  function cancelScheduledScroll(): void {
    if (scrollRaf !== null) {
      cancelAnimationFrame(scrollRaf);
      scrollRaf = null;
    }
  }

  function cancelAnchorTick(): void {
    if (anchorRaf !== null) {
      cancelAnimationFrame(anchorRaf);
      anchorRaf = null;
    }
  }

  function clearSpacer(): void {
    spacerHeight.value = 0;
  }

  function enterStickyMode(): void {
    scrollMode.value = 'sticky';
    clearSpacer();
    anchorUserIndex.value = null;
    lastAppliedAnchorTop = null;
    userDetached.value = false;
    isPinned.value = true;
  }

  function detachFromBottom(): void {
    cancelScheduledScroll();
    cancelAnchorTick();
    cancelProgrammaticReleaseTimer();
    programmaticScrollDepth = 0;
    userDetached.value = true;
    isPinned.value = false;
    scrollMode.value = 'detached';
  }

  function onUserWheel(event: WheelEvent): void {
    if (event.deltaY < 0) detachFromBottom();
  }

  function onUserTouchStart(event: TouchEvent): void {
    lastTouchY = event.touches[0]?.clientY ?? null;
  }

  function onUserTouchMove(event: TouchEvent): void {
    const y = event.touches[0]?.clientY;
    if (y == null || lastTouchY == null) return;
    if (y > lastTouchY) detachFromBottom();
    lastTouchY = y;
  }

  function bindScrollListeners(): void {
    const target = scrollTarget.value;
    if (!target || target === scrollListenersTarget) return;
    unbindScrollListeners();
    scrollListenersTarget = target;
    target.addEventListener('wheel', onUserWheel, { passive: true });
    target.addEventListener('touchstart', onUserTouchStart, { passive: true });
    target.addEventListener('touchmove', onUserTouchMove, { passive: true });
  }

  function unbindScrollListeners(): void {
    if (!scrollListenersTarget) return;
    scrollListenersTarget.removeEventListener('wheel', onUserWheel);
    scrollListenersTarget.removeEventListener('touchstart', onUserTouchStart);
    scrollListenersTarget.removeEventListener('touchmove', onUserTouchMove);
    scrollListenersTarget = null;
    lastTouchY = null;
  }

  function scrollToBottom(smooth = false): void {
    const target = listRef.value?.getScrollTarget();
    if (!target) return;
    target.scrollTo({
      top: target.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
  }

  function scrollConfirmationActionsIntoView(): void {
    const target = listRef.value?.getScrollTarget();
    if (!target || typeof target.querySelector !== 'function') return;
    const card = target.querySelector<HTMLElement>(
      '[data-testid="confirmation-card"]',
    );
    if (!card) return;
    const actions =
      card.querySelector<HTMLElement>('.confirmation-card__actions') ?? card;
    const targetRect = target.getBoundingClientRect();
    const actionsRect = actions.getBoundingClientRect();
    const margin = 12;
    if (actionsRect.bottom <= targetRect.bottom - margin) return;

    const delta = actionsRect.bottom - targetRect.bottom + margin;
    beginProgrammaticScroll();
    target.scrollTop += delta;
    releaseProgrammaticScrollAfter(80);
  }

  async function ensureConfirmationVisible(): Promise<void> {
    if (userDetached.value) return;
    if (scrollMode.value === 'anchor') {
      enterStickyMode();
    } else if (scrollMode.value !== 'sticky') {
      enterStickyMode();
    } else {
      isPinned.value = true;
    }
    await scrollToBottomStable();
    await nextTick();
    scrollConfirmationActionsIntoView();
    requestAnimationFrame(() => {
      if (userDetached.value) return;
      scrollConfirmationActionsIntoView();
    });
  }

  function applyAnchorScrollTop(force = false): void {
    const list = listRef.value;
    const userIndex = anchorUserIndex.value;
    if (!list || userIndex == null) return;

    const userSize = list.getItemSize(userIndex);
    if (userSize <= 0) {
      beginProgrammaticScroll();
      list.scrollToItem(userIndex, { align: 'start' });
      releaseProgrammaticScrollAfter(48);
      scheduleAnchorTick();
      return;
    }

    const peek = clampAnchorPeek(userSize);
    const itemOffset = scrollToItemOffsetForPeek(userSize);
    const dedupeKey = userIndex * 1_000_000 + Math.round(userSize) * 1_000 + peek;
    if (!force && lastAppliedAnchorTop === dedupeKey) return;
    lastAppliedAnchorTop = dedupeKey;

    beginProgrammaticScroll();
    list.scrollToItem(userIndex, { align: 'start', offset: itemOffset });
    releaseProgrammaticScrollAfter(48);
  }

  function findLastUserMessageIndex(): number | null {
    for (let i = messages.value.length - 1; i >= 0; i -= 1) {
      if (messages.value[i]?.role === 'user') return i;
    }
    return null;
  }

  function measureResponseHeightBelowUser(userIndex: number): number {
    const list = listRef.value;
    if (!list) return 0;
    const viewportHeight = list.getScrollTarget()?.clientHeight ?? 0;
    let height = 0;
    for (let i = userIndex + 1; i < messages.value.length; i += 1) {
      height += Math.max(0, list.getItemSize(i));
      if (viewportHeight > 0 && height >= viewportHeight) break;
    }
    return height;
  }

  function isAssistantThinkingExpanded(message: ChatMessage): boolean {
    for (const part of message.parts ?? []) {
      if (part.type === 'thinking' && isThinkingPartExpanded(part.id)) {
        return true;
      }
    }
    if (message.thinking != null) {
      if (isThinkingPartExpanded(`${message.id}__thinking`)) return true;
    }
    if (isThinkingPartExpanded(`${message.id}__thinking-placeholder`)) {
      return true;
    }
    return false;
  }

  function shouldSuspendAnchorLayout(userIndex: number): boolean {
    const responseHeight = measureResponseHeightBelowUser(userIndex);
    for (let i = userIndex + 1; i < messages.value.length; i += 1) {
      const msg = messages.value[i];
      if (!msg || msg.role !== 'assistant') continue;
      if (
        shouldSuspendAnchorForCollapsedThinking({
          hasAnchorableContent: messageHasAnchorableContent(msg),
          hasThinking: messageHasThinking(msg),
          thinkingExpanded: isAssistantThinkingExpanded(msg),
        })
      ) {
        // Garde l'ancre une fois le header thinking mesuré (responseHeight > 0).
        return responseHeight <= 0;
      }
      // Seul le premier assistant sous le user compte pour suspendre l'ancre.
      break;
    }
    return false;
  }

  function updateAnchorLayout(): void {
    if (scrollMode.value !== 'anchor' || userDetached.value) return;

    const list = listRef.value;
    const target = list?.getScrollTarget();
    const userIndex = anchorUserIndex.value;
    if (!list || !target || userIndex == null) return;

    if (shouldSuspendAnchorLayout(userIndex)) {
      enterStickyMode();
      scheduleScrollToBottom();
      return;
    }

    const userSize = list.getItemSize(userIndex);
    if (userSize <= 0) {
      beginProgrammaticScroll();
      list.scrollToItem(userIndex, { align: 'start' });
      releaseProgrammaticScrollAfter(48);
      scheduleAnchorTick();
      return;
    }

    const peek = clampAnchorPeek(userSize);
    const responseHeight = measureResponseHeightBelowUser(userIndex);
    const nextSpacer = computeDynamicSpacer({
      viewportHeight: target.clientHeight,
      anchorPeek: peek,
      responseHeight,
    });

    if (nextSpacer !== spacerHeight.value) {
      spacerHeight.value = nextSpacer;
      void nextTick(() => {
        if (scrollMode.value !== 'anchor' || userDetached.value) return;
        if (shouldPromoteAnchorToSticky(spacerHeight.value) && streaming.value) {
          enterStickyMode();
          scheduleScrollToBottom();
          return;
        }
        applyAnchorScrollTop(false);
      });
      return;
    }

    if (shouldPromoteAnchorToSticky(nextSpacer) && streaming.value) {
      enterStickyMode();
      scheduleScrollToBottom();
      return;
    }

    applyAnchorScrollTop(false);
  }

  function scheduleAnchorTick(): void {
    if (anchorRaf !== null) return;
    anchorRaf = requestAnimationFrame(() => {
      anchorRaf = null;
      updateAnchorLayout();
    });
  }

  async function enterAnchorMode(): Promise<void> {
    const userIndex = findLastUserMessageIndex();
    if (userIndex == null) {
      enterStickyMode();
      void scrollToBottomStable();
      return;
    }

    scrollMode.value = 'anchor';
    anchorUserIndex.value = userIndex;
    lastAppliedAnchorTop = null;
    userDetached.value = false;
    isPinned.value = true;
    cancelScheduledScroll();
    bindScrollTarget();
    await nextTick();

    const list = listRef.value;
    if (list) {
      beginProgrammaticScroll();
      list.scrollToItem(userIndex, { align: 'start' });
      releaseProgrammaticScrollAfter(48);
    }

    scheduleAnchorTick();
    requestAnimationFrame(() => {
      if (scrollMode.value === 'anchor') scheduleAnchorTick();
    });
  }

  const SCROLL_STABLE_MAX_ATTEMPTS = 4;
  const SCROLL_STABLE_TIMEOUT_MS = 250;

  async function scrollToBottomStable(smooth = false): Promise<void> {
    await nextTick();
    beginProgrammaticScroll();
    const deadline = performance.now() + SCROLL_STABLE_TIMEOUT_MS;
    let lastHeight = -1;
    let attempts = 0;

    try {
      await new Promise<void>((resolve) => {
        const run = (): void => {
          const target = listRef.value?.getScrollTarget();
          if (!target) {
            if (
              attempts < SCROLL_STABLE_MAX_ATTEMPTS &&
              performance.now() < deadline
            ) {
              attempts += 1;
              requestAnimationFrame(run);
              return;
            }
            resolve();
            return;
          }

          const height = target.scrollHeight;
          if (isPinned.value && scrollMode.value === 'sticky') {
            scrollToBottom(smooth && attempts === 0);
          }

          attempts += 1;
          const stable = height === lastHeight && lastHeight >= 0;
          lastHeight = height;

          if (
            !isPinned.value ||
            scrollMode.value !== 'sticky' ||
            stable ||
            attempts >= SCROLL_STABLE_MAX_ATTEMPTS ||
            performance.now() >= deadline
          ) {
            resolve();
            return;
          }

          requestAnimationFrame(run);
        };

        requestAnimationFrame(run);
      });
    } finally {
      if (smooth) {
        await new Promise((r) => {
          cancelProgrammaticReleaseTimer();
          programmaticReleaseTimer = setTimeout(() => {
            programmaticReleaseTimer = null;
            r(undefined);
          }, 350);
        });
      }
      endProgrammaticScroll();
    }
  }

  function scheduleScrollToBottom(): void {
    if (scrollMode.value !== 'sticky' || !isPinned.value) return;
    if (scrollRaf !== null) return;
    scrollRaf = requestAnimationFrame(() => {
      scrollRaf = null;
      if (!(isPinned.value && scrollMode.value === 'sticky')) return;
      beginProgrammaticScroll();
      scrollToBottom();
      releaseProgrammaticScrollAfter(32);
    });
  }

  function handleScrollDownClick(): void {
    enterStickyMode();
    void scrollToBottomStable(true);
  }

  function getScrollState() {
    return {
      mode: scrollMode.value,
      spacerHeight: spacerHeight.value,
      isPinned: isPinned.value,
      userDetached: userDetached.value,
      anchorUserIndex: anchorUserIndex.value,
    };
  }

  watch(
    () => arrivedState.bottom,
    (bottom) => {
      if (!scrollReady.value || isProgrammaticScroll()) return;
      if (scrollMode.value === 'anchor') return;
      if (userDetached.value) {
        if (bottom) {
          userDetached.value = false;
          isPinned.value = true;
          scrollMode.value = 'sticky';
        }
        return;
      }
      isPinned.value = bottom;
      if (!bottom && scrollMode.value === 'sticky') {
        userDetached.value = true;
        scrollMode.value = 'detached';
      }
    },
  );

  watch(
    () => messages.value.length,
    (length) => {
      bindScrollTarget();
      const prevCount = previousMessageCount;
      const grew = length > prevCount;
      previousMessageCount = length;
      if (suppressNextLengthAnchor) {
        suppressNextLengthAnchor = false;
        return;
      }
      if (grew) {
        let newUser = false;
        for (let i = prevCount; i < length; i += 1) {
          if (messages.value[i]?.role === 'user') {
            newUser = true;
            break;
          }
        }
        if (newUser) {
          void enterAnchorMode();
          return;
        }
      }
      if (scrollMode.value === 'sticky' && isPinned.value && !userDetached.value) {
        void scrollToBottomStable();
      }
    },
  );

  watch(
    () => sessionId.value,
    () => {
      suppressNextLengthAnchor = true;
      previousMessageCount = messages.value.length;
      enterStickyMode();
      bindScrollTarget();
      void scrollToBottomStable();
    },
  );

  watch(
    () => streaming.value,
    (isStreaming, wasStreaming) => {
      if (wasStreaming && !isStreaming) {
        cancelAnchorTick();
        const wasAnchor = scrollMode.value === 'anchor';
        if (wasAnchor && !userDetached.value) {
          clearSpacer();
          scrollMode.value = 'sticky';
          anchorUserIndex.value = null;
          lastAppliedAnchorTop = null;
        } else if (!userDetached.value) {
          clearSpacer();
          if (scrollMode.value === 'anchor') {
            enterStickyMode();
          }
          if (isPinned.value && scrollMode.value === 'sticky') {
            void scrollToBottomStable();
          }
        } else {
          clearSpacer();
          if (scrollMode.value === 'anchor') {
            scrollMode.value = 'detached';
            anchorUserIndex.value = null;
            lastAppliedAnchorTop = null;
          }
        }
        return;
      }
      if (isStreaming && !wasStreaming) {
        if (userDetached.value) {
          userDetached.value = false;
          isPinned.value = true;
        }
        const last = messages.value[messages.value.length - 1];
        if (last?.pendingConfirmation || last?.preparingConfirmation) {
          void ensureConfirmationVisible();
          return;
        }
        if (last?.role === 'assistant' && scrollMode.value !== 'anchor') {
          void enterAnchorMode();
          return;
        }
        if (scrollMode.value === 'anchor') {
          scheduleAnchorTick();
        } else if (isPinned.value) {
          enterStickyMode();
          void scrollToBottomStable();
        }
      }
    },
  );

  watch(expansionEpoch, () => {
    if (scrollMode.value === 'anchor' && !userDetached.value) {
      scheduleAnchorTick();
      return;
    }
    if (scrollMode.value === 'sticky' && isPinned.value) {
      scheduleScrollToBottom();
    }
  });

  watch(
    () => {
      const last = messages.value[messages.value.length - 1];
      if (!last) return null;
      return [
        last.content,
        last.parts?.length,
        last.toolCalls?.length,
        last._contentRev,
        last.pendingConfirmation?.confirmationId,
        last.preparingConfirmation?.toolCallId,
        last.pendingPlan?.planId,
      ] as const;
    },
    (curr, prev) => {
      const confirmationAppeared =
        curr != null &&
        prev != null &&
        (curr[4] !== prev[4] || curr[5] !== prev[5]) &&
        (curr[4] != null || curr[5] != null);
      if (confirmationAppeared && !userDetached.value) {
        void ensureConfirmationVisible();
        return;
      }
      if (scrollMode.value === 'anchor' && !userDetached.value) {
        scheduleAnchorTick();
        return;
      }
      if (scrollMode.value === 'sticky' && isPinned.value) {
        scheduleScrollToBottom();
      }
    },
  );

  onMounted(() => {
    previousMessageCount = messages.value.length;
    bindScrollTarget();
    void scrollToBottomStable();
  });

  onUnmounted(() => {
    cancelScheduledScroll();
    cancelAnchorTick();
    cancelProgrammaticReleaseTimer();
    programmaticScrollDepth = 0;
    unbindScrollListeners();
    scrollTarget.value = null;
  });

  return {
    scrollMode,
    spacerHeight,
    showScrollDown,
    enterAnchorMode,
    enterStickyMode,
    detachFromBottom,
    handleScrollDownClick,
    ensureConfirmationVisible,
    scheduleScrollToBottom,
    bindScrollTarget,
    getScrollState,
    detachFromBottomForTest: detachFromBottom,
    beginProgrammaticScrollForTest: beginProgrammaticScroll,
    handleScrollDownClickForTest: handleScrollDownClick,
  };
}
