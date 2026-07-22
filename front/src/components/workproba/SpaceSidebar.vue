<template>
  <nav class="wp-sidebar" :class="{ 'wp-sidebar--rail': rail }">
    <div v-if="!rail" class="wp-sidebar__inner">
      <!-- En-tête : Espaces -->
      <div class="wp-sidebar__topbar">
        <span class="wp-sidebar__brand">{{ t('shell.spaces') }}</span>
        <button
          type="button"
          class="wp-sidebar__icon-btn"
          :title="t('common.openSpaceEllipsis')"
          @click="onOpenSpace"
        >
          <Lucide name="layers" size="15" color="wp-text-muted" />
        </button>
      </div>

      <!-- Arbre espaces / sessions -->
      <div class="wp-sidebar__tree">
        <div v-if="recentWorkspaces.length === 0" class="wp-sidebar__empty">
          <p>{{ t('shell.noSpaces') }}</p>
          <button type="button" class="wp-sidebar__new-cta" @click="onOpenSpace">
            <Lucide name="plus" size="16" color="text-invert" />
            {{ t('common.openSpace') }}
          </button>
        </div>

        <section
          v-for="ws in recentWorkspaces"
          :key="ws.id"
          class="wp-space"
          :class="{ 'wp-space--active': ws.id === activeSpaceId }"
        >
          <div class="wp-space__row">
            <button
              type="button"
              class="wp-space__chevron"
              :title="isExpanded(ws.id) ? t('common.collapse') : t('common.expand')"
              :aria-expanded="isExpanded(ws.id)"
              :aria-controls="`wp-space-children-${ws.id}`"
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
              class="wp-space__label"
              :title="t('shell.spacePathHint', { path: ws.folderPath })"
              @click="onActivate(ws)"
            >
              <Lucide name="layers" size="16" color="wp-text-muted" />
              <span class="wp-space__name">{{ ws.title || basename(ws.folderPath) }}</span>
            </button>

            <button
              type="button"
              class="wp-space__action"
              :title="t('shell.editSpace')"
              @click.stop="openSettingsDialog(ws)"
            >
              <Lucide name="pencil" size="13" color="wp-text-muted" />
            </button>

            <button
              v-if="ws.id === activeSpaceId"
              type="button"
              class="wp-space__action"
              :title="t('common.newConversation')"
              @click.stop="onNewConversation"
            >
              <Lucide name="message-square-plus" size="14" color="wp-text-muted" />
            </button>
          </div>

          <div v-if="isExpanded(ws.id)" class="wp-space__children" :id="`wp-space-children-${ws.id}`">
            <div v-if="isLoading(ws.id)" class="wp-space__hint">{{ t('common.loading') }}</div>

            <div v-else-if="sessionsFor(ws.id).length === 0" class="wp-space__hint">
              <button
                v-if="ws.id === activeSpaceId"
                type="button"
                class="wp-space__inline-cta"
                @click="onNewConversation"
              >
                <Lucide name="plus" size="13" color="text-invert" />
                {{ t('common.newConversation') }}
              </button>
              <template v-else>{{ t('shell.noConversations') }}</template>
            </div>

            <div v-else class="wp-space__convos">
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
                class="wp-space__more"
                @click="toggleConvos(ws.id)"
              >
                {{ isConvosExpanded(ws.id) ? t('common.seeLess') : t('common.seeMore', { count: sessionsFor(ws.id).length - visibleSessions(ws.id).length }) }}
              </button>
            </div>
          </div>
        </section>
      </div>

      <SpaceSettingsDialog
        v-model="settingsDialogOpen"
        :workspace="settingsTarget"
        @saved="onSpaceSaved"
      />

      <!-- Pied : profil (bas gauche) + mémoire partagée + réglages -->
      <div class="wp-sidebar__footer">
        <button
          type="button"
          class="wp-sidebar__profile"
          :class="{
            'wp-sidebar__profile--guest': isGuestIdentity,
            'wp-sidebar__profile--disconnected': isDisconnectedIdentity,
          }"
          :title="isGuestIdentity || isDisconnectedIdentity ? t('shell.connectPrompt') : t('shell.editProfile')"
          @click="onProfileClick"
        >
          <span class="wp-sidebar__avatar">{{ sidebarInitials }}</span>
          <span class="wp-sidebar__profile-text">
            <span class="wp-sidebar__profile-name">{{ sidebarDisplayName }}</span>
            <span class="wp-sidebar__profile-org">{{ sidebarDisplayOrg }}</span>
          </span>
        </button>
        <button
          type="button"
          class="wp-sidebar__footer-btn"
          :title="t('memory.title')"
          :disabled="!activeDataDir"
          @click="onOpenMemory"
        >
          <Lucide name="brain" size="16" color="wp-violet" />
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

      <CloudLoginModal
        v-model="cloudLoginModalOpen"
        @open-invitation="onOpenCloudInvitation"
      />

      <EnrollCloudModal v-model="enrollCloudModalOpen" />

      <q-dialog v-model="memoryDialogOpen">
        <div class="wp-memory-dialog">
          <header class="wp-memory-dialog__head">
            <span class="wp-memory-dialog__title">{{ t('memory.title') }}</span>
            <button
              type="button"
              class="wp-memory-dialog__close"
              :aria-label="t('common.close')"
              @click="memoryDialogOpen = false"
            >
              <Lucide name="x" size="16" color="text-muted" />
            </button>
          </header>
          <MemoryPanel
            :key="memoryDialogKey"
            :workspace-data-dir="activeDataDir"
            :highlight-memory-id="memoryHighlightId"
          />
        </div>
      </q-dialog>
    </div>

    <!-- Mode rail replié -->
    <div v-else class="wp-sidebar__rail">
      <button class="wp-rail-btn" :title="t('shell.spacesTitle')" @click="$emit('expand')">
        <Lucide name="panel-left-open" size="18" color="wp-text-muted" />
      </button>
      <button
        class="wp-rail-btn"
        :title="t('common.openSpaceEllipsis')"
        @click="onOpenSpace"
      >
        <Lucide name="folder-plus" size="18" color="wp-text-muted" />
      </button>
      <button
        class="wp-rail-btn"
        :title="t('common.newConversation')"
        :disabled="!activeSpaceId"
        @click="onNewConversation"
      >
        <Lucide name="message-square-plus" size="18" color="wp-text-muted" />
      </button>
      <div class="wp-sidebar__rail-spacer" />
      <button
        class="wp-rail-btn"
        :title="t('memory.title')"
        :disabled="!activeDataDir"
        @click="onOpenMemory"
      >
        <Lucide name="brain" size="18" color="wp-violet" />
      </button>
      <button class="wp-rail-btn" :title="sidebarProfileTitle" @click="onProfileClick">
        <span class="wp-sidebar__avatar wp-sidebar__avatar--sm">{{ sidebarInitials }}</span>
      </button>
      <button class="wp-rail-btn" :title="t('shell.settingsModelsShort')" @click="onOpenSettings">
        <Lucide name="settings-2" size="18" color="wp-text-muted" />
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
import { useSpace } from '@composables/useSpace';
import { useUserProfile } from '@composables/useUserProfile';
import { useAppSettings } from '@composables/useAppSettings';
import { useCloud } from '@composables/useCloud';
import { listWorkspaces } from '@composables/useDesktop';
import type { WorkspaceInfo } from '@composables/useDesktop.types';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';
import { bumpSessions, useSessionSync } from '@composables/useSessionSync';
import { HOME_ROUTE } from '@router/meta';
import MemoryPanel from '@components/memory/MemoryPanel.vue';
import SpaceSettingsDialog from '@components/workproba/SpaceSettingsDialog.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import { useMemoryPanel } from '@composables/useMemoryPanel';

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
  activeSpaceId,
  activeDataDir,
  openSpace,
  switchSpace,
  initFromStoredPath,
} = useSpace();

const recentWorkspaces = ref<WorkspaceInfo[]>([]);
const expanded = reactive<Record<string, boolean>>({});
const expandedConvos = reactive<Record<string, boolean>>({});
const sessionsByWs = reactive<Record<string, LocalSession[]>>({});
const loadingByWs = reactive<Record<string, boolean>>({});

const PREVIEW_COUNT = 4;

const currentSessionId = computed(() => String(route.params.id ?? ''));

const { profile, initials, save: saveProfile } = useUserProfile();
const { onboardingDone } = useAppSettings();
const { status, isEnrolled, init: initCloud } = useCloud();

type SidebarIdentityMode = 'guest' | 'cloud' | 'local';

const sidebarIdentityMode = computed<SidebarIdentityMode>(() => {
  if (!onboardingDone.value) return 'guest';
  if (isEnrolled.value) return 'cloud';
  return 'local';
});

const isGuestIdentity = computed(() => sidebarIdentityMode.value === 'guest');
const isDisconnectedIdentity = computed(() => sidebarIdentityMode.value === 'local');

const sidebarDisplayName = computed(() => {
  switch (sidebarIdentityMode.value) {
    case 'guest':
      return t('shell.guestName');
    case 'cloud':
      return profile.value.name.trim() || t('shell.cloudAccount');
    default:
      return t('shell.localMode');
  }
});

const sidebarDisplayOrg = computed(() => {
  switch (sidebarIdentityMode.value) {
    case 'guest':
      return t('shell.guestOrg');
    case 'cloud':
      return status.value?.org_label?.trim()
        || status.value?.org_id?.trim()
        || '';
    default:
      return t('shell.connectPrompt');
  }
});

const sidebarInitials = computed(() => {
  if (isGuestIdentity.value) return '?';
  return initials.value;
});

const sidebarProfileTitle = computed(() =>
  isGuestIdentity.value ? t('shell.guestOrg') : t('common.profile'),
);

const cloudLoginModalOpen = ref(false);
const enrollCloudModalOpen = ref(false);

function onProfileClick(): void {
  if (isGuestIdentity.value || isDisconnectedIdentity.value) {
    cloudLoginModalOpen.value = true;
    return;
  }
  profileDialogOpen.value = true;
}

function onOpenCloudInvitation(): void {
  enrollCloudModalOpen.value = true;
}
const profileDialogOpen = ref(false);
const settingsDialogOpen = ref(false);
const settingsTarget = ref<WorkspaceInfo | null>(null);
const memoryDialogOpen = ref(false);
const memoryDialogKey = ref(0);
const memoryHighlightId = ref<string | null>(null);
const { panelRequest, clearMemoryPanelRequest } = useMemoryPanel();
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
  const ts = new Date(iso).getTime();
  const diff = Date.now() - ts;
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

const refreshInFlight = new Map<string, Promise<void>>();

async function refreshActiveSessions(): Promise<void> {
  const id = activeSpaceId.value;
  const path = activePath.value;
  if (!id || !path) return;

  const existing = refreshInFlight.get(id);
  if (existing) return existing;

  const promise = (async () => {
    loadingByWs[id] = true;
    try {
      sessionsByWs[id] = await listSessions(id, path);
    } catch {
      sessionsByWs[id] = [];
    } finally {
      loadingByWs[id] = false;
      refreshInFlight.delete(id);
    }
  })();

  refreshInFlight.set(id, promise);
  return promise;
}

function prependSession(wsId: string, session: LocalSession): void {
  const existing = sessionsByWs[wsId] ?? [];
  if (existing.some((s) => s.id === session.id)) return;
  sessionsByWs[wsId] = [session, ...existing];
}

async function toggleExpand(ws: WorkspaceInfo): Promise<void> {
  const next = !isExpanded(ws.id);
  expanded[ws.id] = next;
  if (next) await ensureSessionsLoaded(ws);
}

async function onActivate(ws: WorkspaceInfo): Promise<void> {
  if (ws.id === activeSpaceId.value) {
    expanded[ws.id] = true;
    return;
  }
  expanded[ws.id] = true;
  await switchSpace(ws.folderPath);
}

async function onOpenSpace(): Promise<void> {
  await openSpace();
  await refreshWorkspaces();
  const id = activeSpaceId.value;
  if (id) expanded[id] = true;
}

function openSettingsDialog(ws: WorkspaceInfo): void {
  settingsTarget.value = ws;
  settingsDialogOpen.value = true;
}

function onSpaceSaved(updated: WorkspaceInfo): void {
  const index = recentWorkspaces.value.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    recentWorkspaces.value[index] = updated;
  }
}

async function onNewConversation(): Promise<void> {
  if (!activeSpaceId.value || !activePath.value) {
    Notify.create({
      message: t('shell.conversationCreateFailed'),
      classes: 'bg-danger text-white',
    });
    return;
  }
  try {
    const session = await createSession(activeSpaceId.value, activePath.value);
    prependSession(activeSpaceId.value, session);
    bumpSessions();
    expanded[activeSpaceId.value] = true;
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
}

function onOpenSession(session: LocalSession): void {
  if (session.id === currentSessionId.value) return;
  if (session.workspaceId !== activeSpaceId.value) {
    void switchSpace(session.projectPath)
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

function onOpenMemory(): void {
  if (!activeDataDir.value) return;
  memoryDialogKey.value += 1;
  memoryDialogOpen.value = true;
}

watch(panelRequest, (request) => {
  if (!request) return;
  memoryHighlightId.value = request.memoryId ?? null;
  onOpenMemory();
  clearMemoryPanelRequest();
});

watch(memoryDialogOpen, (open) => {
  if (!open) memoryHighlightId.value = null;
});

watch(
  activeSpaceId,
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
  void import('@pages/chat/ChatPage.vue');
  void initCloud();
  await initFromStoredPath();
  await refreshWorkspaces();
  // Sans espace ouvert, seule la page chat est inaccessible ; réglages et accueil restent valides.
  if (!activeSpaceId.value && route.name === 'chat_session') {
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
  color: var(--wp-text-muted);
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-accent);
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
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-accent-strong);
  }
}

/* Noeud workspace */
.wp-space + .wp-space {
  margin-top: 2px;
}

.wp-space__row {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1);
  border-radius: var(--wp-r-sm);
}

.wp-space--active > .wp-space__row {
  background: var(--wp-selection-soft);
}

.wp-space__chevron {
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

.wp-space__label {
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

.wp-space__name {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wp-space--active .wp-space__name {
  color: var(--wp-text);
}

.wp-space__action {
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
  color: var(--wp-text-muted);
  opacity: 0;
  transition: opacity 120ms var(--wp-ease), background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:focus-visible {
    opacity: 1;
  }

  .wp-space__row:hover &,
  .wp-space--active & {
    opacity: 1;
  }

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-accent);
  }
}

/* Sessions imbriquées */
.wp-space__children {
  padding: var(--wp-space-1) 0 var(--wp-space-2) 24px;
}

.wp-space__hint {
  padding: var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.wp-space__inline-cta {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
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
  background: var(--wp-selection-soft);
  border-left-color: var(--wp-selection);

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
  background: var(--wp-selection);
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

.wp-space__more {
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

/* Pied : profil (bas gauche) + mémoire + réglages */
.wp-sidebar__footer {
  flex: none;
  display: flex;
  align-items: center;
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

  &--guest,
  &--disconnected {
    .wp-sidebar__profile-name,
    .wp-sidebar__profile-org {
      color: var(--wp-text-muted);
    }

    .wp-sidebar__profile-org {
      color: var(--wp-accent);
      font-weight: 600;
    }
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
  background: var(--wp-avatar-bg);
  color: var(--wp-avatar-text);
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

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }
  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
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

/* Dialogue mémoire */
.wp-memory-dialog {
  width: min(34rem, 92vw);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  box-shadow: var(--wp-shadow-2);
  overflow: hidden;
}

.wp-memory-dialog__head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--wp-space-3) var(--wp-space-4);
  border-bottom: 1px solid var(--wp-border);
}

.wp-memory-dialog__title {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-base);
  color: var(--wp-text);
}

.wp-memory-dialog__close {
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

.wp-memory-dialog :deep(.memory-panel) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
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
