# Standard Layout

Le `StandardLayout` est un composant de layout principal pour les applications utilisant Quasar et Vue 3. Il fournit une structure standardisée avec une barre de navigation (toolbar) en haut et un conteneur de pages.

## Vue d'ensemble

Le `StandardLayout` encapsule :
- Une **toolbar** avec navigation principale et menu utilisateur
- Un **conteneur de pages** pour le contenu principal
- La gestion automatique des menus selon les rôles utilisateur
- Le support des slots pour personnalisation

## Architecture

```
standard/
├── Index.vue                    # Wrapper pour compatibilité avec les imports existants
├── StandardLayout.vue          # Composant principal du layout
├── toolbar/
│   ├── Index.vue               # Wrapper du toolbar
│   └── StandardToolbar.vue    # Composant toolbar avec navigation et menu utilisateur
├── types/
│   ├── menu-item.types.ts      # Types pour les items de menu
│   ├── layout-props.types.ts   # Types pour les props du layout
│   └── toolbar-props.types.ts # Types pour les props du toolbar
└── config/
    ├── default-menu-items.ts   # Menu items par défaut
    └── default-user-menu-items.ts # User menu items par défaut
```

## Utilisation de base

```vue
<template>
  <StandardLayout>
    <DPage>
      <!-- Votre contenu ici -->
      <router-view />
    </DPage>
  </StandardLayout>
</template>

<script setup lang="ts">
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';
</script>
```

## Props

### StandardLayoutProps

| Prop | Type | Défaut | Description |
|------|------|--------|-------------|
| `menuItems` | `MenuItem[] \| null` | `null` | Items de menu personnalisés. Si `null`, utilise les items par défaut. |
| `profileMenuItems` | `UserMenuItem[] \| null` | `null` | Items du menu utilisateur personnalisés. Si `null`, utilise les items par défaut (thème, déconnexion). |
| `roleTitle` | `string` | `''` | Titre à afficher pour le rôle utilisateur dans la toolbar. |
| `themeLabel` | `string` | `''` | Label pour le toggle de thème (non utilisé actuellement). |
| `leftDrawerOnTop` | `boolean` | `false` | Si `true`, le drawer gauche est positionné au-dessus du contenu. |

### Exemple avec props personnalisées

```vue
<template>
  <StandardLayout
    :menuItems="customMenuItems"
    :profileMenuItems="customUserMenuItems"
    roleTitle="Administrateur"
  >
    <router-view />
  </StandardLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';
import type { MenuItem, UserMenuItem } from '@lib-improba/components/layouts/standard/types/menu-item.types';

const customMenuItems = computed<MenuItem[]>(() => [
  {
    label: 'Accueil',
    route: { name: 'home' },
  },
  {
    label: 'Dashboard',
    route: { name: 'dashboard' },
  },
]);

const customUserMenuItems = computed<UserMenuItem[]>(() => [
  {
    name: 'profile',
    label: 'Mon profil',
    action: () => {
      // Navigation vers le profil
    },
  },
]);
</script>
```

## Slots

### Slot par défaut

Le slot par défaut contient le contenu principal de la page. Si aucun contenu n'est fourni, `<router-view />` est utilisé par défaut.

```vue
<StandardLayout>
  <DPage>
    <h1>Ma page</h1>
    <p>Contenu de la page</p>
  </DPage>
</StandardLayout>
```

### Slot `toolbar-logo`

Permet de personnaliser le logo affiché dans la toolbar.

```vue
<StandardLayout>
  <template #toolbar-logo>
    <img src="/custom-logo.png" alt="Logo" />
  </template>
  
  <router-view />
</StandardLayout>
```

### Slot `toolbar`

Permet d'ajouter du contenu supplémentaire dans la toolbar (à droite des menus).

```vue
<StandardLayout>
  <template #toolbar>
    <q-btn icon="notifications" round />
    <q-btn icon="settings" round />
  </template>
  
  <router-view />
</StandardLayout>
```

## Types

### MenuItem

Représente un item de menu dans la barre de navigation.

```typescript
interface MenuItem {
  /** Label affiché (string ou fonction) */
  label: string | (() => string);
  /** Route vers laquelle naviguer */
  route: RouteLocationRaw;
  /** Si l'item est désactivé */
  disable?: boolean;
  /** Nom de l'icône (optionnel) */
  icon?: string;
  /** Identifiant unique (optionnel) */
  name?: string;
}
```

**Exemple :**

```typescript
const menuItem: MenuItem = {
  label: 'Accueil',
  route: { name: 'home' },
  icon: 'home',
};
```

### UserMenuItem

Représente un item dans le menu déroulant utilisateur.

```typescript
interface UserMenuItem {
  /** Label affiché (string ou fonction) */
  label: string | (() => string);
  /** Identifiant unique requis */
  name: string;
  /** Action à exécuter au clic */
  action?: () => void;
  /** Si l'item est cliquable (par défaut: true) */
  clickable?: boolean;
  /** Classe CSS optionnelle */
  class?: string;
}
```

**Exemple :**

```typescript
const userMenuItem: UserMenuItem = {
  name: 'logout',
  label: () => i18n.t('layout.dropDownMenu.quit'),
  clickable: false,
  action: () => {
    auth.methods.logout();
  },
};
```

## Fonctionnalités spéciales

### Ajout automatique du menu Admin

Si l'utilisateur connecté a le rôle `ADMIN`, un item de menu "Admin" est automatiquement ajouté à la fin de la liste des menu items.

```typescript
// Dans StandardLayout.vue
if (auth.methods.hasAnyRole([EUserRole.ADMIN])) {
  items.push({
    label: 'Admin',
    route: { name: 'admin' },
  });
}
```

### Menu utilisateur par défaut

Par défaut, le menu utilisateur contient :
- **Thème** : Toggle pour changer entre thème clair/sombre
- **Quitter** : Déconnexion de l'utilisateur

Ces items peuvent être remplacés en passant la prop `profileMenuItems`.

## Exemples complets

### Exemple 1 : Layout simple

```vue
<template>
  <StandardLayout>
    <DPage>
      <h1>Bienvenue</h1>
      <router-view />
    </DPage>
  </StandardLayout>
</template>

<script setup lang="ts">
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';
</script>
```

### Exemple 2 : Layout avec menu personnalisé

```vue
<template>
  <StandardLayout :menuItems="menuItems">
    <DPage>
      <router-view />
    </DPage>
  </StandardLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';
import type { MenuItem } from '@lib-improba/components/layouts/standard/types/menu-item.types';

const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'Accueil',
    route: { name: 'home' },
  },
  {
    label: 'Articles',
    route: { name: 'articles' },
  },
  {
    label: 'Contact',
    route: { name: 'contact' },
    disable: false,
  },
]);
</script>
```

### Exemple 3 : Layout avec slots personnalisés

```vue
<template>
  <StandardLayout>
    <template #toolbar-logo>
      <q-img src="/logo.png" width="120px" />
    </template>
    
    <template #toolbar>
      <q-btn icon="search" flat round />
      <q-btn icon="notifications" flat round>
        <q-badge color="red" floating>3</q-badge>
      </q-btn>
    </template>
    
    <DPage>
      <router-view />
    </DPage>
  </StandardLayout>
</template>

<script setup lang="ts">
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';
</script>
```

## Structure du Toolbar

Le `StandardToolbar` affiche :
1. **Logo** (ou slot `logo`) à gauche
2. **Menu items** (navigation principale) au centre
3. **Nom d'utilisateur** (si disponible)
4. **Menu utilisateur** (dropdown avec icône compte) à droite
5. **Slot toolbar** pour contenu supplémentaire

## Notes importantes

- Le layout utilise Quasar `q-layout` avec la vue `hHh lpR fff` par défaut (ou `lHh LpR fff` si `leftDrawerOnTop` est `true`)
- Les menu items par défaut sont définis dans `config/default-menu-items.ts` (actuellement vide)
- Les user menu items par défaut sont définis dans `config/default-user-menu-items.ts`
- Le layout utilise `useAuth` pour vérifier les rôles et obtenir les informations utilisateur
- Le layout utilise `useI18n` pour l'internationalisation des labels

## Import

```typescript
// Import direct du composant
import StandardLayout from '@lib-improba/components/layouts/standard/StandardLayout.vue';

// Ou via le wrapper (pour compatibilité)
import StandardLayout from '@lib-improba/components/layouts/standard/Index.vue';

// Ou via l'export centralisé
import { StandardLayout } from '@lib-improba/components/layouts';
```

## Types disponibles

```typescript
// Types pour les props
import type { StandardLayoutProps } from '@lib-improba/components/layouts/standard/types/layout-props.types';

// Types pour les menus
import type { MenuItem, UserMenuItem } from '@lib-improba/components/layouts/standard/types/menu-item.types';

// Types pour le toolbar
import type { StandardToolbarProps } from '@lib-improba/components/layouts/standard/types/toolbar-props.types';
```

