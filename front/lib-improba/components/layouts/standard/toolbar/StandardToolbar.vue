<!--
  Composant StandardToolbar - Barre de navigation principale
  
  Ce composant affiche la toolbar standard avec :
  - Logo (personnalisable via slot ou Logo par défaut)
  - Onglets de navigation (menu items) avec routage automatique
  - Nom d'utilisateur affiché si disponible
  - Menu dropdown utilisateur avec actions (theme, logout, etc.)
  - Slot pour contenu personnalisé à droite
  
  Structure :
  - DMainToolbar : Conteneur principal avec bordure et padding
  - DTabs : Système d'onglets pour la navigation
  - Logo : Affiché par défaut ou remplacé par slot
  - DRouteTab : Onglets de navigation générés depuis menuItems
  - q-space : Espace flexible pour pousser le contenu à droite
  - DBtnDropdown : Menu dropdown utilisateur avec icône compte
  
  Gestion spéciale :
  - Item 'theme' : Affiche ThemeToggler au lieu d'un label simple
  - Items avec action : Exécutent l'action au clic
  - Items avec clickable=false : Ne sont pas cliquables
  
  Utilisation :
  ```vue
  <StandardToolbar
    :menuItems="menuItems"
    :userMenuItems="userMenuItems"
    roleTitle="Admin"
  >
    <template #logo>
      <CustomLogo />
    </template>
    <MBtn>Action personnalisée</MBtn>
  </StandardToolbar>
  ```
-->
<template>
  <q-toolbar
    class="bg-primary-low"
    style="border-bottom: 1px solid hsla(0, 0%, 100%, 0.12); padding: 20"
  >
    <q-tabs class="full-width text-text" align="left">
      <!-- Logo personnalisable ou Logo par défaut -->
      <template v-if="$slots.logo">
        <slot name="logo" />
      </template>
      <Logo v-else />

      <!-- Onglets de navigation générés depuis menuItems -->
      <q-route-tab
        v-for="(item, index) in props.menuItems"
        :key="getMenuItemKey(item, index)"
        :to="item.route"
        :label="getMenuItemLabel(item)"
        :disable="item.disable"
        dense
      />

      <!-- Espace flexible pour pousser le contenu à droite -->
      <q-space />

      <!-- Nom d'utilisateur affiché si disponible -->
      <template v-if="userName">
        <span class="text-text">{{ userName }}</span>
      </template>

      <!-- Menu dropdown utilisateur -->
      <q-btn-dropdown
        v-if="props.userMenuItems.length > 0"
        flat
        no-caps
        color="primary"
      >
        <template #label>
          <q-icon name="account_circle" size="md" />
        </template>
        <q-list>
          <q-item
            v-for="item in props.userMenuItems"
            :key="item.name"
            clickable
            v-close-popup
            @click="handleUserMenuItemClick(item)"
          >
            <!-- Item spécial 'theme' : affiche ThemeToggler -->
            <q-item-section v-if="item.name === 'theme'">
              <ThemeToggler />
            </q-item-section>
            <!-- Autres items : affiche le label -->
            <q-item-section v-else>
              <q-item-label>{{ getUserMenuItemLabel(item) }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-btn-dropdown>

      <!-- Slot pour contenu personnalisé à droite -->
      <slot />
    </q-tabs>
  </q-toolbar>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuth } from '@lib-improba/composables/use-auth';
import Logo from '../../Logo.vue';
import ThemeToggler from '../../theme-toggler/ThemeToggler.vue';
import type { StandardToolbarProps } from '../types/toolbar-props.types';
import type { MenuItem, UserMenuItem } from '../types/menu-item.types';

const props = defineProps<StandardToolbarProps>();

const router = useRouter();
const auth = useAuth(router);

/**
 * Calcule le nom d'utilisateur à afficher dans la toolbar
 * 
 * Priorité d'affichage :
 * 1. firstname de l'utilisateur (si disponible)
 * 2. username du UserJwt (si disponible)
 * 3. roleTitle fourni en props (fallback)
 * 
 * @returns Nom d'utilisateur à afficher ou undefined
 */
const userName = computed(() => {
  const user = auth.sharedState?.user;
  return user?.firstname ?? user?.userJwt?.username ?? props.roleTitle;
});

/**
 * Generates a unique key for a menu item
 * Uses name if available, otherwise creates a key from label and route
 * 
 * Priority:
 * 1. item.name (if provided) - most reliable
 * 2. label + route.name (if route is an object with name)
 * 3. label + route.path (if route is an object with path)
 * 4. label + route string (if route is a string)
 * 5. label + index (fallback)
 */
function getMenuItemKey(item: MenuItem, index: number): string {
  // Use name if available (most reliable and unique)
  if (item.name) {
    return item.name;
  }
  
  // Generate key from label and route to ensure uniqueness
  const label = getMenuItemLabel(item);
  
  // Handle route as string
  if (typeof item.route === 'string') {
    return `${label}-${item.route}`;
  }
  
  // Handle route as object
  if (item.route && typeof item.route === 'object') {
    // Prefer route.name if available (most stable)
    if ('name' in item.route && item.route.name) {
      return `${label}-${String(item.route.name)}`;
    }
    // Fallback to route.path
    if ('path' in item.route && item.route.path) {
      return `${label}-${String(item.route.path)}`;
    }
  }
  
  // Last resort: use index (not ideal but ensures uniqueness)
  return `${label}-${index}`;
}

/**
 * Gets the label from a menu item (handles both string and function types)
 */
function getMenuItemLabel(item: MenuItem): string {
  return typeof item.label === 'string' ? item.label : item.label();
}

/**
 * Gets the label from a user menu item (handles both string and function types)
 */
function getUserMenuItemLabel(item: UserMenuItem): string {
  return typeof item.label === 'string' ? item.label : item.label();
}

/**
 * Handles click on a user menu item
 */
function handleUserMenuItemClick(item: UserMenuItem): void {
  if (item.action && item.clickable !== false) {
    item.action();
  }
}
</script>

