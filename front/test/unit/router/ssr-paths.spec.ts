import { describe, expect, it } from 'vitest';
import { defineComponent } from 'vue';
import type { RouteRecordRaw } from 'vue-router';
import { collectSsrPaths, matchesPathSet } from '../../../src/router/ssr-paths';

const stub = defineComponent({ name: 'RouteStub', template: '<div />' });

describe('ssr-paths', () => {
  it('inclut les routes publiques statiques', () => {
    const routes: RouteRecordRaw[] = [
      {
        path: '/public',
        component: stub,
      },
      {
        path: '/nested',
        component: stub,
        children: [
          {
            path: 'child',
            component: stub,
          },
        ],
      },
    ];

    const paths = collectSsrPaths(routes);

    expect(paths.has('/public')).toBe(true);
    expect(paths.has('/nested')).toBe(true);
    expect(paths.has('/nested/child')).toBe(true);
  });

  it('exclut auth, dynamique, redirect-only et routes internes', () => {
    const routes: RouteRecordRaw[] = [
      {
        path: '/',
        redirect: '/home',
        component: stub,
      },
      {
        path: '/home',
        meta: { requiresAuth: true },
        component: stub,
      },
      {
        path: '/userspace',
        meta: { auth: true },
        component: stub,
      },
      {
        path: '/item/:id',
        component: stub,
      },
      {
        path: '/__spa_shell__',
        component: stub,
      },
      {
        path: '/redirect-only',
        redirect: '/public',
      },
      {
        path: '/opt-out',
        meta: { ssr: false },
        component: stub,
      },
    ];

    const paths = collectSsrPaths(routes);

    expect(paths.size).toBe(0);
  });

  it('hérite le CSR des ancêtres', () => {
    const routes: RouteRecordRaw[] = [
      {
        path: '/admin',
        meta: { requiresAuth: true },
        component: stub,
        children: [
          {
            path: 'list',
            component: stub,
          },
        ],
      },
    ];

    const paths = collectSsrPaths(routes);

    expect(paths.has('/admin/list')).toBe(false);
  });

  it('matchesPathSet tolère les slashs finaux', () => {
    const paths = new Set(['/demo', '/demo/']);

    expect(matchesPathSet('/demo', paths)).toBe(true);
    expect(matchesPathSet('/demo/', paths)).toBe(true);
    expect(matchesPathSet('/unknown', paths)).toBe(false);
  });
});
