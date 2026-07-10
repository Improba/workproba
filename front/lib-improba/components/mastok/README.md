# Mastok - Système de composants UI

Mastok est un système de composants UI cohérent et moderne pour les applications Vue 3 / Quasar. Il fournit une collection de composants stylisés qui intègrent parfaitement le système de design Anubis.

## 🎯 Concept

Mastok offre une couche d'abstraction au-dessus des composants Quasar standard, appliquant automatiquement :
- Le système de couleurs Anubis (au lieu des couleurs Quasar par défaut)
- Des styles cohérents et modernes (bordures arrondies, transitions fluides)
- Une API unifiée pour les variantes de couleurs
- Le support des icônes Lucide via le composant `Lucide`

## 🎨 Système de couleurs

Tous les composants Mastok utilisent le système de couleurs Anubis via le composable `use-mastok.ts`. Les variantes disponibles sont :

- **primary** (défaut) : Couleur principale de l'application
- **secondary** : Fond neutre avec bordure et texte primary
- **tertiary** : Fond neutre avec texte neutre
- **light** : Fond neutre clair avec texte sombre
- **danger** : Couleur de danger (rouge)
- **success** : Couleur de succès (vert)
- **warning** : Couleur d'avertissement (orange/jaune)

Chaque variante applique automatiquement :
- Une classe de fond (`bg-*`)
- Une classe de texte (`text-*`)
- Une classe de bordure (`border-*-thin`)

## 📦 Composants disponibles

### MBtn
Bouton stylisé avec support des icônes Lucide.

```vue
<MBtn primary>Sauvegarder</MBtn>
<MBtn secondary lucideIcon="edit">Modifier</MBtn>
<MBtn danger flat lucideIcon="trash">Supprimer</MBtn>
```

### MBtnDropdown
Bouton avec menu déroulant.

```vue
<MBtnDropdown lucideIcon="menu">
  <q-list>
    <q-item clickable>Option 1</q-item>
    <q-item clickable>Option 2</q-item>
  </q-list>
</MBtnDropdown>
```

### MCard
Carte avec structure standardisée (titre, description, contenu, actions).

```vue
<MCard title="Mon titre" description="Ma description">
  <template #content>
    Contenu de la carte
  </template>
  <template #actions>
    <MBtn primary>Action</MBtn>
  </template>
</MCard>
```

### MChip
Badge/Puce pour afficher des tags ou labels.

```vue
<MChip primary>Nouveau</MChip>
<MChip success>Actif</MChip>
<MChip danger>Inactif</MChip>
```

### MDialog
Modale avec structure standardisée et boutons d'action.

```vue
<MDialog 
  v-model="showDialog" 
  title="Confirmer" 
  description="Êtes-vous sûr ?"
  :showCancel="true"
>
  <template #content>
    Contenu de la modale
  </template>
</MDialog>
```

### MPage
Page avec style Mastok (remplace DPage).

```vue
<MPage :padding="true">
  <div>Contenu de la page</div>
</MPage>
```

### MRange
Sélecteur de plage de valeurs (min/max).

```vue
<MRange 
  v-model="range" 
  label="Plage de prix"
  :bind="{ min: 0, max: 1000, step: 10 }"
/>
```

### MSlider
Curseur pour sélectionner une valeur unique.

```vue
<MSlider 
  v-model="value" 
  label="Volume"
  :bind="{ min: 0, max: 100, step: 1 }"
/>
```

### MToggle
Interrupteur personnalisé avec style Mastok.

```vue
<MToggle v-model="enabled" primary />
<MToggle v-model="active" success />
```

### Lucide
Wrapper pour les icônes Lucide avec intégration Anubis.

```vue
<Lucide name="home" size="md" color="primary" />
<Lucide name="user" size="sm" color="neutral-highest" label="Profil" />
```

### MInput
Input stylisé Mastok avec support des types text, search et password.

```vue
<!-- Input de recherche -->
<MInput
  v-model="searchQuery"
  type="search"
  placeholder="Rechercher..."
/>

<!-- Input avec label et validation -->
<MInput
  v-model="email"
  label="Email"
  type="text"
  placeholder="exemple@email.com"
  :rules="[val => !!val || 'Email requis']"
/>

<!-- Input password avec toggle visibilité -->
<MInput
  v-model="password"
  label="Mot de passe"
  type="password"
/>
```

### MTable
Table Mastok avec pagination, tri et synchronisation URL automatique.

**Props principales :**
- `columns` (requis) : Définitions des colonnes (format Quasar QTableColumn[])
- `fetch-function` (requis) : Fonction asynchrone pour récupérer les données
- `filters` : Liste des noms de filtres à synchroniser avec l'URL (ex: `['role', 'status']`)
- `show-edit-action` : Afficher le bouton d'édition (défaut: `true`)
- `show-remove-action` : Afficher le bouton de suppression (défaut: `true`)
- `limit-options` : Options de pagination disponibles (défaut: `[10, 15, 20, 25, 50, 0]`)
- `no-data-icon` : Nom de l'icône Lucide pour l'état "no-data" (défaut: `'CircleQuestionMark'`)
- `no-data-title` : Titre affiché dans l'état "no-data" (défaut: `'Aucun résultat'`)
- `no-data-message` : Message affiché dans l'état "no-data"

**Événements :**
- `@edit-item` : Émis quand l'utilisateur clique sur le bouton d'édition
- `@remove-item` : Émis quand l'utilisateur clique sur le bouton de suppression

```vue
<template>
  <MTable
    :columns="columns"
    :fetch-function="fetchUsers"
    :filters="['role', 'status']"
    :limit-options="[10, 20, 50, 100]"
    :show-edit-action="true"
    :show-remove-action="true"
    no-data-icon="Users"
    no-data-title="Aucun utilisateur"
    @edit-item="handleEdit"
    @remove-item="handleRemove"
  >
    <!-- Personnaliser le rendu d'une colonne -->
    <template v-slot:body-cell-roles="{ row }">
      <q-td>
        <MChip v-for="role in row.roles" :key="role">{{ role }}</MChip>
      </q-td>
    </template>
  </MTable>
</template>

<script setup lang="ts">
import { MTable } from '@lib-improba/components/mastok';
import { FetchFn } from '@lib-improba/utils/table-types.utils';
import { QTableColumn } from 'quasar';

const columns: QTableColumn[] = [
  { name: 'id', label: 'ID', field: 'id', sortable: true },
  { name: 'name', label: 'Nom', field: 'name', sortable: true },
  { name: 'roles', label: 'Rôles', field: 'roles', sortable: false },
];

const fetchUsers: FetchFn<User> = async (pagination, filters) => {
  const response = await UserService.paginate({
    ...pagination,
    ...filters,
  });
  return {
    results: response.data,
    count: response.total,
  };
};
</script>
```

**Méthodes exposées :**
- `refresh()` : Rafraîchit les données de la table

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { MTable } from '@lib-improba/components/mastok';

const tableRef = ref<InstanceType<typeof MTable> | null>(null);

const refreshTable = () => {
  tableRef.value?.refresh();
};
</script>
```

### MFilterTable
Table complète avec barre de recherche, filtres et boutons d'action.

**Props principales :**
- `columns` (requis) : Définitions des colonnes (format Quasar QTableColumn[])
- `fetch-function` (requis) : Fonction asynchrone pour récupérer les données
- `title` : Titre affiché en haut du composant
- `searchable` : Activer la fonctionnalité de recherche (défaut: `true`)
- `search-placeholder` : Placeholder pour l'input de recherche (défaut: `'Rechercher...'`)
- `query-prefix` : Préfixe pour les query params (utile pour plusieurs tables sur la même page)
- `filters` : Liste des noms de filtres à synchroniser avec l'URL
- `show-filters-button` : Afficher le bouton "Filtres" (défaut: `true`)
- `add-button-label` : Label du bouton "Ajouter" (le bouton est affiché si cette prop est fournie)
- `show-edit-action` : Afficher le bouton d'édition (défaut: `true`)
- `show-remove-action` : Afficher le bouton de suppression (défaut: `true`)
- `no-data-icon`, `no-data-title`, `no-data-message` : Personnalisation de l'état "no-data"

**Événements :**
- `@add-item` : Émis quand l'utilisateur clique sur le bouton "Ajouter"
- `@edit-item` : Émis quand l'utilisateur clique sur le bouton d'édition
- `@remove-item` : Émis quand l'utilisateur clique sur le bouton de suppression

```vue
<template>
  <MFilterTable
    title="Gestion des utilisateurs"
    :columns="columns"
    :fetch-function="fetchUsers"
    add-button-label="Ajouter un utilisateur"
    :filters="['role', 'status']"
    @add-item="showAddModal = true"
    @edit-item="handleEdit"
    @remove-item="handleRemove"
  >
    <!-- Personnaliser le rendu d'une colonne -->
    <template v-slot:body-cell-roles="{ row }">
      <q-td>
        <MChip
          v-for="role in row.roles"
          :key="role"
          primary
          dense
        >
          {{ role }}
        </MChip>
      </q-td>
    </template>
  </MFilterTable>
</template>

<script setup lang="ts">
import { MFilterTable } from '@lib-improba/components/mastok';
import { FetchFn } from '@lib-improba/utils/table-types.utils';
import { ref } from 'vue';

const showAddModal = ref(false);

const fetchUsers: FetchFn<User> = async (pagination, filters) => {
  // La recherche est automatiquement dans filters['q']
  const response = await UserService.paginate({
    ...pagination,
    q: filters.q, // Recherche textuelle
    ...filters,
  });
  return { results: response.data, count: response.total };
};
</script>
```

**Utilisation avec préfixe de query params** (pour plusieurs tables sur la même page) :

```vue
<template>
  <div class="row q-gutter-md">
    <!-- Table des utilisateurs avec préfixe 'users' -->
    <div class="col-6">
      <MFilterTable
        title="Utilisateurs"
        query-prefix="users"
        :columns="userColumns"
        :fetch-function="fetchUsers"
        :filters="['role', 'status']"
      />
    </div>
    
    <!-- Table des produits avec préfixe 'products' -->
    <div class="col-6">
      <MFilterTable
        title="Produits"
        query-prefix="products"
        :columns="productColumns"
        :fetch-function="fetchProducts"
        :filters="['category', 'status']"
      />
    </div>
  </div>
</template>
```

**Méthodes exposées :**
- `refresh()` : Rafraîchit les données de la table

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { MFilterTable } from '@lib-improba/components/mastok';

const filterTableRef = ref<InstanceType<typeof MFilterTable> | null>(null);

const refreshTable = () => {
  filterTableRef.value?.refresh();
};
</script>
```

## 🔧 Utilisation

### Import

```typescript
// Composants de base
import { MBtn, MCard, MDialog, Lucide } from '@lib-improba/components/mastok';

// Composants de table
import { MInput, MTable, MFilterTable } from '@lib-improba/components/mastok';

// Types pour les tables
import { FetchFn } from '@lib-improba/utils/table-types.utils';
```

### Props communes

La plupart des composants Mastok partagent les mêmes props de couleur :

- `primary` : Variante principale (défaut)
- `secondary` : Variante secondaire
- `tertiary` : Variante tertiaire
- `light` : Variante claire
- `danger` : Variante danger
- `success` : Variante succès
- `warning` : Variante avertissement
- `flat` : Style plat (sans fond)
- `lucideIcon` : Nom de l'icône Lucide à afficher

### Exemple complet

```vue
<template>
  <MPage :padding="true">
    <MCard title="Gestion des utilisateurs" description="Créez et gérez les utilisateurs">
      <template #content>
        <div class="column q-gutter-md">
          <MBtn primary lucideIcon="user-plus">Ajouter un utilisateur</MBtn>
          <MBtn secondary lucideIcon="edit">Modifier</MBtn>
          <MBtn danger flat lucideIcon="trash">Supprimer</MBtn>
        </div>
      </template>
      <template #actions>
        <MChip success>Actif</MChip>
        <MChip warning>En attente</MChip>
      </template>
    </MCard>
  </MPage>
</template>

<script setup lang="ts">
import { MBtn, MCard, MChip, MPage } from '@lib-improba/components/mastok';
</script>
```

### Exemple avec table

```vue
<template>
  <MPage :padding="true">
    <MFilterTable
      title="Liste des utilisateurs"
      :columns="columns"
      :fetch-function="fetchUsers"
      add-button-label="Ajouter un utilisateur"
      :filters="['role', 'status']"
      @add-item="showAddModal = true"
      @edit-item="handleEdit"
      @remove-item="handleRemove"
    >
      <template v-slot:body-cell-roles="{ row }">
        <q-td>
          <MChip
            v-for="role in row.roles"
            :key="role"
            primary
            dense
          >
            {{ role }}
          </MChip>
        </q-td>
      </template>
    </MFilterTable>
  </MPage>
</template>

<script setup lang="ts">
import { MFilterTable, MChip, MPage } from '@lib-improba/components/mastok';
import { FetchFn } from '@lib-improba/utils/table-types.utils';
import { QTableColumn } from 'quasar';
import { ref } from 'vue';
import { UserService } from '@services/users';

const showAddModal = ref(false);

const columns: QTableColumn[] = [
  { name: 'id', label: 'ID', field: 'id', sortable: true },
  { name: 'name', label: 'Nom', field: 'name', sortable: true },
  { name: 'email', label: 'Email', field: 'email', sortable: true },
  { name: 'roles', label: 'Rôles', field: 'roles', sortable: false },
];

const fetchUsers: FetchFn<User> = async (pagination, filters) => {
  const response = await UserService.paginate({
    ...pagination,
    q: filters.q, // Recherche textuelle
    ...filters,
  });
  return {
    results: response.data,
    count: response.total,
  };
};

const handleEdit = (user: User) => {
  console.log('Edit user:', user);
};

const handleRemove = (user: User) => {
  console.log('Remove user:', user);
};
</script>
```

## 🎨 Style et thème

Les composants Mastok utilisent :
- Les classes Anubis pour les couleurs (`bg-primary`, `text-primary`, etc.)
- La classe `smooth` pour les transitions fluides
- Les bordures arrondies (`rounded`, `rounded-md`)
- Aucune ombre par défaut (`shadow-none`)

## 🔧 Utilitaires pour les tables

Les composants de table utilisent des utilitaires disponibles dans `@lib-improba/utils/` :

### Types

```typescript
import { FetchFn, TablePagination } from '@lib-improba/utils/table-types.utils';

// FetchFn est le type de la fonction de récupération des données
const fetchFunction: FetchFn<User> = async (pagination, filters) => {
  // pagination contient : limit, offset, orderBy, order
  // filters contient les filtres synchronisés avec l'URL
  const response = await UserService.paginate({
    ...pagination,
    ...filters,
  });
  return {
    results: response.data,
    count: response.total,
  };
};
```

### Query Parameters

```typescript
import {
  useSingleQueryParam,
  useManyQueryParams,
  NUMBER_PARSER,
  NUMBER_SERIALIZER,
} from '@lib-improba/utils/table-query-params.utils';

// Gérer un seul paramètre URL
const searchQuery = useSingleQueryParam<string>('q');
searchQuery.value = 'test'; // Met à jour l'URL automatiquement

// Gérer plusieurs paramètres URL
const { filters } = useManyQueryParams(['role', 'status']);
filters.role = 'admin'; // Met à jour ?role=admin automatiquement

// Avec parser/serializer personnalisés
const page = useSingleQueryParam<number>('page', {
  parse: NUMBER_PARSER,
  serialize: NUMBER_SERIALIZER,
});
```

## 📝 Notes importantes

- **Toujours utiliser les composants Mastok** au lieu des composants Quasar directs pour maintenir la cohérence visuelle
- **Utiliser les couleurs Anubis** via les props Mastok plutôt que les props `color` de Quasar
- **Les composants de `lib-improba/components/app/` sont dépréciés** - utiliser Mastok à la place
- **MPage remplace DPage** - utiliser MPage dans les nouveaux développements
- **Les tables synchronisent automatiquement** la pagination, le tri et les filtres avec l'URL pour permettre le partage d'URLs et la navigation navigateur
- **Utiliser `queryPrefix`** quand plusieurs tables sont sur la même page pour éviter les conflits de query params

## 🔗 Voir aussi

- [Documentation Anubis UI](../../../docs/anubis-ui.md) - Guide du système de couleurs Anubis
- [Architecture du projet](../../../docs/architecture.md) - Vue d'ensemble de l'architecture

