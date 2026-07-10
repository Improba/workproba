<!--
  Composant StandardLayout - Layout principal avec header et contenu
  
  Ce composant fournit la structure de base du layout standard avec :
  - Un header fixe contenant la toolbar de navigation
  - Un conteneur de page pour le contenu principal
  - Gestion dynamique des items de menu selon les rôles utilisateur
  - Support des slots pour personnaliser la toolbar et le logo
  
  Structure Quasar Layout :
  - View 'hHh lpR fff' (par défaut) : Header fixe en haut, contenu scrollable
  - View 'lHh LpR fff' (si leftDrawerOnTop) : Drawer gauche en overlay, header fixe
  
  Fonctionnalités :
  - Menu items dynamiques : utilise les items fournis ou les items par défaut
  - Ajout automatique du menu Admin si l'utilisateur a le rôle ADMIN
  - User menu items : utilise les items personnalisés ou les items par défaut
  - Slots disponibles : toolbar-logo, toolbar, default
  
  Utilisation :
  ```vue
  <StandardLayout 
    :menuItems="customMenuItems"
    :profileMenuItems="customUserMenuItems"
    roleTitle="Administrateur"
  >
    <template #toolbar-logo>
      <CustomLogo />
    </template>
    <template #toolbar>
      <MBtn>Action</MBtn>
    </template>
    <MPage>Contenu de la page</MPage>
  </StandardLayout>
  ```
-->
<template>
  <q-layout :view="leftDrawerOnTop ? 'lHh LpR fff' : 'hHh lpR fff'">
    <q-header>
      <StandardToolbar
        :menuItems="computedMenuItems"
        :userMenuItems="computedUserMenuItems"
        :roleTitle="roleTitle"
        :themeLabel="themeLabel"
      >
        <template #logo v-if="$slots['toolbar-logo']">
          <slot name="toolbar-logo" />
        </template>
        <template #default v-if="$slots.toolbar">
          <slot name="toolbar" />
        </template>
      </StandardToolbar>
    </q-header>
    <q-page-container>
      <slot><router-view /></slot>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useAuth } from '@lib-improba/composables/use-auth';
import { EUserRole } from '#types';
import StandardToolbar from './toolbar/StandardToolbar.vue';
import { defaultMenuItems } from './config/default-menu-items';
import { getDefaultUserMenuItems } from './config/default-user-menu-items';
import type { StandardLayoutProps } from './types/layout-props.types';

const props = withDefaults(defineProps<StandardLayoutProps>(), {
  menuItems: null,
  profileMenuItems: null,
  roleTitle: '',
  themeLabel: '',
  leftDrawerOnTop: false,
});

const router = useRouter();
const i18n = useI18n();
const auth = useAuth(router);

/**
 * Calcule les items de menu à afficher dans la navigation
 * 
 * Logique :
 * - Utilise les items fournis en props, sinon utilise les items par défaut
 * - Ajoute automatiquement le menu "Admin" si l'utilisateur a le rôle ADMIN
 * 
 * @returns Liste des items de menu à afficher
 */
const computedMenuItems = computed(() => {
  const items = props.menuItems ?? [...defaultMenuItems];

  if (auth.methods.hasAnyRole([EUserRole.ADMIN])) {
    items.push({
      label: 'Admin',
      route: { name: 'admin' },
    });
  }

  return items;
});

/**
 * Calcule les items du menu utilisateur (dropdown profil)
 * 
 * Logique :
 * - Utilise les items personnalisés si fournis en props
 * - Sinon utilise les items par défaut (theme toggle + logout)
 * 
 * @returns Liste des items du menu utilisateur
 */
const computedUserMenuItems = computed(() => {
  if (props.profileMenuItems) {
    return props.profileMenuItems;
  }
  return getDefaultUserMenuItems(i18n, auth);
});
</script>

