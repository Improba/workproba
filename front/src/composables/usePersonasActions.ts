import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useProject } from '@composables/useProject';
import {
  usePersonasNavigation,
  type PersonasNavAction,
} from '@composables/usePersonasNavigation';
import { useMainChatContext } from '@composables/useMainChatContext';
import { useSideChat } from '@composables/useSideChat';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { usePersonas } from '@composables/usePersonas';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';
import { formatMainChatContext } from '@utils/mainChatContext';

interface RelaunchConfig {
  personaIds: string[];
  topic: string;
  rounds: number;
}

interface ResumePayload {
  discussionId: string;
  personaIds: string[];
  messages: import('@composables/usePersonas').DiscussionMessage[];
}

function pickBestSession(sessions: LocalSession[]): LocalSession | null {
  if (!sessions.length) return null;
  return [...sessions].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  )[0] ?? null;
}

/**
 * Actions personas (avis / réunion / discussion) mutualisées.
 * L'avis et la discussion ouvrent le panneau latéral directement ;
 * réunion et reprise passent par une session chat si besoin.
 */
export function usePersonasActions() {
  const router = useRouter();
  const route = useRoute();
  const { locale, t } = useI18n();
  const { activeWorkspaceId, activePath } = useProject();
  const { requestAction } = usePersonasNavigation();
  const { getFormattedContext } = useMainChatContext();
  const { openSideChat } = useSideChat();
  const { isPersonasPluginActive, getPluginDataDir } = usePlugins();
  const { refresh } = usePersonas();

  async function resolveConversationContext(): Promise<string> {
    const fromActiveChat = getFormattedContext(locale.value).trim();
    if (fromActiveChat) return fromActiveChat;

    const workspaceId = activeWorkspaceId.value;
    const projectPath = activePath.value;
    if (!workspaceId || !projectPath) return '';

    let sessions: LocalSession[];
    try {
      sessions = await listSessions(workspaceId, projectPath);
    } catch {
      return '';
    }

    const sorted = [...sessions].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );
    const withMessages = sorted.find((session) => (session.messages?.length ?? 0) > 0);
    const fallback = sorted[0];
    const source = withMessages ?? fallback;
    if (!source?.messages?.length) return '';

    return formatMainChatContext(source.messages, { locale: locale.value });
  }

  async function ensurePersonasReady(): Promise<boolean> {
    if (!isPersonasPluginActive.value) {
      Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
      return false;
    }
    try {
      const dir = await getPluginDataDir(PERSONAS_PLUGIN_ID);
      if (dir) await refresh(dir);
      return true;
    } catch {
      Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
      return false;
    }
  }

  async function openPersonasSideChat(
    mode: 'avis' | 'discussion',
    personaIds?: string[],
    opts?: { resume?: ResumePayload; autoAsk?: boolean },
  ): Promise<void> {
    const ready = await ensurePersonasReady();
    if (!ready) return;

    const ids = personaIds ?? [];
    const conversationContext = await resolveConversationContext();
    const autoAsk = opts?.autoAsk ?? (!opts?.resume && ids.length > 0);

    openSideChat(PERSONAS_PLUGIN_ID, {
      mode,
      personaIds: ids,
      conversationContext,
      autoAsk,
      resume: opts?.resume,
    });
  }

  async function ensureChatSession(): Promise<boolean> {
    if (route.name === 'chat_session') return true;
    const workspaceId = activeWorkspaceId.value;
    const projectPath = activePath.value;
    if (!workspaceId || !projectPath) {
      Notify.create({ message: t('errors.noSpaceOpen'), color: 'negative' });
      return false;
    }

    let sessions: LocalSession[];
    try {
      sessions = await listSessions(workspaceId, projectPath);
    } catch {
      sessions = [];
    }

    let target = pickBestSession(sessions);
    if (!target) {
      try {
        target = await createSession(workspaceId, projectPath);
      } catch {
        target = null;
      }
    }
    if (!target) {
      Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
      return false;
    }

    await router.push({ name: 'chat_session', params: { id: target.id } });
    return true;
  }

  async function runAction(
    action: PersonasNavAction,
    opts?: { personaIds?: string[] },
  ): Promise<void> {
    const ready = await ensureChatSession();
    if (!ready) return;
    requestAction(action, opts);
  }

  async function askOpinion(personaIds?: string[]): Promise<void> {
    await openPersonasSideChat('avis', personaIds);
  }

  function startMeeting(): Promise<void> {
    return runAction('meeting');
  }

  async function discuss(personaIds?: string[]): Promise<void> {
    await openPersonasSideChat('discussion', personaIds);
  }

  async function relaunchMeeting(config: RelaunchConfig): Promise<void> {
    const ready = await ensureChatSession();
    if (!ready) return;
    sessionStorage.setItem(
      'workproba.personas.relaunchMeeting',
      JSON.stringify(config),
    );
    requestAction('meeting');
  }

  async function resumeDiscussion(payload: ResumePayload): Promise<void> {
    await openPersonasSideChat('discussion', payload.personaIds, { resume: payload });
  }

  return {
    askOpinion,
    startMeeting,
    discuss,
    relaunchMeeting,
    resumeDiscussion,
  };
}
