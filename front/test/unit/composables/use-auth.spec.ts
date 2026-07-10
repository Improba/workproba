import { beforeEach, describe, expect, it, vi } from 'vitest';
import { EUserRole } from '../../../src/types/enums';
import { HOME_ROUTE } from '../../../src/router/meta';
import { useAuth } from '../../../lib-improba/composables/use-auth';

const {
  initAxiosMock,
  initRouterMock,
  loginMock,
  refreshTokenMock,
  getCurrentUserMock,
  cookiesMock,
} = vi.hoisted(() => ({
  initAxiosMock: vi.fn(async () => undefined),
  initRouterMock: vi.fn(),
  loginMock: vi.fn(),
  refreshTokenMock: vi.fn(),
  getCurrentUserMock: vi.fn(),
  cookiesMock: (() => {
    const store = new Map<string, string>();
    return {
      get: vi.fn((key: string) => store.get(key)),
      set: vi.fn((key: string, value: string) => {
        store.set(key, value);
      }),
      remove: vi.fn((key: string) => {
        store.delete(key);
      }),
      has: vi.fn((key: string) => store.has(key)),
    };
  })(),
}));

vi.mock('quasar', () => ({
  Cookies: cookiesMock,
}));

vi.mock('@lib-improba/composables/use-auth/axios', () => ({
  init: initAxiosMock,
}));

vi.mock('@lib-improba/composables/use-auth/router', () => ({
  init: initRouterMock,
}));

vi.mock('@services/users/auth.service', () => ({
  AuthService: {
    login: loginMock,
    refreshToken: refreshTokenMock,
  },
}));

vi.mock('@services/users/user.service', () => ({
  UserService: {
    getCurrentUser: getCurrentUserMock,
  },
}));

type RouterMock = {
  currentRoute: { value: { query: Record<string, unknown> } };
  push: ReturnType<typeof vi.fn>;
  beforeEach: ReturnType<typeof vi.fn>;
  replace: ReturnType<typeof vi.fn>;
};

const createRouterMock = (query: Record<string, unknown> = {}): RouterMock => ({
  currentRoute: { value: { query } },
  push: vi.fn(),
  beforeEach: vi.fn(),
  replace: vi.fn(),
});

describe('use-auth composable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('connecte un utilisateur puis redirige vers HOME_ROUTE', async () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    const user = {
      roles: [EUserRole.ADMIN],
      userJwt: { username: 'admin@test.local' },
    };

    loginMock.mockResolvedValue({ token: 'jwt-token' });
    getCurrentUserMock.mockResolvedValue(user as never);

    await auth.methods.login({
      username: 'admin@test.local',
      password: 'password',
    });

    expect(loginMock).toHaveBeenCalledWith({
      username: 'admin@test.local',
      password: 'password',
    });
    expect(getCurrentUserMock).toHaveBeenCalledTimes(1);
    expect(auth.sharedState.token).toBe('jwt-token');
    expect(auth.sharedState.user).toEqual(user);
    expect(auth.methods.isLoggedIn()).toBe(true);
    expect(auth.methods.hasAnyRole([EUserRole.ADMIN])).toBe(true);
    expect(router.push).toHaveBeenCalledWith({ name: HOME_ROUTE });

    auth.methods.logout();
  });

  it('retourne false pour hasAnyRole quand non connecté', () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    auth.methods.logout();

    expect(auth.methods.hasAnyRole([EUserRole.ADMIN])).toBe(false);
    expect(auth.methods.isLoggedIn()).toBe(false);
  });

  it('échoue à refreshToken quand aucun token n’est présent', async () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    auth.methods.logout();

    await expect(auth.methods.refreshToken()).rejects.toThrow('No token to refresh');
    expect(refreshTokenMock).not.toHaveBeenCalled();
  });

  it('utilise le redirect de query après login', async () => {
    const router = createRouterMock({ redirect: '/admin/users' });
    const auth = useAuth(router as never);

    loginMock.mockResolvedValue({ token: 'jwt-token' });
    getCurrentUserMock.mockResolvedValue({
      roles: [EUserRole.USER],
      userJwt: { username: 'user@test.local' },
    } as never);

    await auth.methods.login({
      username: 'user@test.local',
      password: 'password',
    });

    expect(router.push).toHaveBeenCalledWith('/admin/users');

    auth.methods.logout();
  });

  it('déconnecte l’utilisateur et nettoie la session', () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    auth.sharedState.user = {
      roles: [EUserRole.ADMIN],
      userJwt: { username: 'admin@test.local' },
    } as never;
    auth.sharedState.token = 'jwt-token';
    auth.sharedState.loginDate = new Date();

    auth.methods.logout();

    expect(auth.sharedState.user).toBeNull();
    expect(auth.sharedState.token).toBeNull();
    expect(auth.sharedState.loginDate).toBeNull();
    expect(router.push).toHaveBeenCalledWith({ name: 'auth-login' });
  });

  it('initialise les hooks axios/router sans cookie', async () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    auth.methods.logout();
    await auth.methods.init();

    expect(initAxiosMock).toHaveBeenCalledWith({
      sharedState: auth.sharedState,
      methods: auth.methods,
    });
    expect(initRouterMock).toHaveBeenCalledWith(router, {
      sharedState: auth.sharedState,
      methods: auth.methods,
    });
    expect(refreshTokenMock).not.toHaveBeenCalled();
  });

  it('initialise avec cookie + refresh puis met à jour l’état', async () => {
    const router = createRouterMock();
    const auth = useAuth(router as never);

    const cookieName = process.env.APP_NAME || 'auth-token';
    cookiesMock.set(cookieName, 'stale-token');

    refreshTokenMock.mockResolvedValue({ token: 'fresh-token' });
    getCurrentUserMock.mockResolvedValue({
      roles: [EUserRole.ADMIN],
      userJwt: { username: 'admin@test.local' },
    } as never);

    await auth.methods.init();

    expect(refreshTokenMock).toHaveBeenCalledWith('stale-token');
    expect(auth.sharedState.token).toBe('fresh-token');
    expect(auth.methods.isLoggedIn()).toBe(true);
    expect(initRouterMock).toHaveBeenCalledTimes(1);
  });
});
