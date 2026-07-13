import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useProject } from '@composables/useProject';
import {
  usePersonasNavigation,
  type PersonasNavAction,
} from '@composables/usePersonasNavigation';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';

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

/**
 * Actions personas (avis / réunion / discussion) mutualisées.
 * Bascule sur une session de chat si besoin, puis émet l'action via usePersonasNavigation.
 */
export function usePersonasActions() {
  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const { activeWorkspaceId, activePath } = useProject();
  const { requestAction } = usePersonasNavigation();

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

    let target: LocalSession | null = sessions[0] ?? null;
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

  function askOpinion(personaIds?: string[]): Promise<void> {
    return runAction(
      'opinion',
      personaIds?.length ? { personaIds } : undefined,
    );
  }

  function startMeeting(): Promise<void> {
    return runAction('meeting');
  }

  function discuss(personaIds?: string[]): Promise<void> {
    return runAction(
      'discuss',
      personaIds?.length ? { personaIds } : undefined,
    );
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
    const ready = await ensureChatSession();
    if (!ready) return;
    requestAction('discuss', {
      personaIds: payload.personaIds.length ? [...payload.personaIds] : undefined,
      resume: payload,
    });
  }

  return {
    askOpinion,
    startMeeting,
    discuss,
    relaunchMeeting,
    resumeDiscussion,
  };
}
