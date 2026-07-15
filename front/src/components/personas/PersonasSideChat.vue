<template>
  <div class="personas-side-chat">
    <div v-if="!isPersonasPluginActive" class="personas-side-chat__unavailable">
      {{ t('personas.errors.unavailable') }}
    </div>
    <div v-else-if="loading" class="personas-side-chat__unavailable">
      {{ t('common.loading') }}
    </div>
    <div v-else-if="loadError" class="personas-side-chat__unavailable">
      {{ t('personas.errors.loadFailed') }}
    </div>
    <div v-else-if="selectablePersonas.length === 0" class="personas-side-chat__unavailable">
      {{ t('personas.picker.empty') }}
    </div>

    <template v-else>
      <PersonasConfidentialityHint class="personas-side-chat__privacy" />

      <header class="personas-side-chat__toolbar">
        <div class="personas-side-chat__modes" role="tablist">
          <button
            type="button"
            role="tab"
            class="personas-side-chat__mode"
            :class="{ 'personas-side-chat__mode--active': mode === 'avis' }"
            :aria-selected="mode === 'avis'"
            @click="switchMode('avis')"
          >
            {{ t('personas.sideChat.modeAvis') }}
          </button>
          <button
            type="button"
            role="tab"
            class="personas-side-chat__mode"
            :class="{ 'personas-side-chat__mode--active': mode === 'discussion' }"
            :aria-selected="mode === 'discussion'"
            @click="switchMode('discussion')"
          >
            {{ t('personas.sideChat.modeDiscussion') }}
          </button>
        </div>

        <button type="button" class="personas-side-chat__pick" @click="pickerOpen = true">
          {{ t('personas.sideChat.changePersonas') }}
        </button>

        <button type="button" class="personas-side-chat__meeting" @click="onStartMeeting">
          {{ t('personas.actions.simulateMeeting') }}
        </button>

        <div v-if="selectedPersonas.length" class="personas-side-chat__chips">
          <span
            v-for="persona in selectedPersonas"
            :key="persona.id"
            class="personas-side-chat__chip"
          >
            <span class="personas-side-chat__chip-dot" :style="{ backgroundColor: persona.avatar_color }" />
            {{ persona.name }}
          </span>
        </div>
      </header>

      <div ref="scrollRef" class="personas-side-chat__feed" role="log" aria-live="polite">
        <p v-if="feedEmpty && busy" class="personas-side-chat__empty">
          {{ t('common.inProgress') }}
        </p>
        <p v-else-if="feedEmpty" class="personas-side-chat__empty">
          {{ t('personas.sideChat.empty') }}
        </p>

        <template v-if="mode === 'avis'">
          <section
            v-for="entry in avisEntries"
            :key="entry.id"
            class="personas-side-chat__avis-entry"
          >
            <p class="personas-side-chat__question">{{ entry.question }}</p>
            <PersonasOpinionCard
              :card="entry.card"
              @another="onAnotherOpinion(entry)"
              @to-discussion="onToDiscussion(entry.card)"
            />
          </section>
        </template>

        <template v-else>
          <article
            v-for="msg in discussionMessages"
            :key="msg.id"
            class="personas-side-chat__message"
            :class="{
              'personas-side-chat__message--user': msg.role === 'user',
              'personas-side-chat__message--persona': msg.role === 'persona',
            }"
          >
            <header class="personas-side-chat__message-head">
              <PersonaAvatar
                v-if="msg.role === 'persona'"
                :name="msg.personaName ?? ''"
                :color="msg.avatarColor"
                :icon="msg.avatarIcon"
              />
              <Lucide v-else name="user" size="14" color="primary" />
              <span class="personas-side-chat__role">
                {{ msg.role === 'user' ? t('chat.roleUser') : `${msg.personaName} :` }}
              </span>
              <span v-if="msg.personaRole" class="personas-side-chat__persona-role">
                {{ msg.personaRole }}
              </span>
            </header>
            <MessageTextPart
              class="personas-side-chat__content"
              :content="msg.content"
              :streaming="!!msg.streaming"
            />
          </article>
        </template>
      </div>

      <form class="personas-side-chat__composer" @submit.prevent="onSend">
        <button
          v-if="mode === 'discussion' && isProjetPluginActive && discussionMessages.length > 0"
          type="button"
          class="personas-side-chat__publish"
          @click="publishOpen = true"
        >
          {{ t('personas.publishToProject') }}
        </button>
        <textarea
          v-model="draft"
          class="personas-side-chat__input"
          rows="2"
          :placeholder="composerPlaceholder"
          :disabled="busy"
        />
        <button type="submit" class="personas-side-chat__send" :disabled="!canSend">
          {{ busy ? t('common.inProgress') : t('personas.sideChat.send') }}
        </button>
      </form>
    </template>

    <PublishToProjectDialog
      v-model:open="publishOpen"
      :content="publishMarkdown"
      :default-name="publishDefaultName"
      :workspace-data-dir="activeDataDir"
    />

    <PersonasPicker
      v-model:open="pickerOpen"
      :personas="selectablePersonas"
      :loading="loading"
      :title="t('personas.sideChat.changePersonas')"
      :confirm-label="t('personas.sideChat.changePersonas')"
      :show-topic="false"
      :show-include-memory="mode === 'avis' || mode === 'discussion'"
      :busy="false"
      :estimate-mode="mode === 'avis' ? 'ask' : 'discuss'"
      :plugin-data-dir="pluginDataDir"
      @confirm="onPickerConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import PersonasPicker from '@components/personas/PersonasPicker.vue';
import PersonasConfidentialityHint from '@components/personas/PersonasConfidentialityHint.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useProject } from '@composables/useProject';
import {
  discussionMessagesToStored,
  formatDiscussionMarkdown,
  usePersonas,
  type DiscussionMessage,
} from '@composables/usePersonas';
import { useSideChat } from '@composables/useSideChat';
import { usePersonasActions } from '@composables/usePersonasActions';
import type { PersonasOpinionCard as PersonasOpinionCardType } from '#types';
import type { PersonaInfo } from '@services/aiSidecar';

defineProps<{
  pluginId: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const { t, locale } = useI18n();
const {
  selectablePersonas,
  loading,
  loadError,
  refresh,
  askOpinion,
  discuss,
  saveDiscussion,
  findPersona,
} = usePersonas();
const { getPluginDataDir, isPersonasPluginActive, isProjetPluginActive } = usePlugins();
const { activeDataDir } = useProject();
const { consumeInitial, peekInitial, launchToken } = useSideChat();
const { startMeeting } = usePersonasActions();

const mode = ref<'avis' | 'discussion'>('avis');
const selectedPersonaIds = ref<string[]>([]);
const avisEntries = ref<
  Array<{ id: string; kind: 'avis'; question: string; card: PersonasOpinionCardType }>
>([]);
const discussionMessages = ref<DiscussionMessage[]>([]);
const discussionId = ref<string | null>(null);
const draft = ref('');
const busy = ref(false);
const pickerOpen = ref(false);
const publishOpen = ref(false);
const includeMemory = ref(false);
const pluginDataDir = ref<string | null>(null);
const scrollRef = ref<HTMLElement | null>(null);
const sendGeneration = ref(0);
const pendingInit = ref(false);
const conversationContext = ref('');
const pendingAutoAsk = ref(false);
const deferredPersonaIds = ref<string[]>([]);

type SideChatInitialPayload = ReturnType<typeof peekInitial>;

function hasInitialPayload(initial: SideChatInitialPayload): boolean {
  return (
    initial.mode != null
    || initial.personaIds.length > 0
    || initial.draft.length > 0
    || initial.discussionSeed != null
    || initial.conversationContext.length > 0
    || initial.autoAsk
    || initial.resume != null
  );
}

const selectedPersonas = computed(() =>
  selectedPersonaIds.value
    .map((id) => findPersona(id))
    .filter((p): p is PersonaInfo => p != null),
);

const composerPlaceholder = computed(() =>
  mode.value === 'avis'
    ? t('personas.sideChat.placeholder.avis')
    : t('personas.sideChat.placeholder.discussion'),
);

const feedEmpty = computed(() =>
  mode.value === 'avis'
    ? avisEntries.value.length === 0
    : discussionMessages.value.length === 0,
);

const canSend = computed(
  () => !busy.value && draft.value.trim().length > 0 && selectedPersonas.value.length > 0,
);

const publishMarkdown = computed(() =>
  formatDiscussionMarkdown(
    selectedPersonas.value.map((p) => p.name),
    discussionMessages.value,
  ),
);

const publishDefaultName = computed(() => {
  const date = new Date().toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  return t('personas.publishToProjectNameDiscussion', { date });
});

watch(
  () => (mode.value === 'avis' ? avisEntries.value.length : discussionMessages.value.length),
  async () => {
    await nextTick();
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  },
);

function switchMode(next: 'avis' | 'discussion'): void {
  if (mode.value === next) return;
  mode.value = next;
}

function onStartMeeting(): void {
  emit('close');
  void startMeeting();
}

function onAnotherOpinion(entry: { question: string; card: PersonasOpinionCardType }): void {
  draft.value = entry.question;
  pickerOpen.value = true;
}

function onToDiscussion(card: PersonasOpinionCardType): void {
  const ids = filterKnownPersonaIds(card.opinions.map((o) => o.personaId));
  selectedPersonaIds.value = ids;
  mode.value = 'discussion';
  discussionMessages.value = [
    {
      id: `ctx_${Date.now()}`,
      role: 'user',
      content: card.question,
    },
  ];
  discussionId.value = null;
}

function onPickerConfirm(payload: {
  personaIds: string[];
  includeMemory: boolean;
}): void {
  selectedPersonaIds.value = payload.personaIds;
  includeMemory.value = payload.includeMemory;
  pickerOpen.value = false;
}

async function ensureDataDir(): Promise<string | null> {
  if (pluginDataDir.value) return pluginDataDir.value;
  try {
    pluginDataDir.value = await getPluginDataDir(PERSONAS_PLUGIN_ID);
    return pluginDataDir.value;
  } catch {
    return null;
  }
}

async function sendMessage(text: string): Promise<boolean> {
  if (!text || selectedPersonaIds.value.length === 0 || busy.value) return false;

  busy.value = true;
  const gen = ++sendGeneration.value;

  const dir = await ensureDataDir();
  if (!dir) {
    busy.value = false;
    Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
    return false;
  }

  if (gen !== sendGeneration.value) return false;

  const context = conversationContext.value.trim() || undefined;

  try {
    if (mode.value === 'avis') {
      const card = await askOpinion(
        dir,
        selectedPersonaIds.value,
        text,
        context,
        activeDataDir.value,
        includeMemory.value,
      );
      avisEntries.value.push({
        id: `avis_${Date.now()}`,
        kind: 'avis',
        question: text,
        card,
      });
    } else {
      const result = await discuss(
        dir,
        selectedPersonaIds.value,
        text,
        discussionId.value,
        discussionMessages.value,
        (msgs) => {
          if (gen !== sendGeneration.value) return;
          discussionMessages.value = msgs;
        },
        activeDataDir.value,
        includeMemory.value,
        context,
      );
      discussionId.value = result.discussionId;
      discussionMessages.value = result.messages;
      if (result.discussionId) {
        saveDiscussion(
          discussionMessagesToStored(
            result.discussionId,
            selectedPersonaIds.value,
            result.messages,
          ),
        );
      }
    }
    return true;
  } catch {
    if (gen !== sendGeneration.value) return false;
    Notify.create({
      message:
        mode.value === 'avis'
          ? t('personas.errors.askFailed')
          : t('personas.errors.discussFailed'),
      color: 'negative',
    });
    return false;
  } finally {
    if (gen === sendGeneration.value) {
      busy.value = false;
    }
  }
}

async function onSend(): Promise<void> {
  const text = draft.value.trim();
  if (!text || selectedPersonaIds.value.length === 0 || busy.value) return;

  const savedDraft = text;
  draft.value = '';
  const ok = await sendMessage(savedDraft);
  if (!ok) {
    draft.value = savedDraft;
  }
}

async function maybeAutoAsk(): Promise<void> {
  if (!pendingAutoAsk.value || busy.value) return;
  if (mode.value !== 'avis' && mode.value !== 'discussion') {
    pendingAutoAsk.value = false;
    deferredPersonaIds.value = [];
    return;
  }

  if (selectedPersonaIds.value.length === 0) {
    if (deferredPersonaIds.value.length > 0) {
      await ensurePersonasReady();
      selectedPersonaIds.value = filterKnownPersonaIds(deferredPersonaIds.value);
    }
  }

  if (selectedPersonaIds.value.length === 0) {
    return;
  }

  pendingAutoAsk.value = false;
  deferredPersonaIds.value = [];
  const defaultQuestion = mode.value === 'discussion'
    ? t('personas.sideChat.defaultDiscussionQuestion')
    : t('personas.sideChat.defaultOpinionQuestion');
  const question = draft.value.trim() || defaultQuestion;
  draft.value = '';
  await sendMessage(question);
}

async function ensurePersonasReady(): Promise<void> {
  const dir = await ensureDataDir();
  if (!dir) return;
  if (!loading.value && selectablePersonas.value.length > 0) return;
  await refresh(dir);
}

function filterKnownPersonaIds(ids: string[]): string[] {
  return ids.filter((id) => findPersona(id) != null);
}

function resetFeedState(): void {
  avisEntries.value = [];
  discussionMessages.value = [];
  discussionId.value = null;
  draft.value = '';
  conversationContext.value = '';
  pendingAutoAsk.value = false;
  deferredPersonaIds.value = [];
}

function applyInitialPayload(initial: SideChatInitialPayload): void {
  if (initial.resume) {
    const knownIds = filterKnownPersonaIds(initial.resume.personaIds);
    if (knownIds.length < initial.resume.personaIds.length) {
      Notify.create({
        message: t('personas.errors.personasUnavailable'),
        color: 'warning',
      });
    }
    mode.value = 'discussion';
    discussionId.value = initial.resume.discussionId;
    selectedPersonaIds.value = knownIds.length > 0 ? knownIds : filterKnownPersonaIds(
      initial.resume.messages
        .map((m) => m.personaId)
        .filter((id): id is string => Boolean(id)),
    );
    discussionMessages.value = initial.resume.messages.map((m) => ({ ...m }));
    return;
  }

  if (initial.mode === 'avis' || initial.mode === 'discussion') {
    mode.value = initial.mode;
  }
  conversationContext.value = initial.conversationContext;
  if (initial.draft) {
    draft.value = initial.draft;
  }
  if (initial.discussionSeed) {
    discussionMessages.value = [
      {
        id: `ctx_${Date.now()}`,
        role: 'user',
        content: initial.discussionSeed,
      },
    ];
    discussionId.value = null;
  } else if (initial.mode === 'discussion') {
    discussionMessages.value = [];
    discussionId.value = null;
  }

  const knownIds = filterKnownPersonaIds(initial.personaIds);
  selectedPersonaIds.value = knownIds;
  if (initial.autoAsk) {
    pendingAutoAsk.value = true;
    deferredPersonaIds.value = knownIds.length > 0 ? [] : [...initial.personaIds];
  }
}

function applySideChatInitial(): void {
  if (busy.value) {
    pendingInit.value = true;
    return;
  }
  pendingInit.value = false;

  const peeked = peekInitial();
  if (!hasInitialPayload(peeked)) return;

  sendGeneration.value += 1;
  busy.value = false;
  resetFeedState();

  const initial = consumeInitial();
  applyInitialPayload(initial);
  void maybeAutoAsk();
}

watch(launchToken, () => {
  applySideChatInitial();
});

watch([loading, selectablePersonas], () => {
  if (pendingAutoAsk.value && !busy.value) {
    void maybeAutoAsk();
  }
});

watch(busy, (isBusy) => {
  if (!isBusy && pendingInit.value) {
    applySideChatInitial();
  } else if (!isBusy && pendingAutoAsk.value) {
    void maybeAutoAsk();
  }
});

onUnmounted(() => {
  sendGeneration.value += 1;
  if (pendingInit.value) {
    consumeInitial();
    pendingInit.value = false;
  }
});

onMounted(async () => {
  const dir = await ensureDataDir();
  if (dir) await refresh(dir);
  applySideChatInitial();
  if (pendingAutoAsk.value) {
    void maybeAutoAsk();
  }
});

defineExpose({ close: () => emit('close') });
</script>

<style scoped lang="scss">
.personas-side-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--wp-bg);
}

.personas-side-chat__unavailable {
  margin: auto;
  padding: var(--wp-space-4);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-align: center;
}

.personas-side-chat__privacy {
  flex: none;
  padding: var(--wp-space-2) var(--wp-space-3) 0;
}

.personas-side-chat__toolbar {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.personas-side-chat__modes {
  display: flex;
  gap: var(--wp-space-1);
}

.personas-side-chat__mode {
  flex: 1;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }

  &--active {
    border-color: var(--wp-gold);
    color: var(--wp-text);
    font-weight: 600;
    background: var(--wp-accent-soft);
  }
}

.personas-side-chat__pick,
.personas-side-chat__meeting {
  align-self: flex-start;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.personas-side-chat__meeting {
  color: var(--wp-gold);
  border-color: var(--wp-gold-soft);
}

.personas-side-chat__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1);
}

.personas-side-chat__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: 2px var(--wp-space-2);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-side-chat__chip-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--wp-r-pill);
  flex: none;
}

.personas-side-chat__feed {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--wp-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.personas-side-chat__empty {
  margin: auto;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-align: center;
}

.personas-side-chat__avis-entry {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.personas-side-chat__question {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.personas-side-chat__message {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  padding: var(--wp-space-2);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);

  &--user {
    border-color: var(--wp-accent-soft);
  }

  &--persona {
    border-color: color-mix(in srgb, var(--wp-gold) 35%, var(--wp-border));
  }
}

.personas-side-chat__message-head {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  flex-wrap: wrap;
}

.personas-side-chat__role {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
}

.personas-side-chat__persona-role {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-side-chat__content {
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);

  :deep(.chat-message__markdown) {
    font-family: inherit;
    font-size: inherit;
    line-height: inherit;
    color: inherit;
  }

  :deep(p) {
    margin: 0 0 0.5rem;
  }

  :deep(p:last-child) {
    margin-bottom: 0;
  }

  :deep(ul),
  :deep(ol) {
    margin: 0.25rem 0 0.5rem 1.1rem;
  }
}

.personas-side-chat__composer {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.personas-side-chat__publish {
  align-self: flex-start;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
  cursor: pointer;

  &:hover {
    background: var(--wp-gold-soft);
  }
}

.personas-side-chat__input {
  width: 100%;
  resize: vertical;
  min-height: 56px;
  padding: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &:focus {
    outline: none;
    border-color: var(--wp-accent);
  }

  &:disabled {
    opacity: 0.6;
  }
}

.personas-side-chat__send {
  align-self: flex-end;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent, #fff);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
