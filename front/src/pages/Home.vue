<template>
  <div class="home-page">
    <section
      v-if="showFirstLaunchOnboarding"
      class="home-page__onboarding home-page__onboarding--guided"
    >
      <h1 class="home-page__welcome">
        Bienvenue sur Workproba, votre assistant de bureau local.
      </h1>

      <ol class="home-page__steps">
        <li class="home-page__step">
          <span class="home-page__step-badge">1</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="folder-open" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">Ouvrez un dossier de documents</p>
            <p class="home-page__step-text">
              Choisissez le dossier sur lequel l'assistant pourra travailler.
            </p>
            <OpenFolderButton :loading="loading" @click="openFolder" />
          </div>
        </li>

        <li class="home-page__step">
          <span class="home-page__step-badge">2</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="messages-square" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">Discutez avec l'assistant</p>
            <p class="home-page__step-text">
              Posez vos questions en langage courant, comme à un collègue.
            </p>
          </div>
        </li>

        <li class="home-page__step">
          <span class="home-page__step-badge">3</span>
          <span class="home-page__step-icon" aria-hidden="true">
            <Lucide name="file-plus" size="22" color="wp-accent" />
          </span>
          <div class="home-page__step-body">
            <p class="home-page__step-title">Il crée vos fichiers localement</p>
            <p class="home-page__step-text">
              Tableaux, courriers, synthèses : tout reste dans votre dossier.
            </p>
          </div>
        </li>
      </ol>

      <button
        type="button"
        class="home-page__skip"
        @click="skipOnboarding"
      >
        Vous êtes à l'aise avec l'IA ? Passer le tutoriel
      </button>

      <p v-if="error" class="home-page__error">{{ error }}</p>
    </section>

    <section v-else-if="!activePath && sessionsChecked" class="home-page__onboarding">
      <h1 class="home-page__title">Bienvenue sur Workproba</h1>
      <p class="home-page__lead">
        Ouvrez un dossier projet pour commencer à travailler avec l'agent IA
        sur vos documents locaux.
      </p>
      <OpenFolderButton :loading="loading" @click="openFolder" />
      <p v-if="error" class="home-page__error">{{ error }}</p>
    </section>

    <section v-else class="home-page__workspace">
      <header class="home-page__header">
        <div class="home-page__header-text">
          <h1 class="home-page__title">Projet</h1>
          <p class="home-page__path" :title="activePath ?? undefined">{{ activePath }}</p>
        </div>
        <div class="home-page__actions">
          <OpenFolderButton
            :loading="loading"
            label="Changer de dossier"
            @click="openFolder"
          />
          <button
            type="button"
            class="home-page__new-chat"
            :disabled="loading"
            @click="startNewConversation"
          >
            <Lucide name="message-square-plus" size="sm" color="wp-canard" />
            Nouvelle conversation
          </button>
        </div>
      </header>

      <p v-if="error" class="home-page__error">{{ error }}</p>

      <section v-if="recentSessions.length" class="home-page__sessions">
        <h2 class="home-page__section-title">Conversations récentes</h2>
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
          Aucune conversation pour l'instant. Choisissez un point de départ :
        </p>
        <StartPrompts @select="startConversationWithPrompt" />
        <button
          type="button"
          class="home-page__new-chat home-page__new-chat--secondary"
          :disabled="loading"
          @click="startNewConversation"
        >
          <Lucide name="message-square-plus" size="sm" color="wp-canard" />
          Ou démarrer une conversation vide
        </button>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import OpenFolderButton from '@components/workspace/OpenFolderButton.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { listWorkspaces } from '@composables/useDesktop';
import { useProject } from '@composables/useProject';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';

const router = useRouter();

const {
  activePath,
  activeWorkspaceId,
  loading,
  error,
  openFolder,
} = useProject();

const { onboardingDone, loaded: settingsLoaded, setOnboardingDone } = useAppSettings();

const recentSessions = ref<LocalSession[]>([]);
const hasAnySessions = ref(false);
const sessionsChecked = ref(false);

const showFirstLaunchOnboarding = computed(
  () =>
    settingsLoaded.value
    && sessionsChecked.value
    && !activePath.value
    && !hasAnySessions.value
    && !onboardingDone.value,
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
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function startNewConversation(): void {
  if (!activePath.value || !activeWorkspaceId.value) return;
  void (async () => {
    const session = await createSession(
      activeWorkspaceId.value!,
      activePath.value!,
    );
    void router.push({ name: 'chat_session', params: { id: session.id } });
  })();
}

function startConversationWithPrompt(prompt: string): void {
  if (!activePath.value || !activeWorkspaceId.value) return;
  void (async () => {
    const session = await createSession(
      activeWorkspaceId.value!,
      activePath.value!,
    );
    void router.push({
      name: 'chat_session',
      params: { id: session.id },
      state: { initialPrompt: prompt },
    });
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
</style>
