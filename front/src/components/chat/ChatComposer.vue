<template>
  <div
    class="chat-composer"
    :class="{ 'chat-composer--expanded': isExpanded }"
  >
    <div
      v-if="showEngineBanner"
      class="chat-composer__engine-banner"
      role="status"
    >
      <p class="chat-composer__engine-banner-text">{{ engineBannerMessage }}</p>
      <button
        type="button"
        class="chat-composer__engine-banner-action"
        @click="onEngineBannerAction"
      >
        {{ engineBannerActionLabel }}
      </button>
    </div>
    <div
      v-if="showStreamErrorBanner"
      class="chat-composer__stream-error"
      role="alert"
    >
      <Lucide name="alert-circle" size="sm" color="danger" />
      <span class="chat-composer__stream-error-msg">{{ streamErrorMessage }}</span>
      <button
        type="button"
        class="chat-composer__stream-error-action"
        @click="emit('stream-error-report')"
      >
        <Lucide name="flag" size="xs" color="primary" />
        {{ t('errors.reportOpenAction') }}
      </button>
      <button
        v-if="streamErrorReconnect"
        type="button"
        class="chat-composer__stream-error-action"
        @click="emit('stream-error-reconnect')"
      >
        <Lucide name="log-in" size="xs" color="primary" />
        {{ t('errors.cloudReconnect') }}
      </button>
      <button
        v-if="streamError?.retryable && !streamErrorReconnect"
        type="button"
        class="chat-composer__stream-error-action"
        @click="emit('stream-error-retry')"
      >
        <Lucide name="rotate-ccw" size="xs" color="primary" />
        {{ t('common.retry') }}
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
      class="chat-composer__memory-index"
    >
      <input v-model="indexAttachmentsInMemory" type="checkbox" />
      <span>{{ t('chat.attachment.indexInMemory') }}</span>
    </label>
    <form class="chat-composer__form" @submit.prevent="handleSubmit">
      <input
        ref="fileInputRef"
        type="file"
        class="chat-composer__file-input"
        multiple
        :accept="ATTACHMENT_ACCEPT"
        @change="onFileInputChange"
      />
      <div class="chat-composer__tools">
        <button
          type="button"
          class="chat-composer__attach"
          :aria-label="attachAriaLabel"
          :title="attachTitle"
          aria-haspopup="menu"
        >
          <Lucide name="plus" size="18" color="wp-text" />
          <q-menu
            ref="addMenuRef"
            anchor="bottom left"
            self="top left"
            :offset="[0, 8]"
            :close-on-click="false"
            class="chat-composer__add-menu"
            transition-show="jump-down"
            transition-hide="jump-up"
          >
            <div class="chat-composer__add-menu-scroll">
              <div class="chat-composer__add-head">{{ t('chat.attachFile') }}</div>
              <q-list dense>
                <q-item
                  clickable
                  class="chat-composer__add-item"
                  @click="onAttachClick"
                >
                  <q-item-section avatar class="chat-composer__add-icon">
                    <Lucide name="paperclip" size="16" color="wp-text" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="chat-composer__add-item-label">
                      {{ t('chat.attachFile') }}
                    </q-item-label>
                    <q-item-label caption class="chat-composer__add-item-hint">
                      {{ t('chat.attachFileHint') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>

              <template v-if="showModelControl">
                <q-separator class="chat-composer__add-sep" />
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

        <button
          v-if="personasEnabled"
          type="button"
          class="chat-composer__regards"
          :aria-label="t('regards.chipAria')"
          :title="t('regards.chip')"
          aria-haspopup="menu"
        >
          <Lucide name="users" size="14" color="wp-gold" />
          <span>{{ t('regards.chip') }}</span>
          <q-menu
            ref="regardsMenuRef"
            anchor="bottom left"
            self="top left"
            :offset="[0, 8]"
            :close-on-click="false"
            class="chat-composer__add-menu chat-composer__regards-menu"
            transition-show="jump-down"
            transition-hide="jump-up"
          >
            <div class="chat-composer__add-menu-scroll">
              <div class="chat-composer__add-head">{{ t('chat.addMenuPersonas') }}</div>
              <q-list dense>
                <q-item
                  clickable
                  class="chat-composer__add-item chat-composer__regards-item"
                  @click.stop="onPersonasOpen"
                >
                  <q-item-section avatar class="chat-composer__add-icon">
                    <Lucide name="message-circle-question" size="16" color="wp-gold" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="chat-composer__add-item-label">
                      {{ t('regards.ask') }}
                    </q-item-label>
                    <q-item-label caption class="chat-composer__add-item-hint">
                      {{ t('regards.askHint') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
                <q-item
                  clickable
                  class="chat-composer__add-item chat-composer__regards-item"
                  :disable="streaming"
                  @click.stop="onPersonasMeeting"
                >
                  <q-item-section avatar class="chat-composer__add-icon">
                    <Lucide name="presentation" size="16" color="wp-gold" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="chat-composer__add-item-label">
                      {{ t('regards.cross') }}
                    </q-item-label>
                    <q-item-label caption class="chat-composer__add-item-hint">
                      {{ t('regards.crossHint') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
                <q-item
                  clickable
                  class="chat-composer__add-item chat-composer__regards-item"
                  @click.stop="onPersonasDiscuss"
                >
                  <q-item-section avatar class="chat-composer__add-icon">
                    <Lucide name="messages-square" size="16" color="wp-gold" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="chat-composer__add-item-label">
                      {{ t('regards.discuss') }}
                    </q-item-label>
                    <q-item-label caption class="chat-composer__add-item-hint">
                      {{ t('regards.discussHint') }}
                    </q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </div>
          </q-menu>
        </button>
      </div>

      <div class="chat-composer__field">
        <q-input
          ref="composerInputRef"
          v-model="draft"
          type="textarea"
          autogrow
          borderless
          class="chat-composer__input"
          :placeholder="t('chat.messagePlaceholder')"
          :maxlength="COMPOSER_MAX_LENGTH"
          @keydown.enter="onComposerEnter"
          @paste="onPaste"
        />
      </div>

      <div class="chat-composer__actions">
        <button
          v-if="streaming"
          type="button"
          class="chat-composer__stop"
          :aria-label="t('chat.stop')"
          :title="t('chat.stop')"
          @click="emit('abort')"
        >
          <Lucide name="square" size="16" color="wp-canard" />
        </button>
        <button
          v-else
          type="submit"
          class="chat-composer__send"
          :disabled="!canSend"
          :aria-label="t('chat.send')"
        >
          <Lucide name="arrow-up" size="18" color="text-invert" />
        </button>
      </div>
    </form>

    <p v-if="hasDraft" class="chat-composer__hint">
      {{ t('chat.composerHint') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import ChatModelMenuContent from '@components/chat/ChatModelMenuContent.vue';
import ChatComposerAttachments from '@components/chat/ChatComposerAttachments.vue';
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
import type { ChatAttachment, ChatError, ChatMessage, ReasoningEffort } from '#types';
import { addMemoryItem } from '@services/aiSidecar';
import type { QInput, QMenu } from 'quasar';
import { supportsReasoning } from '@utils/reasoningSupport';
import { hasModelChoice } from '@utils/modelCatalog';
import { hasSetModelChoice, supportsReasoningForSet } from '@utils/providerSetModels';

const COMPOSER_MAX_LENGTH = 32_000;

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  workspaceDataDir?: string | null;
  personasEnabled?: boolean;
  reasoningEffort?: ReasoningEffort | null;
  reasoningProvider?: LlmProviderName | null;
  reasoningModel?: string | null;
  settingsLocked?: boolean;
  streamError?: ChatError | null;
  streamErrorReconnect?: 'login' | 'enroll' | null;
}>();

const emit = defineEmits<{
  send: [text: string, attachments: ChatAttachment[]];
  abort: [];
  'update:reasoningEffort': [value: ReasoningEffort];
  'update:reasoningModel': [model: string];
  'personas-open': [];
  'personas-meeting': [];
  'personas-discuss': [];
  'stream-error-report': [];
  'stream-error-retry': [];
  'stream-error-reconnect': [];
}>();

const { t } = useI18n();
const router = useRouter();

const {
  attachments,
  hasAttachments,
  isReading,
  addFiles,
  removeAttachment,
  clear: clearAttachments,
} = useChatAttachments();

const fileInputRef = ref<HTMLInputElement | null>(null);
const addMenuRef = ref<QMenu | null>(null);
const regardsMenuRef = ref<QMenu | null>(null);
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

const lastAssistantError = computed(() => {
  for (let i = props.messages.length - 1; i >= 0; i -= 1) {
    if (props.messages[i]?.role === 'assistant') {
      return props.messages[i]?.error ?? null;
    }
  }
  return null;
});

const showStreamErrorBanner = computed(() => {
  if (!props.streamError) return false;
  const streamTurnId = props.streamError.turnId;
  if (!streamTurnId) return true;
  const assistantError = lastAssistantError.value;
  if (!assistantError?.turnId) return true;
  return assistantError.turnId !== streamTurnId;
});

const streamErrorMessage = computed(() => props.streamError?.message ?? '');

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

const attachTitle = computed(() => t('chat.addMenuTitle'));

const attachAriaLabel = computed(() =>
  t('chat.attachFileAria', { current: attachments.value.length, max: MAX_ATTACHMENTS }),
);

function closeAddMenu(): void {
  addMenuRef.value?.hide?.();
}

function closeRegardsMenu(): void {
  regardsMenuRef.value?.hide?.();
}

function onAttachClick(): void {
  openFilePicker();
  closeAddMenu();
}

function onPersonasOpen(): void {
  emit('personas-open');
  closeRegardsMenu();
}

function onPersonasMeeting(): void {
  if (props.streaming) return;
  emit('personas-meeting');
  closeRegardsMenu();
}

function onPersonasDiscuss(): void {
  emit('personas-discuss');
  closeRegardsMenu();
}

const draft = ref('');
const composerInputRef = ref<QInput | null>(null);

const canSend = computed(
  () =>
    draft.value.trim().length > 0 &&
    draft.value.length <= COMPOSER_MAX_LENGTH &&
    !props.streaming &&
    !isReading.value,
);

const hasDraft = computed(() => draft.value.trim().length > 0);
const isExpanded = computed(() => hasDraft.value || hasAttachments.value);

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
  addFiles,
});

function insertComposerNewline(e: KeyboardEvent): void {
  const el = e.target as HTMLTextAreaElement | null;
  const value = draft.value;
  if (value.length >= COMPOSER_MAX_LENGTH) return;

  if (!el || typeof el.selectionStart !== 'number') {
    draft.value = `${value}\n`;
    return;
  }

  const start = el.selectionStart;
  const end = el.selectionEnd;
  draft.value = `${value.slice(0, start)}\n${value.slice(end)}`;
  void nextTick(() => {
    const pos = start + 1;
    el.selectionStart = pos;
    el.selectionEnd = pos;
  });
}

function onComposerEnter(e: KeyboardEvent): void {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    insertComposerNewline(e);
    return;
  }
  if (e.shiftKey || e.altKey) return;
  e.preventDefault();
  handleSubmit();
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
  input.value = '';
}

function onPaste(event: ClipboardEvent): void {
  const files = event.clipboardData?.files;
  if (files && files.length > 0) {
    addFiles(files);
  }
}

onMounted(() => {
  void initCloud();
});
</script>

<style scoped lang="scss">
.chat-composer {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
  padding: 0.6rem 1.25rem 0.5rem;
  background: var(--wp-surface);
}

.chat-composer__engine-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
}

.chat-composer__engine-banner-text {
  margin: 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.chat-composer__engine-banner-action {
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

.chat-composer__stream-error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.5rem;
  padding: 0.5rem 0.65rem;
  font-size: var(--wp-fs-sm);
  color: var(--wp-danger);
  background: var(--wp-danger-soft);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-md);
}

.chat-composer__stream-error-msg {
  flex: 1 1 12rem;
  min-width: 0;
  line-height: var(--wp-lh-normal);
  word-break: break-word;
}

.chat-composer__stream-error-action {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong, var(--wp-accent));
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: var(--wp-accent);
    color: var(--wp-canard);
  }
}

.chat-composer__memory-index {
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

.chat-composer__form {
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

.chat-composer--expanded .chat-composer__form {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas:
    'field field'
    'tools actions';
  align-items: center;
  column-gap: 0.45rem;
  row-gap: 4px;
  border-radius: var(--wp-r-lg);
  padding: 10px 10px 8px;
}

.chat-composer__tools {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 0 0 auto;
}

.chat-composer--expanded .chat-composer__tools {
  grid-area: tools;
  justify-self: start;
}

.chat-composer__field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.chat-composer--expanded .chat-composer__field {
  grid-area: field;
  justify-content: flex-start;
}

.chat-composer__actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: none;
}

.chat-composer--expanded .chat-composer__actions {
  grid-area: actions;
  justify-self: end;
}

.chat-composer__file-input {
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

.chat-composer__attach {
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

.chat-composer__regards {
  position: relative;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  height: 2rem;
  padding: 0 0.7rem 0 0.55rem;
  border: 1px solid color-mix(in srgb, var(--wp-gold) 50%, var(--wp-border));
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease);

  &:hover {
    filter: brightness(0.97);
    border-color: var(--wp-gold);
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--wp-focus-ring);
  }
}

.chat-composer__add-menu {
  min-width: 240px;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
  padding: 4px;
}

.chat-composer__add-menu-scroll {
  max-height: min(70vh, 420px);
  overflow-y: auto;
}

.chat-composer__add-head {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-text-faint);
  padding: 6px 8px;
}

.chat-composer__add-sep {
  margin: 4px 0;
}

.chat-composer__add-item {
  min-height: 40px;
  padding: 6px 8px;
  border-radius: var(--wp-r-sm);
  color: var(--wp-text);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.chat-composer__add-icon {
  min-width: 28px;
  padding-right: 4px;
  justify-content: center;
}

.chat-composer__add-item-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  line-height: 1.2;
}

.chat-composer__add-item-hint {
  font-size: 0.72rem;
  color: var(--wp-text-faint);
  line-height: 1.25;
  margin-top: 2px;
}

.chat-composer__hint {
  margin: 0;
  padding: 0 0.4rem;
  font-size: 0.7rem;
  color: var(--wp-text-faint);
  line-height: 1.2;
}

.chat-composer__input {
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

.chat-composer__send {
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

.chat-composer__stop {
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
