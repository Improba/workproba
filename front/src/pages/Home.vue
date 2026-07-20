<template>
  <div class="home-page">
    <q-dialog
      v-model="engineWizardVisible"
      persistent
      no-esc-dismiss
      no-backdrop-dismiss
    >
      <EngineOnboardingWizard />
    </q-dialog>

    <section v-if="!activePath && sessionsChecked" class="home-page__onboarding">
      <h1 class="home-page__title">{{ t('home.welcomeShort') }}</h1>
      <p class="home-page__lead">
        {{ t('home.openSpaceLead') }}
      </p>
      <OpenSpaceButton :loading="loading" @click="openSpace" />
      <p v-if="error" class="home-page__error">{{ error }}</p>
    </section>

    <section
      v-else-if="activePath"
      class="home-page__workspace"
      :class="{ 'home-page__workspace--solo': sessionsReady && !recentSessions.length }"
    >
      <div class="home-page__stage">
        <div class="home-page__hub">
          <ChatView
            embedded
            layout="hub"
            :messages="[]"
            :streaming="false"
            :project-path="activePath"
            :workspace-data-dir="activeDataDir"
            :settings-locked="settingsLocked"
            :personas-enabled="isPersonasPluginActive"
            :reasoning-effort="homeReasoningEffort"
            :reasoning-provider="activeChatRouting?.provider ?? null"
            :reasoning-model="homeReasoningModel"
            @send="startConversationFromComposer"
            @update:reasoning-effort="onHomeReasoningEffortChange"
            @update:reasoning-model="onHomeReasoningModelChange"
          />
        </div>

        <footer v-if="recentSessions.length" class="home-page__history">
          <header class="home-page__history-head">
            <h2 class="home-page__history-title">{{ t('home.recentConversations') }}</h2>
          </header>
          <ul class="home-page__history-list">
            <li
              v-for="session in recentSessions"
              :key="session.id"
              class="home-page__history-row"
            >
              <button
                type="button"
                class="home-page__history-item"
                :aria-label="t('home.openSessionAria', { title: session.title })"
                @click="openSession(session.id)"
              >
                <span class="home-page__history-icon" aria-hidden="true">
                  <Lucide name="messages-square" size="15" color="text-faint" />
                </span>
                <span class="home-page__history-label">{{ session.title }}</span>
                <time
                  class="home-page__history-time"
                  :datetime="session.updatedAt"
                >
                  {{ formatRelative(session.updatedAt) }}
                </time>
                <Lucide
                  name="chevron-right"
                  size="14"
                  color="text-faint"
                  class="home-page__history-chevron"
                />
              </button>
            </li>
          </ul>
        </footer>

        <p v-if="error" class="home-page__error">{{ error }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import OpenSpaceButton from '@components/workspace/OpenSpaceButton.vue';
import ChatView from '@components/chat/ChatView.vue';
import EngineOnboardingWizard from '@components/onboarding/EngineOnboardingWizard.vue';
import { useSpace } from '@composables/useSpace';
import { useAppSettings } from '@composables/useAppSettings';
import { usePlugins } from '@composables/usePlugins';
import { setPendingChatLaunch } from '@composables/usePendingChatLaunch';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';
import { bumpSessions, useSessionSync } from '@composables/useSessionSync';
import { effectiveReasoningEffortFromSet } from '@utils/providerSets';
import { defaultReasoningEffort } from '@utils/reasoningSupport';
import type { ChatAttachment, ReasoningEffort } from '#types';

const router = useRouter();
const { t, locale } = useI18n();

const { activePath, activeSpaceId, activeDataDir, loading, error, openSpace } = useSpace();
const {
  settingsLocked,
  activeChatRouting,
  effectiveActiveSet,
  onboardingDone,
} = useAppSettings();
const { isPersonasPluginActive } = usePlugins();

const homeReasoningOverride = ref<ReasoningEffort | null>(null);
const homeModelOverride = ref<string | null>(null);

const homeReasoningModel = computed(
  () => homeModelOverride.value ?? activeChatRouting.value?.model ?? null,
);

const homeReasoningEffort = computed<ReasoningEffort>({
  get() {
    if (homeReasoningOverride.value != null) {
      return homeReasoningOverride.value;
    }
    const model = homeReasoningModel.value;
    const routing = activeChatRouting.value;
    if (!routing || !model) return 'none';
    if (effectiveActiveSet.value) {
      return effectiveReasoningEffortFromSet(
        effectiveActiveSet.value,
        homeModelOverride.value,
        null,
      );
    }
    return defaultReasoningEffort(routing.provider, model);
  },
  set(effort: ReasoningEffort) {
    homeReasoningOverride.value = effort;
  },
});

function onHomeReasoningEffortChange(effort: ReasoningEffort): void {
  homeReasoningEffort.value = effort;
}

function onHomeReasoningModelChange(model: string): void {
  homeModelOverride.value = model;
}

const engineWizardVisible = computed({
  get: () => !onboardingDone.value,
  set: () => {
    // Dialog persistant : fermeture uniquement via setOnboardingDone.
  },
});

const recentSessions = ref<LocalSession[]>([]);
const sessionsChecked = ref(false);
const sessionsReady = ref(false);

const { sessionVersion } = useSessionSync();

async function refreshSessions(): Promise<void> {
  if (!activePath.value || !activeSpaceId.value) {
    recentSessions.value = [];
    sessionsReady.value = true;
    return;
  }
  try {
    recentSessions.value = (await listSessions(
      activeSpaceId.value,
      activePath.value,
    )).slice(0, 8);
  } finally {
    sessionsReady.value = true;
  }
}

watch([activePath, activeSpaceId], () => {
  sessionsReady.value = false;
  void refreshSessions();
}, { immediate: true });

watch(sessionVersion, () => {
  void refreshSessions();
});

onMounted(() => {
  sessionsChecked.value = true;
});

function formatRelative(iso: string): string {
  const ts = new Date(iso).getTime();
  const diff = Date.now() - ts;
  if (diff < 60_000) return t('common.justNow');
  if (diff < 3_600_000) {
    return t('common.minutesAgo', { count: Math.floor(diff / 60_000) });
  }
  if (diff < 86_400_000) {
    return t('common.hoursAgo', { count: Math.floor(diff / 3_600_000) });
  }
  return new Date(iso).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
  });
}

function openSession(sessionId: string): void {
  void router.push({ name: 'chat_session', params: { id: sessionId } });
}

function startConversationFromComposer(
  prompt: string,
  attachments: ChatAttachment[],
): void {
  if (!activePath.value || !activeSpaceId.value) {
    Notify.create({
      message: t('shell.conversationCreateFailed'),
      classes: 'bg-danger text-white',
    });
    return;
  }
  void (async () => {
    try {
      const session = await createSession(
        activeSpaceId.value!,
        activePath.value!,
      );
      setPendingChatLaunch({
        text: prompt,
        attachments,
        reasoningEffort: homeReasoningEffort.value,
        model: homeReasoningModel.value,
      });
      bumpSessions();
      await router.push({
        name: 'chat_session',
        params: { id: session.id },
      });
    } catch (err) {
      Notify.create({
        message: err instanceof Error ? err.message : t('shell.conversationCreateFailed'),
        classes: 'bg-danger text-white',
      });
    }
  })();
}
</script>

<style scoped lang="scss">
.home-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  box-sizing: border-box;
  width: 100%;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
}

.home-page__onboarding {
  flex: 1;
  width: 100%;
  max-width: 28rem;
  margin: 0 auto;
  padding: clamp(2rem, 10vh, 4rem) 1.5rem 2.5rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1.25rem;
  box-sizing: border-box;
}

.home-page__workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  box-sizing: border-box;
  padding: clamp(1.5rem, 5vh, 2.5rem) clamp(1rem, 4vw, 2rem) 2.5rem;
}

.home-page__workspace--solo {
  justify-content: center;
}

.home-page__stage {
  width: 100%;
  max-width: 40rem;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
  box-sizing: border-box;
  flex: none;
}

.home-page__hub {
  min-width: 0;
  width: 100%;
}

.home-page__onboarding .home-page__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xl);
  font-weight: 700;
  line-height: 1.25;
  color: var(--wp-text);
  text-align: center;
}

.home-page__lead {
  margin: 0;
  font-size: 0.9375rem;
  color: var(--wp-text-muted);
  line-height: 1.6;
  text-align: center;
}

.home-page__error {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-danger);
  background: var(--wp-danger-soft);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-sm);
  padding: 0.45rem 0.65rem;
}

.home-page__history {
  width: 100%;
}

.home-page__history-head {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-bottom: 0.75rem;

  &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--wp-border);
  }
}

.home-page__history-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-faint);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.home-page__history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;
  max-height: min(22rem, 42vh);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.home-page__history-row {
  margin: 0;

  &:not(:last-child) .home-page__history-item {
    border-bottom: 1px solid var(--wp-border);
  }
}

.home-page__history-item {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 0.65rem;
  padding: 0.72rem 0.9rem;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background var(--wp-dur) var(--wp-ease);

  @media (max-width: 520px) {
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.5rem;
    padding: 0.65rem 0.75rem;
  }

  &:hover,
  &:focus-visible {
    background: var(--wp-surface-2);
    outline: none;

    .home-page__history-chevron {
      opacity: 1;
      transform: translateX(2px);
    }
  }
}

.home-page__history-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.home-page__history-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--wp-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.home-page__history-time {
  font-size: 0.75rem;
  color: var(--wp-text-faint);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.home-page__history-chevron {
  flex: none;
  opacity: 0;
  transition:
    opacity var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease);

  @media (max-width: 520px) {
    display: none;
  }
}

</style>
