<template>
  <nav class="wp-sidebar" :class="{ 'wp-sidebar--rail': rail }">
    <div v-if="!rail" class="wp-sidebar__inner">
      <!-- Onglets sidebar : espaces / mémoire -->
      <div class="wp-sidebar__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          class="wp-sidebar__tab"
          :class="{ 'wp-sidebar__tab--active': sidebarTab === 'spaces' }"
          :aria-selected="sidebarTab === 'spaces'"
          @click="sidebarTab = 'spaces'"
        >
          {{ t('shell.spaces') }}
        </button>
        <button
          type="button"
          role="tab"
          class="wp-sidebar__tab wp-sidebar__tab--memory"
          :class="{ 'wp-sidebar__tab--active': sidebarTab === 'memory' }"
          :aria-selected="sidebarTab === 'memory'"
          @click="onMemoryTab"
        >
          {{ t('memory.title') }}
        </button>
        <button
          v-if="isPersonasPluginActive"
          type="button"
          role="tab"
          class="wp-sidebar__tab wp-sidebar__tab--personas"
          :class="{ 'wp-sidebar__tab--active': sidebarTab === 'personas' }"
          :aria-selected="sidebarTab === 'personas'"
          @click="onPersonasTab"
        >
          {{ t('personas.panel.title') }}
        </button>
      </div>

      <!-- En-tête : Workspaces + ouvrir un dossier -->
      <div v-if="sidebarTab === 'spaces'" class="wp-sidebar__topbar">
        <span class="wp-sidebar__brand">{{ t('shell.spaces') }}</span>
        <button
          type="button"
          class="wp-sidebar__icon-btn"
          :title="t('common.openFolderEllipsis')"
          @click="onOpenFolder"
        >
          <Lucide name="folder-plus" size="15" color="accent" />
        </button>
      </div>

      <!-- Arbre workspaces / conversations -->
      <div v-if="sidebarTab === 'spaces'" class="wp-sidebar__tree">
        <div v-if="recentWorkspaces.length === 0" class="wp-sidebar__empty">
          <p>{{ t('shell.noSpaces') }}</p>
          <button type="button" class="wp-sidebar__new-cta" @click="onOpenFolder">
            <Lucide name="plus" size="16" color="wp-canard" />
            {{ t('common.openFolder') }}
          </button>
        </div>

        <section
          v-for="ws in recentWorkspaces"
          :key="ws.id"
          class="wp-ws"
          :class="{ 'wp-ws--active': ws.id === activeWorkspaceId }"
        >
          <div class="wp-ws__row">
            <button
              type="button"
              class="wp-ws__chevron"
              :title="isExpanded(ws.id) ? t('common.collapse') : t('common.expand')"
              :aria-expanded="isExpanded(ws.id)"
              :aria-controls="`wp-ws-children-${ws.id}`"
              @click="toggleExpand(ws)"
            >
              <Lucide
                :name="isExpanded(ws.id) ? 'chevron-down' : 'chevron-right'"
                size="14"
                color="text-faint"
              />
            </button>

            <button
              type="button"
              class="wp-ws__label"
              :title="ws.folderPath"
              @click="onActivate(ws)"
            >
              <Lucide name="folder" size="16" color="accent" />
              <span class="wp-ws__name">{{ ws.title || basename(ws.folderPath) }}</span>
            </button>

            <button
              v-if="ws.id === activeWorkspaceId"
              type="button"
              class="wp-ws__new"
              :title="t('common.newConversation')"
              @click.stop="onNewConversation"
            >
              <Lucide name="message-square-plus" size="14" color="text" />
            </button>
          </div>

          <div v-if="isExpanded(ws.id)" class="wp-ws__children" :id="`wp-ws-children-${ws.id}`">
            <div v-if="isLoading(ws.id)" class="wp-ws__hint">{{ t('common.loading') }}</div>

            <div v-else-if="sessionsFor(ws.id).length === 0" class="wp-ws__hint">
              <button
                v-if="ws.id === activeWorkspaceId"
                type="button"
                class="wp-ws__inline-cta"
                @click="onNewConversation"
              >
                <Lucide name="plus" size="13" color="wp-canard" />
                {{ t('common.newConversation') }}
              </button>
              <template v-else>{{ t('shell.noConversations') }}</template>
            </div>

            <div v-else class="wp-ws__convos">
              <button
                v-for="session in visibleSessions(ws.id)"
                :key="session.id"
                type="button"
                class="wp-convo"
                :class="{ 'wp-convo--active': session.id === currentSessionId }"
                @click="onOpenSession(session)"
              >
                <span
                  class="wp-convo__dot"
                  :class="`wp-convo__dot--${convoStatus(session)}`"
                  :title="convoStatusLabel(session)"
                />
                <span class="wp-convo__title">{{ session.title || t('common.noTitle') }}</span>
                <span class="wp-convo__date">{{ formatRelative(session.updatedAt) }}</span>
              </button>
              <button
                v-if="sessionsFor(ws.id).length > PREVIEW_COUNT"
                type="button"
                class="wp-ws__more"
                @click="toggleConvos(ws.id)"
              >
                {{ isConvosExpanded(ws.id) ? t('common.seeLess') : t('common.seeMore', { count: sessionsFor(ws.id).length - visibleSessions(ws.id).length }) }}
              </button>
            </div>
          </div>
        </section>
      </div>

      <MemoryPanel
        v-else-if="sidebarTab === 'memory'"
        :memories="memories"
        :search-results="searchResults"
        :loading="memoryLoading"
        :searching="memorySearching"
        :load-error="memoryLoadError"
        @refresh="refreshMemoryPanel"
        @search="onMemorySearch"
        @forget="onMemoryForget"
        @forget-all="onMemoryForgetAll"
      />

      <PersonasCentralPanel
        v-else-if="sidebarTab === 'personas'"
        :plugin-active="isPersonasPluginActive"
        :plugin-data-dir="personasDataDir"
        @ask-opinion="onPersonasAsk"
        @meeting="onPersonasMeeting"
        @discuss="onPersonasDiscuss"
        @view-meeting="onPersonasViewMeeting"
        @relaunch-meeting="onPersonasRelaunchMeeting"
        @resume-discussion="onPersonasResumeDiscussion"
      />

      <!-- Pied : profil (bas gauche) + réglages -->
      <div class="wp-sidebar__footer">
        <button
          type="button"
          class="wp-sidebar__profile"
          :title="t('shell.editProfile')"
          @click="profileDialogOpen = true"
        >
          <span class="wp-sidebar__avatar">{{ initials }}</span>
          <span class="wp-sidebar__profile-text">
            <span class="wp-sidebar__profile-name">{{ profile.name }}</span>
            <span class="wp-sidebar__profile-org">{{ profile.organisation }}</span>
          </span>
        </button>
        <button
          type="button"
          class="wp-sidebar__footer-btn"
          :title="t('shell.settingsModels')"
          @click="onOpenSettings"
        >
          <Lucide name="settings-2" size="16" color="text-muted" />
        </button>
      </div>

      <q-dialog v-model="profileDialogOpen">
        <div class="wp-profile-dialog">
          <header class="wp-profile-dialog__head">
            <span class="wp-profile-dialog__title">{{ t('common.profile') }}</span>
            <button
              type="button"
              class="wp-profile-dialog__close"
              :aria-label="t('common.close')"
              @click="profileDialogOpen = false"
            >
              <Lucide name="x" size="16" color="text-muted" />
            </button>
          </header>
          <div class="wp-profile-dialog__field">
            <label for="wp-profile-name">{{ t('common.name') }}</label>
            <input id="wp-profile-name" v-model="profileNameDraft" type="text" />
          </div>
          <div class="wp-profile-dialog__field">
            <label for="wp-profile-org">{{ t('common.organisation') }}</label>
            <input id="wp-profile-org" v-model="profileOrgDraft" type="text" />
          </div>
          <footer class="wp-profile-dialog__foot">
            <button type="button" class="wp-profile-dialog__btn" @click="profileDialogOpen = false">
              {{ t('common.cancel') }}
            </button>
            <button type="button" class="wp-profile-dialog__btn wp-profile-dialog__btn--primary" @click="onSaveProfile">
              {{ t('common.save') }}
            </button>
          </footer>
        </div>
      </q-dialog>
    </div>

    <!-- Mode rail replié -->
    <div v-else class="wp-sidebar__rail">
      <button class="wp-rail-btn" :title="t('shell.spacesTitle')" @click="$emit('expand')">
        <Lucide name="folder" size="18" color="accent" />
      </button>
      <button
        class="wp-rail-btn"
        :title="t('common.openFolderEllipsis')"
        @click="onOpenFolder"
      >
        <Lucide name="folder-plus" size="18" color="accent" />
      </button>
      <button
        class="wp-rail-btn"
        :title="t('common.newConversation')"
        :disabled="!activeWorkspaceId"
        @click="onNewConversation"
      >
        <Lucide name="message-square-plus" size="18" color="text" />
      </button>
      <div class="wp-sidebar__rail-spacer" />
      <button class="wp-rail-btn" :title="t('common.profile')" @click="profileDialogOpen = true">
        <span class="wp-sidebar__avatar wp-sidebar__avatar--sm">{{ initials }}</span>
      </button>
      <button class="wp-rail-btn" :title="t('shell.settingsModelsShort')" @click="onOpenSettings">
        <Lucide name="settings-2" size="18" color="text" />
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useProject } from '@composables/useProject';
import { useUserProfile } from '@composables/useUserProfile';
import { listWorkspaces } from '@composables/useDesktop';
import type { WorkspaceInfo } from '@composables/useDesktop.types';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';
import { useSessionSync } from '@composables/useSessionSync';
import { HOME_ROUTE } from '@router/meta';
import MemoryPanel from '@components/memory/MemoryPanel.vue';
import PersonasCentralPanel from '@components/personas/PersonasCentralPanel.vue';
import { useMemory } from '@composables/useMemory';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { usePersonasNavigation } from '@composables/usePersonasNavigation';
import type { DiscussionMessage } from '@composables/usePersonas';

const props = defineProps<{
  rail?: boolean;
  streaming?: boolean;
}>();

defineEmits<{
  (e: 'expand'): void;
}>();

const router = useRouter();
const route = useRoute();
const { t, locale } = useI18n();

const {
  activePath,
  activeWorkspaceId,
  activeDataDir,
  openFolder,
  switchWorkspace,
  initFromStoredPath,
} = useProject();

const recentWorkspaces = ref<WorkspaceInfo[]>([]);
const expanded = reactive<Record<string, boolean>>({});
const expandedConvos = reactive<Record<string, boolean>>({});
const sessionsByWs = reactive<Record<string, LocalSession[]>>({});
const loadingByWs = reactive<Record<string, boolean>>({});

const PREVIEW_COUNT = 4;

const sidebarTab = ref<'spaces' | 'memory' | 'personas'>('spaces');

const { isPersonasPluginActive, getPluginDataDir } = usePlugins();
const { requestAction } = usePersonasNavigation();
const personasDataDir = ref<string | null>(null);

const {
  memories,
  searchResults,
  loading: memoryLoading,
  searching: memorySearching,
  loadError: memoryLoadError,
  refresh: refreshMemory,
  searchMemory: searchMemoryQuery,
  forgetMemory,
  forgetAll: forgetAllMemory,
} = useMemory();

const currentSessionId = computed(() => String(route.params.id ?? ''));

const { profile, initials, save: saveProfile } = useUserProfile();
const profileDialogOpen = ref(false);
const profileNameDraft = ref(profile.value.name);
const profileOrgDraft = ref(profile.value.organisation);

watch(profileDialogOpen, (open) => {
  if (open) {
    profileNameDraft.value = profile.value.name;
    profileOrgDraft.value = profile.value.organisation;
  }
});

function onSaveProfile(): void {
  saveProfile({ name: profileNameDraft.value, organisation: profileOrgDraft.value });
  profileDialogOpen.value = false;
  Notify.create({ message: t('common.profileSaved'), color: 'dark', timeout: 1500 });
}

function basename(path: string): string {
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

function isExpanded(id: string): boolean {
  return expanded[id] === true;
}

function isLoading(id: string): boolean {
  return loadingByWs[id] === true;
}

function sessionsFor(id: string): LocalSession[] {
  return sessionsByWs[id] ?? [];
}

function sortedSessions(id: string): LocalSession[] {
  return [...sessionsFor(id)].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
}

function isConvosExpanded(id: string): boolean {
  return expandedConvos[id] === true;
}

function toggleConvos(id: string): void {
  expandedConvos[id] = !isConvosExpanded(id);
}

function visibleSessions(id: string): LocalSession[] {
  const sorted = sortedSessions(id);
  if (isConvosExpanded(id)) return sorted;
  const preview = sorted.slice(0, PREVIEW_COUNT);
  const activeId = currentSessionId.value;
  if (!activeId || preview.some((s) => s.id === activeId)) return preview;
  // Garantit que la conversation active reste visible même hors fenêtre.
  const visibleIds = new Set(preview.map((s) => s.id));
  visibleIds.add(activeId);
  return sorted.filter((s) => visibleIds.has(s.id));
}

type ConvoStatus = 'streaming' | 'active' | 'idle';

function convoStatus(session: LocalSession): ConvoStatus {
  if (session.id === currentSessionId.value && props.streaming) return 'streaming';
  if (session.id === currentSessionId.value) return 'active';
  return 'idle';
}

function convoStatusLabel(session: LocalSession): string {
  const status = convoStatus(session);
  if (status === 'streaming') return t('shell.conversationStreaming');
  if (status === 'active') return t('shell.conversationActive');
  return t('shell.conversationIdle');
}

function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  if (diff < 60000) return t('common.justNow');
  if (diff < 3600000) return t('common.minutesAgo', { count: Math.floor(diff / 60000) });
  if (diff < 86400000) return t('common.hoursAgo', { count: Math.floor(diff / 3600000) });
  return new Date(iso).toLocaleDateString(locale.value, { day: '2-digit', month: 'short' });
}

async function refreshWorkspaces(): Promise<void> {
  try {
    recentWorkspaces.value = await listWorkspaces();
  } catch {
    recentWorkspaces.value = [];
  }
}

async function ensureSessionsLoaded(ws: WorkspaceInfo): Promise<void> {
  if (loadingByWs[ws.id] || ws.id in sessionsByWs) return;
  loadingByWs[ws.id] = true;
  try {
    sessionsByWs[ws.id] = await listSessions(ws.id, ws.folderPath);
  } catch {
    sessionsByWs[ws.id] = [];
  } finally {
    loadingByWs[ws.id] = false;
  }
}

async function refreshActiveSessions(): Promise<void> {
  const id = activeWorkspaceId.value;
  const path = activePath.value;
  if (!id || !path) return;
  if (loadingByWs[id]) return;
  loadingByWs[id] = true;
  try {
    sessionsByWs[id] = await listSessions(id, path);
  } catch {
    sessionsByWs[id] = [];
  } finally {
    loadingByWs[id] = false;
  }
}

async function toggleExpand(ws: WorkspaceInfo): Promise<void> {
  const next = !isExpanded(ws.id);
  expanded[ws.id] = next;
  if (next) await ensureSessionsLoaded(ws);
}

async function onActivate(ws: WorkspaceInfo): Promise<void> {
  if (ws.id === activeWorkspaceId.value) {
    expanded[ws.id] = true;
    return;
  }
  expanded[ws.id] = true;
  await switchWorkspace(ws.folderPath);
}

async function onOpenFolder(): Promise<void> {
  await openFolder();
  await refreshWorkspaces();
  const id = activeWorkspaceId.value;
  if (id) expanded[id] = true;
}

async function onNewConversation(): Promise<void> {
  if (!activeWorkspaceId.value || !activePath.value) return;
  try {
    const session = await createSession(activeWorkspaceId.value, activePath.value);
    await refreshActiveSessions();
    expanded[activeWorkspaceId.value] = true;
    void router.push({ name: 'chat_session', params: { id: session.id } });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('shell.conversationCreateFailed'),
      classes: 'bg-danger text-white',
    });
  }
}

function onOpenSession(session: LocalSession): void {
  if (session.id === currentSessionId.value) return;
  if (session.workspaceId !== activeWorkspaceId.value) {
    void switchWorkspace(session.projectPath)
      .then(() => router.push({ name: 'chat_session', params: { id: session.id } }))
      .catch(() =>
        Notify.create({
          message: t('shell.conversationOpenFailed'),
          classes: 'bg-danger text-white',
        }),
      );
    return;
  }
  void router.push({ name: 'chat_session', params: { id: session.id } });
}

function onOpenSettings(): void {
  void router.push({ name: 'settings_models' });
}

function onMemoryTab(): void {
  sidebarTab.value = 'memory';
  void refreshMemoryPanel();
}

async function ensurePersonasDataDir(): Promise<void> {
  if (personasDataDir.value) return;
  try {
    personasDataDir.value = await getPluginDataDir(PERSONAS_PLUGIN_ID);
  } catch {
    personasDataDir.value = null;
  }
}

function onPersonasTab(): void {
  sidebarTab.value = 'personas';
  void ensurePersonasDataDir();
}

function navigateToChatForPersonas(): void {
  if (route.name !== 'chat_session' && activeWorkspaceId.value) {
    const sessions = sessionsFor(activeWorkspaceId.value);
    const target = sessions[0];
    if (target) {
      void router.push({ name: 'chat_session', params: { id: target.id } });
    }
  }
}

function onPersonasAsk(): void {
  navigateToChatForPersonas();
  requestAction('opinion');
}

function onPersonasMeeting(): void {
  navigateToChatForPersonas();
  requestAction('meeting');
}

function onPersonasViewMeeting(meeting: {
  persona_ids: string[];
  topic: string;
  rounds?: number;
}): void {
  onPersonasRelaunchMeeting({
    personaIds: meeting.persona_ids,
    topic: meeting.topic,
    rounds: meeting.rounds ?? 3,
  });
}

function onPersonasRelaunchMeeting(config: {
  personaIds: string[];
  topic: string;
  rounds: number;
}): void {
  navigateToChatForPersonas();
  sessionStorage.setItem('workproba.personas.relaunchMeeting', JSON.stringify(config));
  requestAction('meeting');
}

function onPersonasDiscuss(): void {
  navigateToChatForPersonas();
  requestAction('discuss');
}

function onPersonasResumeDiscussion(payload: {
  discussionId: string;
  personaIds: string[];
  messages: DiscussionMessage[];
}): void {
  navigateToChatForPersonas();
  requestAction('discuss');
  sessionStorage.setItem(
    'workproba.personas.resume',
    JSON.stringify(payload),
  );
}

async function refreshMemoryPanel(): Promise<void> {
  if (!activeDataDir.value) return;
  await refreshMemory(activeDataDir.value);
}

async function onMemorySearch(query: string): Promise<void> {
  if (!activeDataDir.value) return;
  await searchMemoryQuery(activeDataDir.value, query);
}

async function onMemoryForget(id: string): Promise<void> {
  if (!activeDataDir.value) return;
  await forgetMemory(activeDataDir.value, id);
}

async function onMemoryForgetAll(): Promise<void> {
  if (!activeDataDir.value) return;
  const ok = await forgetAllMemory(activeDataDir.value, 'all');
  Notify.create({
    message: ok ? t('memory.forgetAllDone') : t('memory.loadFailed'),
    color: ok ? 'positive' : 'negative',
    timeout: 2500,
  });
}

watch(
  activeWorkspaceId,
  (id) => {
    if (!id) return;
    expanded[id] = true;
    void refreshActiveSessions();
  },
  { immediate: true },
);

watch(
  () => props.streaming,
  () => {
    if (!props.streaming) void refreshActiveSessions();
  },
);

const { sessionVersion } = useSessionSync();
watch(sessionVersion, () => {
  void refreshActiveSessions();
});

onMounted(async () => {
  await initFromStoredPath();
  await refreshWorkspaces();
  if (!activeWorkspaceId.value) {
    void router.push({ name: HOME_ROUTE });
  }
});
</script>

<style scoped lang="scss">
.wp-sidebar {
  flex: none;
  width: 268px;
  min-width: 240px;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  border-right: 1px solid var(--wp-border);
  transition: width var(--wp-dur) var(--wp-ease);
}

.wp-sidebar--rail {
  width: 56px;
  min-width: 56px;
  max-width: 56px;
}

.wp-sidebar__inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 268px;
}

.wp-sidebar__tabs {
  flex: none;
  display: flex;
  gap: 2px;
  padding: var(--wp-space-2) var(--wp-space-2) 0;
}

.wp-sidebar__tab {
  flex: 1;
  padding: var(--wp-space-2) var(--wp-space-2);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--wp-text-faint);
  cursor: pointer;
  transition: color var(--wp-dur) var(--wp-ease), border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    color: var(--wp-text);
  }

  &--active {
    color: var(--wp-text);
    border-bottom-color: var(--wp-accent);
  }

  &--memory.wp-sidebar__tab--active {
    color: var(--wp-violet);
    border-bottom-color: var(--wp-violet);
  }

  &--personas.wp-sidebar__tab--active {
    color: var(--wp-gold);
    border-bottom-color: var(--wp-gold);
  }
}

.wp-sidebar__topbar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--wp-space-3) var(--wp-space-3) var(--wp-space-2);
}

.wp-sidebar__brand {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-text-faint);
}

.wp-sidebar__icon-btn {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  transition: background 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-sidebar__tree {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--wp-space-2) var(--wp-space-2);
}

.wp-sidebar__empty {
  padding: var(--wp-space-4) var(--wp-space-2);
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
  text-align: center;

  p {
    margin: 0 0 var(--wp-space-3);
  }
}

.wp-sidebar__new-cta {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-accent-strong);
  }
}

/* Noeud workspace */
.wp-ws + .wp-ws {
  margin-top: 2px;
}

.wp-ws__row {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1);
  border-radius: var(--wp-r-sm);
}

.wp-ws--active > .wp-ws__row {
  background: var(--wp-accent-soft);
}

.wp-ws__chevron {
  flex: none;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  color: var(--wp-text-faint);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-ws__label {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-1);
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  border-radius: var(--wp-r-sm);
}

.wp-ws__name {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-ws--active .wp-ws__name {
  color: var(--wp-text);
}

.wp-ws__new {
  flex: none;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms var(--wp-ease), background 120ms var(--wp-ease);

  .wp-ws__row:hover &,
  .wp-ws--active & {
    opacity: 1;
  }

  &:hover {
    background: var(--wp-surface-2);
  }
}

/* Conversations imbriquées */
.wp-ws__children {
  padding: var(--wp-space-1) 0 var(--wp-space-2) 24px;
}

.wp-ws__hint {
  padding: var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.wp-ws__inline-cta {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-accent-strong);
  }
}

.wp-convo {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-left: 3px solid transparent;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-convo--active {
  background: var(--wp-accent-soft);
  border-left-color: var(--wp-accent);

  .wp-convo__title {
    color: var(--wp-text);
  }
}

.wp-convo__dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);
  opacity: 0.45;
}

.wp-convo__dot--active {
  background: var(--wp-accent);
  opacity: 1;
}

.wp-convo__dot--streaming {
  background: var(--wp-accent);
  opacity: 1;
  animation: wp-breathe 1.4s ease-in-out infinite;
}

.wp-convo__title {
  flex: 1;
  min-width: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 500;
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-convo__date {
  flex: none;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.wp-ws__more {
  display: inline-flex;
  align-items: center;
  padding: var(--wp-space-1) var(--wp-space-3) var(--wp-space-1)
    calc(var(--wp-space-3) + 13px);
  border: none;
  background: transparent;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--wp-r-sm);
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }
}

/* Pied : profil (bas gauche) + réglages */
.wp-sidebar__footer {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
}

.wp-sidebar__profile {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-1);
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-sidebar__avatar {
  flex: none;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-pill);
  background: #b5654a;
  color: #fff;
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  line-height: 1;

  &--sm {
    width: 22px;
    height: 22px;
    font-size: var(--wp-fs-xs);
  }
}

.wp-sidebar__profile-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: var(--wp-lh-tight);
}

.wp-sidebar__profile-name {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-sidebar__profile-org {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-sidebar__footer-btn {
  flex: none;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;
  color: var(--wp-text-muted);
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }
}

/* Dialogue profil */
.wp-profile-dialog {
  width: 340px;
  max-width: 90vw;
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  padding: var(--wp-space-4);
}

.wp-profile-dialog__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--wp-space-3);
}

.wp-profile-dialog__title {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-base);
  color: var(--wp-text);
}

.wp-profile-dialog__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-sm);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.wp-profile-dialog__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  margin-bottom: var(--wp-space-3);

  label {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-faint);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  input {
    padding: var(--wp-space-2) var(--wp-space-3);
    border: 1px solid var(--wp-border);
    border-radius: var(--wp-r-sm);
    background: var(--wp-surface-2);
    font-size: var(--wp-fs-sm);
    color: var(--wp-text);
    font-family: var(--wp-font-ui);

    &:focus {
      outline: none;
      border-color: var(--wp-accent);
    }
  }
}

.wp-profile-dialog__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.wp-profile-dialog__btn {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  font-family: var(--wp-font-ui);

  &:hover {
    background: var(--wp-surface-2);
  }

  &--primary {
    background: var(--wp-accent);
    color: var(--wp-canard);
    border-color: var(--wp-accent);

    &:hover {
      background: var(--wp-accent-strong);
    }
  }
}

/* Rail replié */
.wp-sidebar__rail {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3) 0;
}

.wp-sidebar__rail-spacer {
  flex: 1;
}

.wp-rail-btn {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: var(--wp-r-md);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}
</style>
