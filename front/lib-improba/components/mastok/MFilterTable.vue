<!--
  Composant MFilterTable - Table complète avec recherche et filtres Mastok
  
  Ce composant combine MTable avec une barre de recherche et des boutons d'action.
  Il gère automatiquement la synchronisation de la recherche avec les paramètres URL
  et permet d'ajouter un préfixe aux paramètres pour éviter les conflits entre
  plusieurs tables sur la même page.
  
  Fonctionnalités :
  - Barre de recherche avec synchronisation URL automatique
  - Bouton "Filtres" pour ouvrir un panneau de filtres avancés (à implémenter)
  - Bouton "Ajouter" avec icône Lucide
  - Titre optionnel
  - Préfixe de query params pour éviter les conflits
  - Tous les slots de MTable sont supportés
  
  Utilisation basique :
  ```vue
  <template>
    <MFilterTable
      title="Gestion des utilisateurs"
      :columns="columns"
      :fetch-function="fetchUsers"
      add-button-label="Ajouter un utilisateur"
      @add-item="showAddModal = true"
      @edit-item="handleEdit"
      @remove-item="handleRemove"
    />
  </template>
  
  <script setup lang="ts">
  import { MFilterTable } from '@lib-improba/components/mastok';
  import { FetchFn } from '@lib-improba/utils/table-types.utils';
  import { ref } from 'vue';
  
  const showAddModal = ref(false);
  
  const fetchUsers: FetchFn<User> = async (pagination, filters) => {
    // La recherche est automatiquement dans filters['q'] ou filters['users-q']
    const response = await UserService.paginate({
      ...pagination,
      q: filters.q, // Recherche textuelle
      ...filters,
    });
    return { results: response.data, count: response.total };
  };
  
  const handleEdit = (user: User) => { /* ... */ };
  const handleRemove = (user: User) => { /* ... */ };
  </script>
  ```
  
  Utilisation avec préfixe de query params (pour plusieurs tables sur la même page) :
  ```vue
  <template>
    <div class="row q-gutter-md">
      <div class="col-6">
        <MFilterTable
          title="Utilisateurs"
          query-prefix="users"
          :columns="userColumns"
          :fetch-function="fetchUsers"
          :filters="['role', 'status']"
          add-button-label="Ajouter un utilisateur"
        />
      </div>
      
      <div class="col-6">
        <MFilterTable
          title="Produits"
          query-prefix="products"
          :columns="productColumns"
          :fetch-function="fetchProducts"
          :filters="['category', 'status']"
          add-button-label="Ajouter un produit"
        />
      </div>
    </div>
  </template>
  
  <script setup lang="ts">
  // Les query params seront :
  // - users-q, users-role, users-status pour la première table
  // - products-q, products-category, products-status pour la seconde table
  </script>
  ```
  
  Personnalisation des colonnes avec slots :
  ```vue
  <template>
    <MFilterTable
      :columns="columns"
      :fetch-function="fetchUsers"
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
      
      <template v-slot:body-cell-status="{ row }">
        <q-td>
          <MChip :primary="row.status === 'active'" :danger="row.status === 'inactive'">
            {{ row.status }}
          </MChip>
        </q-td>
      </template>
    </MFilterTable>
  </template>
  ```
  
  Méthodes exposées :
  - `refresh()` : Rafraîchit les données de la table
  
  ```vue
  <script setup lang="ts">
  import { ref } from 'vue';
  import { MFilterTable } from '@lib-improba/components/mastok';
  
  const filterTableRef = ref<InstanceType<typeof MFilterTable> | null>(null);
  
  const refreshTable = () => {
    filterTableRef.value?.refresh();
  };
  
  // Après une création/modification
  const handleUserCreated = () => {
    refreshTable();
  };
  </script>
  ```
-->
<template>
  <div class="column full-height full-width">
    <!-- Header -->
    <div v-if="title" class="text-primary-high heading-medium q-mb-lg">
      {{ title }}
    </div>

    <!-- Search/Filter Bar -->
    <div class="flex items-center justify-between gap-x-3 q-mb-md">
      <!-- Left side: Filters and Sort buttons -->
      <div class="flex gap-x-2">
        <MBtn
          v-if="showFiltersButton"
          light
          flat
          padding="8px 12px"
        >
          <div class="flex items-center gap-x-2">
            <Lucide name="Filter" size="16" color="neutral-higher" />
            <span>Filtres</span>
          </div>
        </MBtn>
      </div>

      <!-- Right side: Search input + Action button -->
      <div class="flex items-center gap-x-3">
        <MInput
          v-if="searchable"
          v-model="searchParam"
          type="search"
          :placeholder="searchPlaceholder"
          autocomplete="off"
        />

        <MBtn
          v-if="addButtonLabel"
          @click="emit('add-item')"
          light
          flat
          class="q-ml-md"
        >
          <div class="flex items-center gap-x-2">
            <Lucide name="Plus" size="16" color="neutral-bg-primary" />
            <span>{{ addButtonLabel }}</span>
          </div>
        </MBtn>
      </div>
    </div>

    <!-- Main Content - Takes all available space -->
    <div class="col-grow q-pb-md" style="overflow-y: auto">
      <MTable
        ref="tableRef"
        :columns="columns"
        :fetch-function="fetchFunction"
        :filters="filtersConfig"
        :show-edit-action="showEditAction"
        :show-remove-action="showRemoveAction"
        :no-data-icon="noDataIcon"
        :no-data-title="noDataTitle"
        :no-data-message="noDataMessage"
        @edit-item="emit('edit-item', $event)"
        @remove-item="emit('remove-item', $event)"
      >
        <!-- Forward all slots to Table component -->
        <template
          v-for="(_, name) in $slots"
          v-slot:[name]="slotProps"
          :key="name"
        >
          <slot :name="name" v-bind="slotProps" />
        </template>
      </MTable>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { QTableColumn } from 'quasar';
import { FetchFn } from '@lib-improba/utils/table-types.utils';
import MTable from './MTable.vue';
import MInput from './MInput.vue';
import MBtn from './MBtn.vue';
import Lucide from './Lucide.vue';
import { useSingleQueryParam } from '@lib-improba/utils/table-query-params.utils';

// =======================
// Props Definition
// =======================
/**
 * Props du composant MFilterTable
 */
interface Props {
  /** Titre affiché en haut du composant */
  title?: string;

  /** Définitions des colonnes de la table (format Quasar QTableColumn) */
  columns: QTableColumn[];

  /**
   * Fonction asynchrone pour récupérer les données avec pagination et filtres.
   * La recherche sera automatiquement disponible dans filters['q'] ou filters[`${queryPrefix}-q`]
   * 
   * @example
   * ```ts
   * const fetchFunction: FetchFn<User> = async (pagination, filters) => {
   *   const searchQuery = filters.q || filters['users-q']; // selon queryPrefix
   *   return await UserService.paginate({
   *     ...pagination,
   *     q: searchQuery,
   *     ...filters,
   *   });
   * };
   * ```
   */
  fetchFunction: FetchFn<any>;

  /** Activer la fonctionnalité de recherche */
  searchable?: boolean;

  /**
   * Préfixe à appliquer à tous les query params pour éviter les conflits.
   * Par exemple, avec queryPrefix="users", les params seront :
   * - users-q (recherche)
   * - users-role, users-status (filtres)
   * 
   * Utile quand plusieurs tables sont sur la même page.
   * 
   * @example
   * ```ts
   * // Sans préfixe : ?q=test&role=admin
   * <MFilterTable :filters="['role']" />
   * 
   * // Avec préfixe : ?users-q=test&users-role=admin
   * <MFilterTable query-prefix="users" :filters="['role']" />
   * ```
   */
  queryPrefix?: string;

  /** Texte du placeholder pour l'input de recherche */
  searchPlaceholder?: string;

  /** Afficher le bouton "Filtres" (pour ouvrir un panneau de filtres avancés) */
  showFiltersButton?: boolean;

  /**
   * Label du bouton "Ajouter" (le bouton est affiché si cette prop est fournie).
   * Le bouton émet l'événement 'add-item' au clic.
   */
  addButtonLabel?: string;

  /** Afficher le bouton d'édition dans la colonne actions */
  showEditAction?: boolean;

  /** Afficher le bouton de suppression dans la colonne actions */
  showRemoveAction?: boolean;

  /**
   * Liste des noms de filtres à synchroniser avec les paramètres URL.
   * Ces filtres seront automatiquement préfixés si queryPrefix est défini.
   * 
   * @example
   * ```ts
   * // Avec queryPrefix="users" et filters="['role', 'status']"
   * // Les query params seront : users-role et users-status
   * :filters="['role', 'status']"
   * ```
   */
  filters?: string[];

  /** Nom de l'icône Lucide affichée dans l'état "no-data" */
  noDataIcon?: string;

  /** Titre affiché dans l'état "no-data" */
  noDataTitle?: string;

  /** Message affiché dans l'état "no-data" */
  noDataMessage?: string;
}

const props = withDefaults(defineProps<Props>(), {
  // Search
  searchable: true,
  searchPlaceholder: 'Rechercher...',

  showFiltersButton: true,
  filters: () => [],

  // Actions
  showEditAction: true,
  showRemoveAction: true,
});

// =======================
// Emits Definition
// =======================
const emit = defineEmits<{
  'add-item': [];
  'edit-item': [row: any];
  'remove-item': [row: any];
}>();

// =======================
// Table Reference
// =======================
const tableRef = ref<InstanceType<typeof MTable> | null>(null);

// =======================
// Search Management
// =======================
const searchParamName = computed(() =>
  props.queryPrefix ? `${props.queryPrefix}-q` : 'q'
);

const searchParam = useSingleQueryParam(searchParamName.value);

// =======================
// Filters Management
// =======================
const filtersConfig = computed(() => {
  // Apply prefix to all filter names if queryPrefix is provided
  const prefixedFilters = props.queryPrefix
    ? props.filters.map((filter) => `${props.queryPrefix}-${filter}`)
    : props.filters;

  return [...prefixedFilters, searchParamName.value];
});

// =======================
// Public Methods
// =======================
defineExpose({
  refresh: () => tableRef.value?.refresh(),
});
</script>

