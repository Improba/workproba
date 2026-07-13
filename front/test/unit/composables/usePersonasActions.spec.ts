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

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('usePersonasActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeRef.value = { name: 'chat_session', params: { id: 'session-1' } };
    sessionStorage.clear();
    listSessions.mockResolvedValue([{ id: 'session-1', title: 'Test' }]);
    createSession.mockResolvedValue({ id: 'session-new', title: 'New' });
  });

  it('resumeDiscussion transmet le payload resume via requestAction', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { resumeDiscussion } = usePersonasActions();

    const payload = {
      discussionId: 'disc-1',
      personaIds: ['p1'],
      messages: [{ id: 'm1', role: 'user' as const, content: 'Hello' }],
    };

    await resumeDiscussion(payload);

    expect(requestAction).toHaveBeenCalledWith('discuss', {
      personaIds: ['p1'],
      resume: payload,
    });
  });

  it('discuss sans ids n\'envoie pas de personaIds', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { discuss } = usePersonasActions();

    await discuss();

    expect(requestAction).toHaveBeenCalledWith('discuss', undefined);
  });

  it('discuss transmet les personaIds', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { discuss } = usePersonasActions();

    await discuss(['p1']);

    expect(requestAction).toHaveBeenCalledWith('discuss', { personaIds: ['p1'] });
  });

  it('ne navigue pas quand la session chat est déjà active', async () => {
    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { askOpinion } = usePersonasActions();

    await askOpinion();

    expect(routerPush).not.toHaveBeenCalled();
    expect(requestAction).toHaveBeenCalledWith('opinion', undefined);
  });

  it('n\'émet pas l\'action si aucune session chat ne peut être ouverte', async () => {
    routeRef.value = { name: 'home', params: {} };
    listSessions.mockResolvedValue([]);
    createSession.mockResolvedValue(null);

    const { usePersonasActions } = await import('@composables/usePersonasActions');
    const { discuss } = usePersonasActions();

    await discuss(['p1']);

    expect(routerPush).not.toHaveBeenCalled();
    expect(requestAction).not.toHaveBeenCalled();
  });
});
