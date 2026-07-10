import { RouteRecordRaw } from 'vue-router';

export const demoRoutes: RouteRecordRaw[] = [
  {
    path: 'demo',
    name: 'demo',
    component: () => import('@lib-improba/pages/demo/Index.vue'),
    children: [
      {
        path: 'Sandbox',
        name: 'demo-sandbox',
        component: () => import('@lib-improba/pages/demo/Sandbox.vue')
      },
      {
        path: 'anubis',
        name: 'demo-anubis',
        component: () => import('@lib-improba/pages/demo/Anubis.vue')
      },
      {
        path: 'mastok',
        name: 'demo-mastok',
        component: () => import('@lib-improba/pages/demo/Mastok.vue')
      },
    ]
  }
]
