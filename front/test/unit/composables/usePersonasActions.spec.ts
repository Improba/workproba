import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

const routerPush = vi.fn();
const routeRef = ref<{ name: string; params: Record<string, string> }>({
  name: 'chat_session',
  params: { id: 'session-1' },
});

const requestAction = vi.fn();
const listSessions = vi.fn();
const createSession = vi.fn();

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

vi.mock('@services/workspaceSession', () => ({
  listSessions,
  createSession,
}));

describe('usePersonasActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeRef.value = { name: 'chat_session', params: { id: 'session-1' } };
    sessionStorage.clear();
    listSessions.mockResolvedValue([{ id: 'session-1', title: 'Test' }]);
    createSession.mockResolvedValue({ id: 'session-new', title: 'New' });
  });

  it('resumeDiscussion écrit sessionStorage avant requestAction', async () => {
    const order: string[] = [];
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key) => {
      order.push(`setItem:${key}`);
    });
    requestAction.mockImplementation(() => {
      order.push('requestAction');
    });

    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { resumeDiscussion } = usePersonasActions();

    await resumeDiscussion({
      discussionId: 'disc-1',
      personaIds: ['p1'],
      messages: [{ id: 'm1', role: 'user', content: 'Hello' }],
    });

    expect(order).toEqual([
      'setItem:workproba.personas.resume',
      'requestAction',
    ]);
    expect(requestAction).toHaveBeenCalledWith('discuss');
    setItemSpy.mockRestore();
  });

  it('ne navigue pas quand la session chat est déjà active', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { askOpinion } = usePersonasActions();

    await askOpinion();

    expect(routerPush).not.toHaveBeenCalled();
    expect(requestAction).toHaveBeenCalledWith('opinion');
  });
});
