import { useRoute, useRouter } from 'vue-router';
import { useProject } from '@composables/useProject';
import { usePersonasNavigation, type PersonasNavAction } from '@composables/usePersonasNavigation';
import { createSession, listSessions, type LocalSession } from '@services/workspaceSession';

interface MeetingSummary {
  persona_ids: string[];
  topic: string;
  rounds?: number;
}

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
 * Garde le même flot qu'avant le déplacement du panneau personas vers la droite :
 * on bascule sur une session de chat (existante ou créée), puis on émet l'action
 * via usePersonasNavigation pour que ChatPage l'applique au montage.
 */
export function usePersonasActions() {
  const router = useRouter();
  const route = useRoute();
  const { activeWorkspaceId, activePath } = useProject();
  const { requestAction } = usePersonasNavigation();

  async function ensureChatSession(): Promise<void> {
    if (route.name === 'chat_session') return;
    const workspaceId = activeWorkspaceId.value;
    const projectPath = activePath.value;
    if (!workspaceId || !projectPath) return;

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
    if (target) {
      await router.push({ name: 'chat_session', params: { id: target.id } });
    }
  }

  async function runAction(action: PersonasNavAction): Promise<void> {
    await ensureChatSession();
    requestAction(action);
  }

  function askOpinion(): Promise<void> {
    return runAction('opinion');
  }

  function startMeeting(): Promise<void> {
    return runAction('meeting');
  }

  function discuss(): Promise<void> {
    return runAction('discuss');
  }

  function viewMeeting(meeting: MeetingSummary): void {
    void relaunchMeeting({
      personaIds: meeting.persona_ids,
      topic: meeting.topic,
      rounds: meeting.rounds ?? 3,
    });
  }

  async function relaunchMeeting(config: RelaunchConfig): Promise<void> {
    await ensureChatSession();
    sessionStorage.setItem(
      'workproba.personas.relaunchMeeting',
      JSON.stringify(config),
    );
    requestAction('meeting');
  }

  async function resumeDiscussion(payload: ResumePayload): Promise<void> {
    await ensureChatSession();
    sessionStorage.setItem(
      'workproba.personas.resume',
      JSON.stringify(payload),
    );
    requestAction('discuss');
  }

  return {
    askOpinion,
    startMeeting,
    discuss,
    viewMeeting,
    relaunchMeeting,
    resumeDiscussion,
  };
}
