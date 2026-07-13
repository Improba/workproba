import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

const routerPush = vi.fn();
const routeRef = ref<{ name: string; params: Record<string, string> }>({
  name: 'chat_session',
  params: { id: 'session-1' },
});

const requestAction = vi.fn();
const openSideChat = vi.fn();
const getFormattedContext = vi.fn(() => '');
const refresh = vi.fn();
const getPluginDataDir = vi.fn().mockResolvedValue('/tmp/personas');

const sessionMocks = vi.hoisted(() => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
  useRoute: () => routeRef.value,
}));

vi.mock('@composables/useProject', () => ({
  useProject: () => ({
    activeWorkspaceId: ref('ws-1'),
    activePath: ref('/tmp/project'),
  }),
}));

vi.mock('@composables/usePersonasNavigation', () => ({
  usePersonasNavigation: () => ({
    requestAction,
  }),
}));

vi.mock('@composables/useMainChatContext', () => ({
  useMainChatContext: () => ({
    getFormattedContext,
  }),
}));

vi.mock('@composables/useSideChat', () => ({
  useSideChat: () => ({
    openSideChat,
  }),
}));

vi.mock('@composables/usePlugins', () => ({
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  usePlugins: () => ({
    isPersonasPluginActive: ref(true),
    getPluginDataDir,
  }),
}));

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    refresh,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: ref('fr') }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

vi.mock('@services/workspaceSession', () => ({
  listSessions: sessionMocks.listSessions,
  createSession: sessionMocks.createSession,
}));

describe('usePersonasActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeRef.value = { name: 'chat_session', params: { id: 'session-1' } };
    sessionStorage.clear();
    getFormattedContext.mockReturnValue('');
    sessionMocks.listSessions.mockResolvedValue([
      { id: 'session-1', title: 'Test', messages: [], updatedAt: '2026-01-01' },
    ]);
    sessionMocks.createSession.mockResolvedValue({
      id: 'session-new',
      title: 'New',
      messages: [],
      updatedAt: '2026-01-02',
    });
  });

  it('askOpinion ouvre le side chat directement sans naviguer', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { askOpinion } = usePersonasActions();

    await askOpinion(['p1']);

    expect(routerPush).not.toHaveBeenCalled();
    expect(requestAction).not.toHaveBeenCalled();
    expect(openSideChat).toHaveBeenCalledWith('workproba.personas', {
      mode: 'avis',
      personaIds: ['p1'],
      conversationContext: '',
      autoAsk: true,
      resume: undefined,
    });
  });

  it('discuss ouvre le side chat directement avec autoAsk', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { discuss } = usePersonasActions();

    await discuss(['p1']);

    expect(routerPush).not.toHaveBeenCalled();
    expect(openSideChat).toHaveBeenCalledWith('workproba.personas', {
      mode: 'discussion',
      personaIds: ['p1'],
      conversationContext: '',
      autoAsk: true,
      resume: undefined,
    });
  });

  it('resumeDiscussion ouvre le side chat avec le payload resume', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { resumeDiscussion } = usePersonasActions();

    const payload = {
      discussionId: 'disc-1',
      personaIds: ['p1'],
      messages: [{ id: 'm1', role: 'user' as const, content: 'Hello' }],
    };

    await resumeDiscussion(payload);

    expect(routerPush).not.toHaveBeenCalled();
    expect(openSideChat).toHaveBeenCalledWith('workproba.personas', {
      mode: 'discussion',
      personaIds: ['p1'],
      conversationContext: '',
      autoAsk: false,
      resume: payload,
    });
  });

  it('startMeeting passe par requestAction après navigation si besoin', async () => {
    routeRef.value = { name: 'home', params: {} };

    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { startMeeting } = usePersonasActions();

    await startMeeting();

    expect(routerPush).toHaveBeenCalled();
    expect(requestAction).toHaveBeenCalledWith('meeting', undefined);
  });

  it('n\'émet pas l\'action réunion si aucune session chat ne peut être ouverte', async () => {
    routeRef.value = { name: 'home', params: {} };
    sessionMocks.listSessions.mockResolvedValue([]);
    sessionMocks.createSession.mockResolvedValue(null);

    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { startMeeting } = usePersonasActions();

    await startMeeting();

    expect(routerPush).not.toHaveBeenCalled();
    expect(requestAction).not.toHaveBeenCalled();
  });
});
