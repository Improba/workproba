<template>
  <div class="home-page">
    <q-dialog
      v-model="profileDialogVisible"
      persistent
      no-esc-dismiss
      no-backdrop-dismiss
    >
      <div class="home-page__profile-dialog">
        <header class="home-page__profile-head">
          <span class="home-page__profile-icon" aria-hidden="true">
            <Lucide name="user-round" size="28" color="wp-accent" />
          </span>
          <h2 class="home-page__profile-title">{{ t('home.onboarding.title') }}</h2>
          <p class="home-page__profile-lead">{{ t('home.onboarding.lead') }}</p>
        </header>

        <div class="home-page__profile-fields">
          <label class="home-page__profile-field" for="home-profile-name">
            <span class="home-page__profile-label">{{ t('home.onboarding.nameLabel') }}</span>
            <input
              id="home-profile-name"
              v-model="profileNameDraft"
              type="text"
              class="home-page__profile-input"
              :placeholder="t('home.onboarding.namePlaceholder')"
              autocomplete="name"
            />
          </label>

          <label class="home-page__profile-field" for="home-profile-org">
            <span class="home-page__profile-label">{{ t('home.onboarding.orgLabel') }}</span>
            <input
              id="home-profile-org"
              v-model="profileOrgDraft"
              type="text"
              class="home-page__profile-input"
              :placeholder="t('home.onboarding.orgPlaceholder')"
              autocomplete="organization"
            />
          </label>
        </div>

        <footer class="home-page__profile-foot">
          <button
            type="button"
            class="home-page__profile-submit"
            :disabled="!profileNameDraft.trim() || profileSaving"
            @click="submitProfileOnboarding"
          >
            {{ t('home.onboarding.start') }}
          </button>
        </footer>
      </div>
    </q-dialog>

    <section
      v-if="showFirstLaunchOnboarding"
      class="home-page__onboarding home-page__onboarding--guided"
    >
      <h1 class="home-page__welcome">
        {{ t('home.welcomeTitle') }}
      </h1>

      <ol class="home-page__steps">
        <li class="home-page__step">
          <span class="home-page__step-badge">{{ t('home.stepBadge', { n: 1 }) }}</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="layers" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">{{ t('home.step1Title') }}</p>
            <p class="home-page__step-text">
              {{ t('home.step1Text') }}
            </p>
            <OpenSpaceButton :loading="loading" @click="openSpace" />
          </div>
        </li>

        <li class="home-page__step">
          <span class="home-page__step-badge">{{ t('home.stepBadge', { n: 2 }) }}</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="messages-square" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">{{ t('home.step2Title') }}</p>
            <p class="home-page__step-text">
              {{ t('home.step2Text') }}
            </p>
          </div>
        </li>

        <li class="home-page__step">
          <span class="home-page__step-badge">{{ t('home.stepBadge', { n: 3 }) }}</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="file-plus" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">{{ t('home.step3Title') }}</p>
            <p class="home-page__step-text">
              {{ t('home.step3Text') }}
            </p>
          </div>
        </li>
      </ol>

      <button
        type="button"
        class="home-page__skip"
        @click="skipOnboarding"
      >
        {{ t('home.skipOnboarding') }}
      </button>

      <p v-if="error" class="home-page__error">{{ error }}</p>
    </section>

    <section v-else-if="!activePath && sessionsChecked" class="home-page__onboarding">
      <h1 class="home-page__title">{{ t('home.welcomeShort') }}</h1>
      <p class="home-page__lead">
        {{ t('home.openSpaceLead') }}
      </p>
      <OpenSpaceButton :loading="loading" @click="openSpace" />
      <p v-if="error" class="home-page__error">{{ error }}</p>
    </section>

    <section v-else class="home-page__workspace">
      <header class="home-page__header">
        <div class="home-page__header-text">
          <h1 class="home-page__title">{{ workspaceTitle || t('home.spaceTitle') }}</h1>
          <p class="home-page__path" :title="activePath ?? undefined">
            {{ activePath ? t('shell.spacePathHint', { path: activePath }) : '' }}
          </p>
        </div>
        <div class="home-page__actions">
          <OpenSpaceButton
            :loading="loading"
            :label="t('common.changeSpace')"
            @click="openSpace"
          />
          <button
            type="button"
            class="home-page__new-chat"
            :disabled="loading"
            @click="startNewConversation"
          >
            <Lucide name="message-square-plus" size="sm" color="wp-canard" />
            {{ t('common.newConversation') }}
          </button>
        </div>
      </header>

      <p v-if="error" class="home-page__error">{{ error }}</p>

      <section v-if="recentSessions.length" class="home-page__sessions">
        <h2 class="home-page__section-title">{{ t('home.recentConversations') }}</h2>
        <ul class="home-page__session-list">
          <li
            v-for="session in recentSessions"
            :key="session.id"
            class="home-page__session-item"
          >
            <button
              type="button"
              class="home-page__session-link"
              @click="openSession(session.id)"
            >
              <span class="home-page__session-title">{{ session.title }}</span>
              <span class="home-page__session-date">
                {{ formatDate(session.updatedAt) }}
              </span>
            </button>
          </li>
        </ul>
      </section>

      <section v-else class="home-page__empty">
        <p class="home-page__empty-text">
          {{ t('home.emptyConversations') }}
        </p>
        <StartPrompts @select="startConversationWithPrompt" />
        <button
          type="button"
          class="home-page__new-chat home-page__new-chat--secondary"
          :disabled="loading"
          @click="startNewConversation"
        >
          <Lucide name="message-square-plus" size="sm" color="wp-canard" />
          {{ t('home.startEmptyConversation') }}
        </button>
      </section>
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
import StartPrompts from '@components/chat/StartPrompts.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useUserProfile } from '@composables/useUserProfile';
import { listWorkspaces } from '@composables/useDesktop';
import { useProject } from '@composables/useProject';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';
import { bumpSessions } from '@composables/useSessionSync';

const router = useRouter();
const { t, locale } = useI18n();

const {
  activePath,
  activeWorkspaceId,
  workspaceTitle,
  loading,
  error,
  openSpace,
} = useProject();

const { onboardingDone, loaded: settingsLoaded, setOnboardingDone } = useAppSettings();

const {
  needsOnboarding: needsProfileOnboarding,
  completeOnboarding: completeProfileOnboarding,
} = useUserProfile();

const profileNameDraft = ref('');
const profileOrgDraft = ref('');
const profileSaving = ref(false);

const profileDialogVisible = computed({
  get: () => needsProfileOnboarding.value,
  set: () => {
    // Dialog persistant : fermeture uniquement via completeOnboarding.
  },
});

async function submitProfileOnboarding(): Promise<void> {
  if (!profileNameDraft.value.trim() || profileSaving.value) return;
  profileSaving.value = true;
  try {
    await completeProfileOnboarding({
      name: profileNameDraft.value,
      organisation: profileOrgDraft.value,
    });
  } finally {
    profileSaving.value = false;
  }
}

const recentSessions = ref<LocalSession[]>([]);
const hasAnySessions = ref(false);
const sessionsChecked = ref(false);

const showFirstLaunchOnboarding = computed(
  () =>
    settingsLoaded.value
    && sessionsChecked.value
    && !activePath.value
    && !hasAnySessions.value
    && !onboardingDone.value
    && !needsProfileOnboarding.value,
);

async function refreshSessions(): Promise<void> {
  if (!activePath.value || !activeWorkspaceId.value) {
    recentSessions.value = [];
    return;
  }
  recentSessions.value = (await listSessions(
    activeWorkspaceId.value,
    activePath.value,
  )).slice(0, 8);
}

async function checkAnySessions(): Promise<void> {
  const workspaces = await listWorkspaces();
  for (const workspace of workspaces) {
    const sessions = await listSessions(workspace.id, workspace.folderPath);
    if (sessions.length > 0) {
      hasAnySessions.value = true;
      sessionsChecked.value = true;
      return;
    }
  }
  hasAnySessions.value = false;
  sessionsChecked.value = true;
}

watch([activePath, activeWorkspaceId], () => {
  void refreshSessions();
}, { immediate: true });

onMounted(() => {
  void checkAnySessions();
});

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(locale.value, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function startNewConversation(): void {
  if (!activePath.value || !activeWorkspaceId.value) {
    Notify.create({
      message: t('shell.conversationCreateFailed'),
      classes: 'bg-danger text-white',
    });
    return;
  }
  void (async () => {
    try {
      const session = await createSession(
        activeWorkspaceId.value!,
        activePath.value!,
      );
      bumpSessions();
      await router.push({
        name: 'chat_session',
        params: { id: session.id },
        state: { focusComposer: true },
      });
    } catch (err) {
      Notify.create({
        message: err instanceof Error ? err.message : t('shell.conversationCreateFailed'),
        classes: 'bg-danger text-white',
      });
    }
  })();
}

function startConversationWithPrompt(prompt: string): void {
  if (!activePath.value || !activeWorkspaceId.value) {
    Notify.create({
      message: t('shell.conversationCreateFailed'),
      classes: 'bg-danger text-white',
    });
    return;
  }
  void (async () => {
    try {
      const session = await createSession(
        activeWorkspaceId.value!,
        activePath.value!,
      );
      bumpSessions();
      await router.push({
        name: 'chat_session',
        params: { id: session.id },
        state: { initialPrompt: prompt },
      });
    } catch (err) {
      Notify.create({
        message: err instanceof Error ? err.message : t('shell.conversationCreateFailed'),
        classes: 'bg-danger text-white',
      });
    }
  })();
}

function openSession(sessionId: string): void {
  void router.push({ name: 'chat_session', params: { id: sessionId } });
}

function skipOnboarding(): void {
  void setOnboardingDone(true);
}
</script>

<style scoped lang="scss">
.home-page {
  height: 100%;
  min-height: 0;
  overflow: auto;
  box-sizing: border-box;
  max-width: 960px;
  margin: 0 auto;
  padding: 32px;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
}

.home-page__onboarding,
.home-page__workspace {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.home-page__onboarding {
  padding-top: 2rem;
}

.home-page__onboarding--guided {
  gap: 1.75rem;
}

.home-page__welcome {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-display, 2rem);
  font-weight: 700;
  line-height: 1.25;
  color: var(--wp-text);
}

.home-page__onboarding .home-page__title {
  font-family: var(--wp-font-head);
  font-size: 2rem;
  font-weight: 700;
}

.home-page__steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.home-page__step {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 0.85rem 1rem;
  align-items: start;
  padding: 1rem 1.1rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
}

.home-page__step-badge {
  grid-row: 1 / span 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 999px;
  background: var(--wp-accent-soft);
  color: var(--wp-canard);
  font-size: 0.8125rem;
  font-weight: 700;
}

.home-page__step-icon {
  grid-row: 1 / span 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
}

.home-page__step-body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.home-page__step-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: 1rem;
  font-weight: 700;
  color: var(--wp-text);
}

.home-page__step-text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--wp-text-muted);
  line-height: 1.45;
}

.home-page__skip {
  align-self: flex-start;
  border: none;
  background: none;
  padding: 0;
  font-size: 0.875rem;
  color: var(--wp-text-muted);
  text-decoration: underline;
  cursor: pointer;
  transition: color var(--wp-dur) var(--wp-ease);

  &:hover {
    color: var(--wp-text);
  }
}

.home-page__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.home-page__header-text {
  min-width: 0;
  flex: 1;
}

.home-page__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--wp-text);
}

.home-page__lead {
  margin: 0;
  font-size: 0.9375rem;
  color: var(--wp-text-muted);
  line-height: 1.6;
}

.home-page__path {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  color: var(--wp-text-faint);
  word-break: break-all;
}

.home-page__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.home-page__new-chat {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.6rem 1rem;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.home-page__new-chat--secondary {
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
  color: var(--wp-text);

  &:hover:not(:disabled) {
    background: var(--wp-surface-3);
  }
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

.home-page__section-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wp-text);
}

.home-page__sessions {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.home-page__session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.home-page__session-item {
  margin: 0;
}

.home-page__session-link {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  cursor: pointer;
  text-align: left;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.home-page__session-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--wp-text);
}

.home-page__session-date {
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  white-space: nowrap;
}

.home-page__empty {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 1rem;
  padding: 1.5rem 0;
}

.home-page__empty-text {
  margin: 0;
  font-size: 0.9375rem;
  color: var(--wp-text-muted);
}

.home-page__profile-dialog {
  width: min(28rem, 92vw);
  padding: 1.75rem;
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
}

.home-page__profile-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 1.25rem;
  text-align: center;
}

.home-page__profile-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3.25rem;
  height: 3.25rem;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent-soft);
}

.home-page__profile-title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
}

.home-page__profile-lead {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.home-page__profile-fields {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.home-page__profile-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.home-page__profile-label {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.home-page__profile-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-base);
  transition: border-color var(--wp-dur) var(--wp-ease);

  &::placeholder {
    color: var(--wp-text-faint);
  }

  &:focus {
    outline: none;
    border-color: var(--wp-accent);
    box-shadow: 0 0 0 2px var(--wp-accent-soft);
  }
}

.home-page__profile-foot {
  margin-top: 1.25rem;
  display: flex;
  justify-content: flex-end;
}

.home-page__profile-submit {
  min-height: 2.5rem;
  padding: 0 1.1rem;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}
</style>
