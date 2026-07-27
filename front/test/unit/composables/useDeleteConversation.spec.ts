import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDeleteConversation } from '@composables/useDeleteConversation';

const mockPush = vi.fn();
const routeName = ref<string | symbol | null | undefined>('home');
const routeParams = ref<Record<string, string>>({});

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({
    get name() {
      return routeName.value;
    },
    get params() {
      return routeParams.value;
    },
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

const deleteSession = vi.fn();
const bumpSessions = vi.fn();

vi.mock('@services/workspaceSession', () => ({
  deleteSession: (...args: unknown[]) => deleteSession(...args),
}));

vi.mock('@composables/useSessionSync', () => ({
  bumpSessions: () => bumpSessions(),
}));

describe('useDeleteConversation', () => {
  beforeEach(() => {
    mockPush.mockReset();
    deleteSession.mockReset();
    bumpSessions.mockReset();
    routeName.value = 'home';
    routeParams.value = {};
    deleteSession.mockResolvedValue(undefined);
  });

  it('supprime la session et notifie la sync', async () => {
    const { removeConversation } = useDeleteConversation();
    const onRemoved = vi.fn();

    const ok = await removeConversation('ws-1', 'sess-1', onRemoved);

    expect(ok).toBe(true);
    expect(deleteSession).toHaveBeenCalledWith('ws-1', 'sess-1');
    expect(onRemoved).toHaveBeenCalledOnce();
    expect(bumpSessions).toHaveBeenCalledOnce();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('redirige vers l\'accueil si la conversation ouverte est supprimée', async () => {
    routeName.value = 'chat_session';
    routeParams.value = { id: 'sess-open' };

    const { removeConversation } = useDeleteConversation();
    await removeConversation('ws-1', 'sess-open');

    expect(mockPush).toHaveBeenCalledWith({ name: 'home' });
  });

  it('ignore les suppressions concurrentes sur la même session', async () => {
    let resolveDelete: (() => void) | undefined;
    deleteSession.mockImplementation(
      () => new Promise<void>((resolve) => {
        resolveDelete = resolve;
      }),
    );

    const { removeConversation, isDeleting } = useDeleteConversation();
    const first = removeConversation('ws-1', 'sess-dup');
    expect(isDeleting('sess-dup')).toBe(true);

    const second = await removeConversation('ws-1', 'sess-dup');
    expect(second).toBe(false);
    expect(deleteSession).toHaveBeenCalledTimes(1);

    resolveDelete?.();
    await first;
    expect(isDeleting('sess-dup')).toBe(false);
  });
});
