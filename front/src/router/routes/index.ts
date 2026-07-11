import { DESKTOP_META, HOME_ROUTE } from '@router/meta';
import { RouteRecordRaw } from 'vue-router';
import { chatRoutes } from './chat.routes';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'root',
    component: () => import('@pages/Index.vue'),
    redirect: { name: HOME_ROUTE },
    children: [
      {
        path: 'home',
        name: HOME_ROUTE,
        meta: DESKTOP_META,
        component: () => import('@pages/Home.vue'),
      },
      {
        path: 'settings/models',
        name: 'settings_models',
        meta: DESKTOP_META,
        component: () => import('@pages/settings/ModelsSettings.vue'),
      },
      {
        path: 'settings/plugins',
        name: 'settings_plugins',
        meta: DESKTOP_META,
        component: () => import('@pages/settings/PluginsSettings.vue'),
      },
      {
        path: 'settings/enterprise',
        name: 'settings_enterprise',
        meta: DESKTOP_META,
        component: () => import('@pages/settings/EnterpriseSettings.vue'),
      },
      ...chatRoutes,
    ],
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('@pages/ErrorNotFound.vue'),
  },
];

export default routes;
