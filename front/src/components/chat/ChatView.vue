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
        @confirm-deny="emit('confirm-deny')"
        @plan-approve="emit('plan-approve')"
        @plan-reject="emit('plan-reject')"
        @personas-another="(card) => emit('personas-another', card)"
        @personas-to-discussion="(card) => emit('personas-to-discussion', card)"
        @edit="(id, text) => emit('edit', id, text)"
        @regenerate="(id) => emit('regenerate', id)"
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

    <div
      class="chat-view__composer"
      :class="{ 'chat-view__composer--expanded': isExpanded }"
    >
      <div
        v-if="showEngineBanner"
        class="chat-view__engine-banner"
        role="status"
      >
        <p class="chat-view__engine-banner-text">{{ engineBannerMessage }}</p>
        <button
          type="button"
          class="chat-view__engine-banner-action"
          @click="onEngineBannerAction"
        >
          {{ engineBannerActionLabel }}
        </button>
      </div>
      <EnrollCloudModal v-model="enrollModalOpen" @enrolled="onCloudEnrolled" />
      <CloudLoginModal
        v-model="cloudLoginModalOpen"
        @enrolled="onCloudLoggedIn"
        @open-invitation="onOpenCloudInvitation"
      />
      <ChatComposerAttachments
        v-if="hasAttachments"
        :attachments="attachments"
        @remove="removeAttachment"
      />
      <label
        v-if="canIndexAttachments"
        class="chat-view__memory-index"
      >
        <input v-model="indexAttachmentsInMemory" type="checkbox" />
        <span>{{ t('chat.attachment.indexInMemory') }}</span>
      </label>
      <form class="chat-view__composer-form" @submit.prevent="handleSubmit">
        <input
          ref="fileInputRef"
          type="file"
          class="chat-view__file-input"
          multiple
          :accept="ATTACHMENT_ACCEPT"
          @change="onFileInputChange"
        />
        <div class="chat-view__composer-input-row">
        <button
          type="button"
          class="chat-view__attach"
          :class="{ 'chat-view__attach--reasoning': showReasoningBadge }"
          :aria-label="attachAriaLabel"
          :title="attachTitle"
          aria-haspopup="menu"
        >
          <Lucide name="plus" size="18" color="wp-text" />
          <span
            v-if="showReasoningBadge"
            class="chat-view__attach-badge"
            aria-hidden="true"
          >
            <Lucide name="brain" size="10" color="accent" />
          </span>
          <q-menu
            ref="addMenuRef"
            anchor="bottom left"
            self="top left"
            :offset="[0, 8]"
            :close-on-click="false"
            class="chat-view__add-menu"
            transition-show="jump-down"
            transition-hide="jump-up"
          >
            <div class="chat-view__add-menu-scroll">
              <div class="chat-view__add-head">{{ t('chat.attachFile') }}</div>
              <q-list dense>
                <q-item
                  clickable
                  class="chat-view__add-item"
                  @click="onAttachClick"
                >
                  <q-item-section avatar class="chat-view__add-icon">
                    <Lucide name="paperclip" size="16" color="wp-text" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="chat-view__add-item-label">
                      {{ t('chat.attachFile') }}
                    </q-item-label>
                    <q-item-label caption class="chat-view__add-item-hint">
                      {{ t('chat.attachFileHint') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>

              <template v-if="personasEnabled">
                <q-separator class="chat-view__add-sep" />
                <div class="chat-view__add-head">{{ t('chat.addMenuPersonas') }}</div>
                <q-list dense>
                  <q-item
                    clickable
                    class="chat-view__add-item"
                    @click="onPersonasOpen"
                  >
                    <q-item-section avatar class="chat-view__add-icon">
                      <Lucide name="message-circle-question" size="16" color="wp-gold" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="chat-view__add-item-label">
                        {{ t('regards.ask') }}
                      </q-item-label>
                      <q-item-label caption class="chat-view__add-item-hint">
                        {{ t('regards.askHint') }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    class="chat-view__add-item"
                    @click="onPersonasMeeting"
                  >
                    <q-item-section avatar class="chat-view__add-icon">
                      <Lucide name="presentation" size="16" color="wp-gold" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="chat-view__add-item-label">
                        {{ t('regards.cross') }}
                      </q-item-label>
                      <q-item-label caption class="chat-view__add-item-hint">
                        {{ t('regards.crossHint') }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    class="chat-view__add-item"
                    @click="onPersonasDiscuss"
                  >
                    <q-item-section avatar class="chat-view__add-icon">
                      <Lucide name="messages-square" size="16" color="wp-gold" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="chat-view__add-item-label">
                        {{ t('regards.discuss') }}
                      </q-item-label>
                      <q-item-label caption class="chat-view__add-item-hint">
                        {{ t('regards.discussHint') }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </template>

              <template v-if="showModelControl">
                <q-separator class="chat-view__add-sep" />
                <ChatModelMenuContent
                  :model-value="reasoningEffort ?? 'none'"
                  :provider="reasoningProvider"
                  :model="reasoningModel"
                  :provider-set="effectiveActiveSet"
                  @update:model-value="
                    (value) => emit('update:reasoningEffort', value)
                  "
                  @update:model="(value) => emit('update:reasoningModel', value)"
                />
              </template>
            </div>
          </q-menu>
        </button>

        <div class="chat-view__composer-field">
          <q-input
            ref="composerInputRef"
            v-model="draft"
            type="textarea"
            autogrow
            borderless
            class="chat-view__input"
            :placeholder="t('chat.messagePlaceholder')"
            :maxlength="COMPOSER_MAX_LENGTH"
            @keydown.enter.ctrl.prevent="handleSubmit"
            @keydown.enter.meta.prevent="handleSubmit"
            @paste="onPaste"
          />
        </div>
        </div>

        <div class="chat-view__composer-actions">
          <button
            v-if="streaming"
            type="button"
            class="chat-view__stop"
            :aria-label="t('chat.stop')"
            :title="t('chat.stop')"
            @click="emit('abort')"
          >
            <Lucide name="square" size="16" color="wp-canard" />
          </button>
          <button
            v-else
            type="submit"
            class="chat-view__send"
            :disabled="!canSend"
            :aria-label="t('chat.send')"
          >
            <Lucide name="arrow-up" size="18" color="text-invert" />
          </button>
        </div>
      </form>

      <p v-if="hasDraft" class="chat-view__composer-hint">
        {{ t('chat.composerHint') }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { useScroll } from '@vueuse/core';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import ChatModelMenuContent from '@components/chat/ChatModelMenuContent.vue';
import ChatComposerAttachments from '@components/chat/ChatComposerAttachments.vue';
import MessageList from '@components/chat/MessageList.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useCloud } from '@composables/useCloud';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import { getSetActivationReadiness } from '@utils/providerSetValidation';
import type { LlmProviderName } from '@composables/useDesktop.types';
import {
  ATTACHMENT_ACCEPT,
  MAX_ATTACHMENTS,
  useChatAttachments,
} from '@composables/useChatAttachments';
import type { ChatAttachment, ChatMessage, ReasoningEffort } from '#types';
import { addMemoryItem } from '@services/aiSidecar';
import type { QInput, QMenu } from 'quasar';
import { REASONING_EFFORT_OPTIONS, supportsReasoning } from '@utils/reasoningSupport';
import { hasModelChoice } from '@utils/modelCatalog';
import { hasSetModelChoice, supportsReasoningForSet } from '@utils/providerSetModels';
import {
  type ChatScrollMode,
  clampAnchorPeek,
  computeDynamicSpacer,
  scrollToItemOffsetForPeek,
  shouldPromoteAnchorToSticky,
} from '@composables/chatScrollAnchor';
import { expansionEpoch } from '@composables/useToolCallExpansion';

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
}>();

const emit = defineEmits<{
  send: [text: string, attachments: ChatAttachment[]];
  abort: [];
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
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
  edit: [messageId: string, newText: string];
  regenerate: [messageId: string];
}>();

const COMPOSER_MAX_LENGTH = 32_000;
const { t } = useI18n();
const router = useRouter();

const layoutMode = computed(() => props.layout ?? 'chat');

const emptyHeroTitle = computed(
  () => props.emptyHero?.trim() || t('home.heroQuestion'),
);

const {
  attachments,
  hasAttachments,
  isReading,
  isDragOver,
  addFiles,
  removeAttachment,
  clear: clearAttachments,
  setDragOver,
} = useChatAttachments();

const fileInputRef = ref<HTMLInputElement | null>(null);
const addMenuRef = ref<QMenu | null>(null);
const dragCounter = ref(0);
const indexAttachmentsInMemory = ref(false);

const canIndexAttachments = computed(
  () => Boolean(props.workspaceDataDir) && hasAttachments.value,
);

const { activeSet, effectiveActiveSet, effectiveActiveSetId } = useAppSettings();
const { providerReadiness, init: initCloud, refreshQuota } = useCloud();

const enrollModalOpen = ref(false);
const cloudLoginModalOpen = ref(false);

const showEngineBanner = computed(
  () => !props.settingsLocked && effectiveActiveSetId.value == null,
);

const activeSetReadinessIssue = computed(() => {
  if (!activeSet.value || effectiveActiveSetId.value != null) return null;
  const check = getSetActivationReadiness(activeSet.value, {
    cloud: providerReadiness.value,
  });
  return check.ok ? null : check.reason;
});

const engineBannerNeedsEnroll = computed(
  () => activeSetReadinessIssue.value === 'cloud_not_enrolled',
);

const engineBannerMessage = computed(() => {
  const issue = activeSetReadinessIssue.value;
  if (issue) {
    return chatErrorMessageForReadiness(issue);
  }
  return t('chat.engineBanner.chooseEngine');
});

const engineBannerActionLabel = computed(() =>
  engineBannerNeedsEnroll.value
    ? t('settings.engine.linkDevice')
    : t('chat.engineBanner.openSettings'),
);

function onEngineBannerAction(): void {
  if (engineBannerNeedsEnroll.value) {
    cloudLoginModalOpen.value = true;
    return;
  }
  void router.push({ name: 'settings_models' });
}

async function onCloudEnrolled(): Promise<void> {
  await refreshQuota();
  enrollModalOpen.value = false;
}

async function onCloudLoggedIn(): Promise<void> {
  await refreshQuota();
  cloudLoginModalOpen.value = false;
}

function onOpenCloudInvitation(): void {
  cloudLoginModalOpen.value = false;
  enrollModalOpen.value = true;
}

const showModelControl = computed(() => {
  const provider = props.reasoningProvider;
  const model = props.reasoningModel;
  if (!provider || !model) return false;
  if (effectiveActiveSet.value) {
    return hasSetModelChoice(effectiveActiveSet.value) || supportsReasoningForSet(effectiveActiveSet.value, model);
  }
  return hasModelChoice(provider) || supportsReasoning(provider, model);
});

const showReasoningBadge = computed(
  () =>
    showModelControl.value &&
    props.reasoningEffort != null &&
    props.reasoningEffort !== 'none',
);

const reasoningBadgeTitle = computed(() => {
  const match = REASONING_EFFORT_OPTIONS.find(
    (opt) => opt.value === props.reasoningEffort,
  );
  return match
    ? `${t('chat.modelControlReasoning')}: ${match.label}`
    : t('chat.modelControlReasoning');
});

const attachTitle = computed(() =>
  showReasoningBadge.value
    ? `${t('chat.addMenuTitle')} · ${reasoningBadgeTitle.value}`
    : t('chat.addMenuTitle'),
);

const attachAriaLabel = computed(() =>
  showReasoningBadge.value
    ? `${t('chat.attachFileAria', { current: attachments.length, max: MAX_ATTACHMENTS })} · ${reasoningBadgeTitle.value}`
    : t('chat.attachFileAria', { current: attachments.length, max: MAX_ATTACHMENTS }),
);

function closeAddMenu(): void {
  addMenuRef.value?.hide?.();
}

function onAttachClick(): void {
  openFilePicker();
  closeAddMenu();
}

function onPersonasOpen(): void {
  emit('personas-open');
  closeAddMenu();
}

function onPersonasMeeting(): void {
  emit('personas-meeting');
  closeAddMenu();
}

function onPersonasDiscuss(): void {
  emit('personas-discuss');
  closeAddMenu();
}

const draft = ref('');
const composerInputRef = ref<QInput | null>(null);
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
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
/** Compteur de scrolls programmatiques en cours (ignore detach / arrivedState). */
let programmaticScrollDepth = 0;
let programmaticReleaseTimer: ReturnType<typeof setTimeout> | null = null;
let lastAppliedAnchorTop: number | null = null;
let suppressNextLengthAnchor = false;
let previousMessageCount = props.messages.length;

const { arrivedState } = useScroll(scrollTarget, { offset: { bottom: 80 } });

const showScrollDown = computed(
  () =>
    userDetached.value ||
    scrollMode.value === 'detached' ||
    (!isPinned.value && props.messages.length > 0),
);

const canSend = computed(
  () =>
    draft.value.trim().length > 0 &&
    draft.value.length <= COMPOSER_MAX_LENGTH &&
    !props.streaming &&
    !isReading.value,
);

const hasDraft = computed(() => draft.value.trim().length > 0);
const isExpanded = computed(() => hasDraft.value || hasAttachments.value);

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

defineExpose({
  setDraft,
  /** Hooks de test / debug scroll (pin, promote, FAB). */
  getScrollState: () => ({
    mode: scrollMode.value,
    spacerHeight: spacerHeight.value,
    isPinned: isPinned.value,
    userDetached: userDetached.value,
    anchorUserIndex: anchorUserIndex.value,
  }),
  detachFromBottomForTest: () => {
    cancelProgrammaticReleaseTimer();
    programmaticScrollDepth = 0;
    detachFromBottom();
  },
  handleScrollDownClickForTest: () => handleScrollDownClick(),
});

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

/** Relâche le lock après un délai ; annule un timer précédent. */
function releaseProgrammaticScrollAfter(ms: number): void {
  cancelProgrammaticReleaseTimer();
  programmaticReleaseTimer = setTimeout(() => {
    programmaticReleaseTimer = null;
    endProgrammaticScroll();
  }, ms);
}

function bindScrollTarget(): void {
  scrollTarget.value = messageListRef.value?.getScrollTarget() ?? null;
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
  if (isProgrammaticScroll()) return;
  userDetached.value = true;
  isPinned.value = false;
  scrollMode.value = 'detached';
  cancelScheduledScroll();
  cancelAnchorTick();
  cancelProgrammaticReleaseTimer();
  programmaticScrollDepth = 0;
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
  const target = messageListRef.value?.getScrollTarget();
  if (!target) return;
  target.scrollTo({
    top: target.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto',
  });
}

function applyAnchorScrollTop(force = false): void {
  const list = messageListRef.value;
  const userIndex = anchorUserIndex.value;
  if (!list || userIndex == null) return;

  const userSize = list.getItemSize(userIndex);
  if (userSize <= 0) {
    // Force le virtual scroller à rendre/mesurer l'item (historique long).
    beginProgrammaticScroll();
    list.scrollToItem(userIndex, { align: 'start' });
    releaseProgrammaticScrollAfter(48);
    scheduleAnchorTick();
    return;
  }

  const peek = clampAnchorPeek(userSize);
  const itemOffset = scrollToItemOffsetForPeek(userSize);
  // Clé stable pendant le tour (évite reflow à chaque token).
  const dedupeKey = userIndex * 1_000_000 + Math.round(userSize) * 1_000 + peek;
  if (!force && lastAppliedAnchorTop === dedupeKey) return;
  lastAppliedAnchorTop = dedupeKey;

  beginProgrammaticScroll();
  // scrollToItem + offset : le scroller stabilise les tailles non mesurées au-dessus.
  list.scrollToItem(userIndex, { align: 'start', offset: itemOffset });
  releaseProgrammaticScrollAfter(48);
}

function findLastUserMessageIndex(): number | null {
  for (let i = props.messages.length - 1; i >= 0; i -= 1) {
    if (props.messages[i]?.role === 'user') return i;
  }
  return null;
}

/** Hauteur réelle des messages sous le tour user (items typiquement mesurés / visibles). */
function measureResponseHeightBelowUser(userIndex: number): number {
  const list = messageListRef.value;
  if (!list) return 0;
  let height = 0;
  for (let i = userIndex + 1; i < props.messages.length; i += 1) {
    height += Math.max(0, list.getItemSize(i));
  }
  return height;
}

function updateAnchorLayout(): void {
  if (scrollMode.value !== 'anchor' || userDetached.value) return;

  const list = messageListRef.value;
  const target = list?.getScrollTarget();
  const userIndex = anchorUserIndex.value;
  if (!list || !target || userIndex == null) return;

  const userSize = list.getItemSize(userIndex);
  if (userSize <= 0) {
    beginProgrammaticScroll();
    list.scrollToItem(userIndex, { align: 'start' });
    releaseProgrammaticScrollAfter(48);
    scheduleAnchorTick();
    return;
  }

  const peek = clampAnchorPeek(userSize);
  // Inclut le header ThinkingCard replié (hauteur DOM via getItemSize).
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
      if (shouldPromoteAnchorToSticky(spacerHeight.value) && props.streaming) {
        enterStickyMode();
        scheduleScrollToBottom();
        return;
      }
      applyAnchorScrollTop(false);
    });
    return;
  }

  if (shouldPromoteAnchorToSticky(nextSpacer) && props.streaming) {
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

  // Prime : amène le message user dans le viewport pour forcer sa mesure
  // (et celle des voisins) avant le calcul de réserve / peek.
  const list = messageListRef.value;
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

/** Réessaie le scroll jusqu'à ce que scrollHeight se stabilise (virtual scroller). */
async function scrollToBottomStable(smooth = false): Promise<void> {
  await nextTick();
  beginProgrammaticScroll();
  const deadline = performance.now() + SCROLL_STABLE_TIMEOUT_MS;
  let lastHeight = -1;
  let attempts = 0;

  try {
    await new Promise<void>((resolve) => {
      const run = (): void => {
        const target = messageListRef.value?.getScrollTarget();
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

function handleSubmit(): void {
  const text = draft.value.trim();
  if (!text || props.streaming || draft.value.length > COMPOSER_MAX_LENGTH)
    return;
  if (isReading.value) return;
  const ready = attachments.value.filter((a) => a.status === 'ready');
  const shouldIndex = indexAttachmentsInMemory.value;
  emit('send', text, ready);
  if (shouldIndex) {
    void indexReadyAttachments(ready);
  }
  draft.value = '';
  clearAttachments();
  indexAttachmentsInMemory.value = false;
}

async function indexReadyAttachments(ready: ChatAttachment[]): Promise<void> {
  const dataDir = props.workspaceDataDir;
  if (!dataDir) return;
  for (const att of ready) {
    if (att.kind !== 'text' || !att.contentBase64) continue;
    try {
      const binary = atob(att.contentBase64);
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      const text = new TextDecoder().decode(bytes).trim();
      if (!text) continue;
      await addMemoryItem(
        dataDir,
        text.slice(0, 8000),
        'project',
        [`attachment:${att.fileName}`],
      );
    } catch {
      /* non bloquant */
    }
  }
}

function openFilePicker(): void {
  fileInputRef.value?.click();
}

function onFileInputChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  addFiles(input.files);
  // On réinitialise pour pouvoir re-sélectionner le même fichier ensuite.
  input.value = '';
}

function onPaste(event: ClipboardEvent): void {
  const files = event.clipboardData?.files;
  if (files && files.length > 0) {
    addFiles(files);
  }
}

function onDragEnter(): void {
  dragCounter.value += 1;
  setDragOver(true);
}

function onDragLeave(): void {
  dragCounter.value = Math.max(0, dragCounter.value - 1);
  if (dragCounter.value === 0) setDragOver(false);
}

function onDrop(event: DragEvent): void {
  dragCounter.value = 0;
  setDragOver(false);
  addFiles(event.dataTransfer?.files ?? null);
}

// Pendant sticky : suivre le bas. Pendant anchor / scroll programmatique :
// ne pas se laisser dé-pinner par arrivedState.
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
  () => props.messages.length,
  (length) => {
    bindScrollTarget();
    const prevCount = previousMessageCount;
    const grew = length > prevCount;
    previousMessageCount = length;
    if (suppressNextLengthAnchor) {
      suppressNextLengthAnchor = false;
      return;
    }
    if (grew && !userDetached.value) {
      // User+assistant sont poussés ensemble : last peut être assistant.
      // Ancrer dès qu'un message user apparaît dans le lot ajouté.
      let newUser = false;
      for (let i = prevCount; i < length; i += 1) {
        if (props.messages[i]?.role === 'user') {
          newUser = true;
          break;
        }
      }
      if (newUser) {
        void enterAnchorMode();
        return;
      }
    }
    if (scrollMode.value === 'sticky' && isPinned.value) {
      void scrollToBottomStable();
    }
  },
);

watch(
  () => props.sessionId,
  () => {
    suppressNextLengthAnchor = true;
    previousMessageCount = props.messages.length;
    enterStickyMode();
    bindScrollTarget();
    void scrollToBottomStable();
  },
);

watch(
  () => props.streaming,
  (streaming, wasStreaming) => {
    if (wasStreaming && !streaming) {
      cancelAnchorTick();
      const wasAnchor = scrollMode.value === 'anchor';
      // Réponse courte : retirer la réserve sans forcer un saut vers le bas
      // (question + réponse déjà visibles). Réponse longue déjà en sticky : follow.
      if (wasAnchor && !userDetached.value) {
        clearSpacer();
        scrollMode.value = 'sticky';
        anchorUserIndex.value = null;
        lastAppliedAnchorTop = null;
        // Pas de scrollToBottom : évite le saut brutal sur réponses courtes.
      } else if (!userDetached.value) {
        clearSpacer();
        if (scrollMode.value === 'anchor') {
          enterStickyMode();
        }
        if (isPinned.value && scrollMode.value === 'sticky') {
          void scrollToBottomStable();
        }
      } else {
        // Détaché : retirer la réserve sans bouger la vue.
        clearSpacer();
        if (scrollMode.value === 'anchor') {
          scrollMode.value = 'detached';
          anchorUserIndex.value = null;
          lastAppliedAnchorTop = null;
        }
      }
      return;
    }
    if (streaming && !wasStreaming) {
      if (userDetached.value) return;
      // Regenerate : pas de nouveau message user, mais on ré-ancre la question.
      const last = props.messages[props.messages.length - 1];
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

watch(
  () => {
    const last = props.messages[props.messages.length - 1];
    if (!last) return null;
    return [
      last.content,
      last.parts?.length,
      last.toolCalls?.length,
      last._contentRev,
      last.pendingConfirmation?.confirmationId,
      last.pendingPlan?.planId,
      // Repli/dépli ThinkingCard : remesure hauteur DOM.
      expansionEpoch.value,
    ] as const;
  },
  () => {
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
  void initCloud();
  previousMessageCount = props.messages.length;
  bindScrollTarget();
  void scrollToBottomStable();
});

onUnmounted(() => {
  cancelScheduledScroll();
  cancelAnchorTick();
  cancelProgrammaticReleaseTimer();
  programmaticScrollDepth = 0;
  unbindScrollListeners();
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

    .chat-view__composer {
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

.chat-view__composer {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
  padding: 0.6rem 1.25rem 0.5rem;
  background: var(--wp-surface);
}

.chat-view__engine-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
}

.chat-view__engine-banner-text {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.chat-view__engine-banner-action {
  flex: 0 0 auto;
  padding: 6px 12px;
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: var(--wp-accent);
    color: var(--wp-canard);
  }
}

.chat-view__memory-index {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  color: var(--wp-violet);
  cursor: pointer;

  input {
    accent-color: var(--wp-violet);
  }
}

/* Pilule : [+] [champ texte] à gauche, [send] à droite. */
.chat-view__composer-form {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 4px 6px 4px 8px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  transition:
    border-color var(--wp-dur) var(--wp-ease),
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

.chat-view__composer-input-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex: 1;
  min-width: 0;
}

.chat-view__composer--expanded .chat-view__composer-input-row {
  width: 100%;
}

.chat-view__composer-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.chat-view__composer--expanded .chat-view__composer-field {
  justify-content: flex-start;
}

.chat-view__composer-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: none;
}

.chat-view__composer--expanded .chat-view__composer-actions {
  width: 100%;
  justify-content: flex-end;
  padding-top: 4px;
}

.chat-view__file-input {
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

.chat-view__attach {
  position: relative;
  flex: 0 0 auto;
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-3);
  color: var(--wp-text);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    border-color: var(--wp-accent);
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }
}

.chat-view__attach--reasoning {
  border-color: color-mix(in srgb, var(--wp-accent) 45%, var(--wp-border));
}

.chat-view__attach-badge {
  position: absolute;
  top: -3px;
  right: -3px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: var(--wp-surface);
  border: 1px solid var(--wp-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

/* Menu « + » : pièces jointes, Regards et modèle/raisonnement. */
.chat-view__add-menu {
  min-width: 240px;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
  padding: 4px;
}

.chat-view__add-menu-scroll {
  max-height: min(70vh, 420px);
  overflow-y: auto;
}

.chat-view__add-head {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-text-faint);
  padding: 6px 8px;
}

.chat-view__add-sep {
  margin: 4px 0;
}

.chat-view__add-item {
  min-height: 40px;
  padding: 6px 8px;
  border-radius: var(--wp-r-sm);
  color: var(--wp-text);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.chat-view__add-icon {
  min-width: 28px;
  padding-right: 4px;
  justify-content: center;
}

.chat-view__add-item-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: 1.2;
}

.chat-view__add-item-hint {
  font-size: 0.72rem;
  color: var(--wp-text-faint);
  line-height: 1.25;
  margin-top: 2px;
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
  color: var(--wp-on-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 1px 2px color-mix(in srgb, var(--wp-accent) 35%, transparent);
  transition:
    background-color var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease),
    opacity var(--wp-dur) var(--wp-ease);

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
  transition:
    background-color var(--wp-dur) var(--wp-ease),
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
