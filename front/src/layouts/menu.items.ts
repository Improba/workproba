import { RouteLocationRaw } from 'vue-router';

export interface IMenuItem {
  name: string
  icon: string
  label: (i18n?: any) => string
  route: RouteLocationRaw

  disable?: boolean
  action?: (options: { auth?: any, router?: any }) => void
}

// _ DEFAULT ITEMS
export const defaultMenuItems = [] as IMenuItem[];

// _ USER ITEMS
export const userMenuItems = [
    {
      name: 'theme',
      label: (i18n) => i18n.t('theme'),
    },
    {
      name: 'quit',
      label: (i18n) => i18n.t('layout.dropDownMenu.quit'),
      action: ({ auth }) => {
        auth.methods.logout();
      },
    }
  ] as IMenuItem[];

  // _ ADMIN ITEMS
  export const adminMenuItems = [
    {
      label: () => 'Admin',
      name: 'admin-users',
      route: { name: 'admin-users-list' },
      icon: 'UsersRound',
      // action: ({ router }) => {
      //   router.push({
      //     name: 'admin-users-list',
      //   });
      // },
    },
    {
      label: () => 'Mastok',
      name: 'demo-mastok',
      route: { name: 'demo-mastok' },
      icon: 'Component',
    },
    {
      label: () => 'AnubisUI',
      name: 'demo-anubis',
      route: { name: 'demo-anubis' },
      icon: 'Pyramid',
    },
    {
      label: () => 'Sandbox',
      name: 'demo-sandbox',
      route: { name: 'demo-sandbox' },
      icon: 'Shovel',
    },
  ] as IMenuItem[]

    /*{
      name: 'lang',
      label: i18n.t('lang'),
      class: 'q-pa-none',
      action: undefined,
    },*/
    /*{
    label: i18n.t('layout.dropDownMenu.profile'),
    disable: true,
    action: () => {
      router.push(routeFromRole({ name: 'account_profil' }));
    },
  },
  {
    label: i18n.t('layout.dropDownMenu.info'),
    disable: true,
    action: () => {
      router.push(routeFromRole({ name: 'account_info' }));
    },
  },*/
