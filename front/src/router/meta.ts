import { RouteMeta } from 'vue-router';

declare module 'vue-router' {
  interface RouteMeta {
    ssr?: boolean;
  }
}

export const CSR_META: RouteMeta = { ssr: false };
export const DESKTOP_META: RouteMeta = { ...CSR_META };

export const HOME_ROUTE = 'home';
