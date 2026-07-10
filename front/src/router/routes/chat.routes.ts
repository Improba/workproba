import { RouteRecordRaw } from 'vue-router';
import { DESKTOP_META } from '@router/meta';

export const chatRoutes: RouteRecordRaw[] = [
  {
    path: 'chat/:id',
    name: 'chat_session',
    meta: DESKTOP_META,
    component: () => import('@pages/chat/ChatPage.vue'),
  },
];
