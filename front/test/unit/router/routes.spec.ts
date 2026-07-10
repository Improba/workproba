import { describe, expect, it } from 'vitest';
import { DESKTOP_META, HOME_ROUTE } from '../../../src/router/meta';
import routes from '../../../src/router/routes/index';

describe('router routes', () => {
  it('déclare home et chat en mode bureau', () => {
    const root = routes[0];
    const homeRoute = root.children?.find((route) => route.name === HOME_ROUTE);
    const chatRoute = root.children?.find((route) => route.name === 'chat_session');

    expect(root.name).toBe('root');
    expect(root.redirect).toEqual({ name: HOME_ROUTE });
    expect(homeRoute?.meta).toEqual(DESKTOP_META);
    expect(chatRoute?.path).toBe('chat/:id');
    expect(chatRoute?.meta).toEqual(DESKTOP_META);
  });

  it('déclare une route catch-all', () => {
    const catchAll = routes.find((route) => route.path === '/:catchAll(.*)*');
    expect(catchAll).toBeDefined();
  });
});
