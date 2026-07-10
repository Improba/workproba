<template>
  <div class="chat-page">
    <header class="chat-page__header">
      <h1 class="chat-page__title">{{ sessionTitle }}</h1>
      <div v-if="streamError" class="chat-page__error" role="alert">
        <Lucide name="alert-circle" size="sm" color="danger" />
        <span class="chat-page__error-msg">{{ streamError.message }}</span>
        <button
          v-if="streamError.retryable"
          type="button"
          class="chat-page__retry"
          @click="retry"
        >
          <Lucide name="rotate-ccw" size="xs" color="primary" />
          Réessayer
        </button>
      </div>
    </header>

    <section class="chat-page__body">
      <ChatView
        ref="chatViewRef"
        :messages="messages"
        :streaming="streaming"
        :project-path="activePath"
        :session-id="sessionId"
        :confirming="confirming"
        @send="send"
        @abort="abort"
        @open-file="handleOpenFile"
        @confirm-approve="() => confirm('approve')"
        @confirm-deny="() => confirm('deny')"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, toRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Notify } from 'quasar';
import { useDebounceFn } from '@vueuse/core';
import ChatView from '@components/chat/ChatView.vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useChatActivity } from '@composables/useChatActivity';
import { useChatStream } from '@composables/useChatStream';
import { useAppSettings } from '@composables/useAppSettings';
import { openLocalFile } from '@composables/useDesktop';
import { useProject } from '@composables/useProject';
import { resolveUiMode } from '@services/aiSidecar';
import { getSession, saveSession } from '@services/workspaceSession';
import type { ChatMessage } from '#types';

const route = useRoute();
const router = useRouter();

const sessionId = computed(() => String(route.params.id ?? ''));
const sessionTitle = ref('Conversation');
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null);

const { activePath, activeDataDir, documents } = useProject();
const { settingsMode, settingsLocked } = useAppSettings();
const { setStreaming, setSidecarState } = useChatActivity();

const uiMode = computed(() =>
  resolveUiMode(settingsLocked.value, settingsMode.value),
);

const {
  messages,
  streaming,
  error: streamError,
  confirming,
  send,
  confirm,
  retry,
  abort,
  loadMessages,
} = useChatStream({
  sessionId: toRef(() => sessionId.value),
  projectPath: activePath,
  workspaceDataDir: activeDataDir,
  documents,
  uiMode,
});

watch(
  [streaming, streamError],
  ([isStreaming, err]) => {
    setStreaming(isStreaming);
    if (err) {
      setSidecarState('error');
    } else if (isStreaming) {
      setSidecarState('working');
    } else {
      setSidecarState('connected');
    }
  },
  { immediate: true },
);

watch(
  sessionId,
  async (id) => {
    if (!id) return;

    // Couper d'abord un éventuel stream en cours (changement de conversation
    // pendant une réponse) pour ne pas écrire dans la mauvaise session.
    abort();

    const session = await getSession(id);
    if (!session) {
      Notify.create({
        message: 'Session introuvable',
        classes: 'bg-danger text-neutral-lowest',
      });
      void router.push({ name: 'home' });
      return;
    }
    sessionTitle.value = session.title || 'Conversation';
    loadMessages(session.messages ?? []);
    await applyInitialPrompt();
  },
  { immediate: true },
);

async function applyInitialPrompt(): Promise<void> {
  const state = history.state as { initialPrompt?: string } | null;
  const prompt = state?.initialPrompt?.trim();
  if (!prompt) return;

  await nextTick();
  chatViewRef.value?.setDraft(prompt);
  history.replaceState({ ...history.state, initialPrompt: undefined }, '');
}

// Sauvegarde debouncée : on évite la rafale d'écriturs pendant le streaming
// (le watch deep se déclenche à chaque flush de tokens) et les races
// read-modify-write concurrentes sur le fichier de session.
const persistSession = useDebounceFn(async (items: ChatMessage[]) => {
  if (!activePath.value) return;
  const session = await getSession(sessionId.value);
  if (!session) return;
  await saveSession({
    ...session,
    messages: items.filter((m) => !m.streaming),
  });
}, 500);

watch(
  messages,
  (items) => {
    void persistSession(items);
  },
  { deep: true },
);

async function handleOpenFile(path: string): Promise<void> {
  try {
    await openLocalFile(path, activePath.value);
  } catch {
    Notify.create({
      message: `Impossible d'ouvrir ${path}`,
      classes: 'bg-danger text-neutral-lowest',
    });
  }
}

onUnmounted(() => {
  abort();
  setStreaming(false);
});
</script>

<style scoped lang="scss">
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
}

.chat-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-shrink: 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
  margin-bottom: 0.75rem;
}

.chat-page__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-page__error {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
  max-width: 60%;
  font-size: 0.8125rem;
  color: var(--wp-danger);
  background: var(--wp-danger-soft);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-sm);
  padding: 0.35rem 0.55rem;
}

.chat-page__error-msg {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-page__retry {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
  border: 1px solid var(--primary-low);
  border-radius: 6px;
  background: var(--primary-lowest);
  color: var(--text-link);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: var(--primary-lower);
  }
}

.chat-page__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
