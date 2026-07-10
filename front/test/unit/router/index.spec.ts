import { afterEach, describe, expect, it, vi } from 'vitest';

type RouterMocks = {
  createMemoryHistory: ReturnType<typeof vi.fn>;
  createWebHistory: ReturnType<typeof vi.fn>;
  createWebHashHistory: ReturnType<typeof vi.fn>;
  createRouter: ReturnType<typeof vi.fn>;
};

const setupRouterModule = async (env: {
  server?: string;
  routerMode?: string;
  routerBase?: string;
}) => {
  vi.resetModules();
  vi.unstubAllEnvs();

  if (env.server !== undefined) {
    vi.stubEnv('SERVER', env.server);
  }
  if (env.routerMode !== undefined) {
    vi.stubEnv('VUE_ROUTER_MODE', env.routerMode);
  }
  if (env.routerBase !== undefined) {
    vi.stubEnv('VUE_ROUTER_BASE', env.routerBase);
  }

  const mocks: RouterMocks = {
    createMemoryHistory: vi.fn(() => 'memory-history'),
    createWebHistory: vi.fn(() => 'web-history'),
    createWebHashHistory: vi.fn(() => 'hash-history'),
    createRouter: vi.fn((options) => ({ options })),
  };

  vi.doMock('vue-router', () => mocks);
  vi.doMock('@router/routes', () => ({ default: [{ path: '/' }] }));

  const module = await import('../../../src/router/index');

  return { module, mocks };
};

describe('router index', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.doUnmock('vue-router');
    vi.doUnmock('@router/routes');
  });

  it('utilise createMemoryHistory en environnement server', async () => {
    const { module, mocks } = await setupRouterModule({
      server: 'true',
      routerBase: '/server',
    });

    expect(mocks.createMemoryHistory).toHaveBeenCalledWith('/server');
    expect(mocks.createWebHistory).not.toHaveBeenCalled();
    expect(mocks.createWebHashHistory).not.toHaveBeenCalled();
    expect(mocks.createRouter).toHaveBeenCalledTimes(1);

    const router = module.default as { options: { history: string } };
    expect(router.options.history).toBe('memory-history');
  });

  it('utilise createWebHistory quand le mode history est demandé', async () => {
    const { module, mocks } = await setupRouterModule({
      server: '',
      routerMode: 'history',
      routerBase: '/history',
    });

    expect(mocks.createMemoryHistory).not.toHaveBeenCalled();
    expect(mocks.createWebHistory).toHaveBeenCalledWith('/history');
    expect(mocks.createWebHashHistory).not.toHaveBeenCalled();

    const router = module.default as { options: { history: string } };
    expect(router.options.history).toBe('web-history');
  });

  it('utilise createWebHashHistory par défaut côté navigateur', async () => {
    const { module, mocks } = await setupRouterModule({
      server: '',
      routerMode: 'hash',
      routerBase: '/hash',
    });

    expect(mocks.createMemoryHistory).not.toHaveBeenCalled();
    expect(mocks.createWebHistory).not.toHaveBeenCalled();
    expect(mocks.createWebHashHistory).toHaveBeenCalledWith('/hash');

    const router = module.default as { options: { history: string } };
    expect(router.options.history).toBe('hash-history');
  });

  it('définit un scrollBehavior qui remonte en haut de page', async () => {
    const { module } = await setupRouterModule({
      server: '',
      routerMode: 'hash',
      routerBase: '/',
    });

    const router = module.default as {
      options: { scrollBehavior: () => { left: number; top: number } };
    };

    expect(router.options.scrollBehavior()).toEqual({ left: 0, top: 0 });
  });
});
