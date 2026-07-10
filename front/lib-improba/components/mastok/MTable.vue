<!--
  Composant MTable - Table Mastok avec pagination, tri et synchronisation URL
  
  Ce composant est un wrapper autour de q-table de Quasar qui ajoute :
  - Pagination automatique avec synchronisation URL
  - Tri par colonnes avec synchronisation URL
  - Gestion des filtres via query parameters
  - Actions d'édition/suppression configurables
  - État de chargement et gestion des erreurs
  - Gestion des conditions de course (race conditions)
  - État "no-data" personnalisable avec icône Lucide
  
  Le composant synchronise automatiquement la pagination, le tri et les filtres
  avec les paramètres de l'URL pour permettre le partage d'URLs et la navigation
  navigateur (précédent/suivant).
  
  Utilisation :
  <template>
    <MTable
      :columns="columns"
      :fetch-function="fetchUsers"
      :filters="['role', 'status']"
      :show-edit-action="true"
      :show-remove-action="true"
      no-data-icon="Users"
      no-data-title="Aucun utilisateur"
      no-data-message="Créez votre premier utilisateur"
      @edit-item="handleEdit"
      @remove-item="handleRemove"
    >
      <template v-slot:body-cell-roles="{ row }">
        <q-td>
          <MChip v-for="role in row.roles" :key="role">{{ role }}</MChip>
        </q-td>
      </template>
      
      <template v-slot:header="props">
        <q-tr>
          <q-th>Actions</q-th>
          <q-th v-for="col in props.cols" :key="col.name">{{ col.label }}</q-th>
        </q-tr>
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
    { name: 'email', label: 'Email', field: 'email', sortable: true },
    { name: 'roles', label: 'Rôles', field: 'roles', sortable: false },
  ];
  
  const fetchUsers: FetchFn<any> = async (pagination, filters) => {
    const response = await api.paginate({
      ...pagination,
      ...filters,
    });
    return {
      results: response.data,
      count: response.total,
    };
  };
  
  const handleEdit = (user: any) => {
    console.log('Edit user:', user);
  };
  
  const handleRemove = (user: any) => {
    console.log('Remove user:', user);
  };
  </script>
  
  Méthodes exposées :
  - `refresh()` : Rafraîchit les données de la table
  
  <script setup lang="ts">
  import { ref } from 'vue';
  import { MTable } from '@lib-improba/components/mastok';
  
  const tableRef = ref<InstanceType<typeof MTable> | null>(null);
  
  const refreshTable = () => {
    tableRef.value?.refresh();
  };
  </script>
-->
<template>
  <q-table
    row-key="id"
    :pagination-label="paginationLabel"
    :rows-per-page-options="$props.limitOptions"
    :columns="computedColumns"
    :rows="state.rows"
    v-model:pagination="state.pagination"
    v-model:selected="state.selected"
    selection="multiple"
    binary-state-sort
    :loading="state.loading"
    @request="onRequest"
    loading-label="Récupération..."
    flat
  >
    <!-- Forward all other slots to q-table -->
    <template v-for="(_, name) in $slots" v-slot:[name]="slotProps" :key="name">
      <slot :name v-bind="slotProps" />
    </template>

    <template v-slot:body-cell-actions="{ row }">
      <q-td>
        <div class="flex flex-row justify-end">
          <q-btn
            v-if="props.showEditAction"
            flat
            dense
            size="md"
            icon="mdi-pencil-outline"
            color="neutral-text-secondary"
            class="q-mr-sm"
            @click="emit('edit-item', row)"
          />
          <q-btn
            v-if="props.showRemoveAction"
            flat
            dense
            size="md"
            icon="mdi-delete-outline"
            color="red"
            @click="emit('remove-item', row)"
          />
        </div>
      </q-td>
    </template>

    <template v-slot:no-data>
      <div class="full-width q-pa-xl text-center">
        <Lucide :name="props.noDataIcon" size="48" color="neutral-text-muted" />
        <div class="text-neutral-text-primary heading-small q-mb-sm">
          {{ props.noDataTitle }}
        </div>
        <div class="text-neutral-text-secondary paragraph-small q-mb-lg">
          {{ props.noDataMessage }}
        </div>
      </div>
    </template>
  </q-table>
</template>

<script setup lang="ts">
import { reactive, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { QTableColumn } from 'quasar';
import { QTablePagination } from '@lib-improba/utils/q-table-types.utils';
import { FetchFn, TablePagination } from '@lib-improba/utils/table-types.utils';
import { useManyQueryParams } from '@lib-improba/utils/table-query-params.utils';
import { PaginationOrder } from '#types/pagination';
import Lucide from './Lucide.vue';

/**
 * Props du composant MTable
 */
interface Props {
  /** Définitions des colonnes de la table (format Quasar QTableColumn) */
  columns: QTableColumn[];

  /**
   * Options de pagination disponibles pour l'utilisateur.
   * Le nombre 0 signifie "Afficher toutes les lignes sur une page"
   * 
   * @default [10, 15, 20, 25, 50, 0]
   */
  limitOptions?: number[],

  /**
   * Fonction asynchrone pour récupérer les données avec pagination et filtres.
   * Doit retourner un objet avec { results: any[], count: number }
   * 
   * @example
   * ```ts
   * const fetchFunction: FetchFn<User> = async (pagination, filters) => {
   *   return await UserService.paginate({
   *     limit: pagination.limit,
   *     offset: pagination.offset,
   *     orderBy: pagination.orderBy,
   *     order: pagination.order,
   *     ...filters,
   *   });
   * };
   * ```
   */
  fetchFunction: FetchFn<any>;

  /** Afficher le bouton d'édition dans la colonne actions */
  showEditAction?: boolean;

  /** Afficher le bouton de suppression dans la colonne actions */
  showRemoveAction?: boolean;

  /** Nom de l'icône Lucide affichée dans l'état "no-data" */
  noDataIcon?: string;

  /** Titre affiché dans l'état "no-data" */
  noDataTitle?: string;

  /** Message affiché dans l'état "no-data" */
  noDataMessage?: string;

  /**
   * Liste des noms de filtres à synchroniser avec les paramètres URL.
   * Ces filtres seront automatiquement synchronisés avec l'URL et
   * passés à la fonction fetchFunction.
   * 
   * @example
   * ```ts
   * // Les filtres 'role' et 'status' seront synchronisés avec ?role=admin&status=active
   * :filters="['role', 'status']"
   * ```
   */
  filters?: string[];
}

const props = withDefaults(defineProps<Props>(), {
  filters: () => [],
  limitOptions: () => [10, 15, 20, 25, 50, 0 ],

  // =======
  // No Data
  // =======
  noDataIcon: 'CircleQuestionMark',
  noDataTitle: 'Aucun résultat',
  noDataMessage:
    "Utilisez le bouton d'ajout pour enregister de nouveaux éléments",
});

const emit = defineEmits<{
  'edit-item': [row: any];
  'remove-item': [row: any];
}>();

const router = useRouter();

// Create query params for filters
const { filters } = useManyQueryParams(props.filters, {
  router,
});

const cleanFilters = computed(() => {
  // Filter out null, undefined, and empty strings
  const cleaned: Record<string, any> = {};

  for (const filter of props.filters ?? []) {
    const value = filters[filter];

    if (value !== null && value !== undefined && value !== '') {
      cleaned[filter] = value;
    }
  }

  return cleaned;
});

/**
 * Computed property that adds an actions column when showActions is true
 * Hidden for GUEST users
 */
const computedColumns = computed(() => {
  // Don't show actions column for GUEST users
  if ((!props.showRemoveAction && !props.showEditAction)) {
    return props.columns;
  }

  // Check if actions column already exists to avoid duplication
  const hasActionsColumn = props.columns.some(
    (col) => col.name === 'actions' || col.field === 'actions'
  );

  if (hasActionsColumn) {
    return props.columns;
  }

  // Add actions column at the end
  const actionsColumn: QTableColumn = {
    name: 'actions',
    label: 'Actions',
    field: 'actions',
    align: 'right',
    sortable: false,
  };

  return [...props.columns, actionsColumn];
});

interface State {
  /** Current table rows data */
  rows: Record<string, unknown>[];
  /** Loading indicator for fetch operations */
  loading: boolean;
  /** Pagination and sorting state from quasar */
  pagination: QTablePagination;
  /** Incremental ID to handle race conditions between concurrent fetch requests */
  fetchId: number;
  /** Selected rows (for multi-select feature) */
  selected: Record<string, unknown>[];
}

const state = reactive<State>({
  rows: [],
  loading: false,

  pagination: {
    // By default, the pagination sorts by descending id
    sortBy: 'id',
    descending: true,

    page: 1,
    rowsPerPage: 10,

    // The presence of the 'rowsNumber' field make the q-table emit the 'request' event.
    // It represents the entities total in the database.
    rowsNumber: 0,
  },

  fetchId: 0,
  selected: [],
});

function toAPIPagination(qPagination: QTablePagination): TablePagination {
  const { sortBy, descending, page, rowsPerPage, } = qPagination;

  let offset =  0;

  if (page !== undefined) {
    offset = (page - 1) * (rowsPerPage || 0)
  }

  let order: PaginationOrder

  if (descending) {
    order = 'DESC'
  } else {
    order = 'ASC'
  }

  return {
    limit: rowsPerPage,
    offset,
    orderBy: sortBy ?? undefined,
    order: order
  }
}

function paginationLabel() {
  const rowsNumber = state.pagination.rowsNumber ?? 0
  const rowsPerPage = state.pagination.rowsPerPage ?? 1

  console.log(`${rowsNumber} / ${rowsPerPage}`)

  const pageNumber = rowsNumber / (rowsPerPage === 0 ? 1 : rowsPerPage)

  return `${state.pagination.page} sur ${Math.ceil(pageNumber)}`
}

async function fetch() {
  // Increment fetchId to handle race conditions
  // If a new fetch starts before the previous completes, the old one is discarded
  const fetchId = state.fetchId + 1;
  state.fetchId = fetchId;

  const pagination = toAPIPagination(state.pagination)

  state.loading = true;

  try {
    // Call the user provided fecth function with the pagination options and filters.
    const response = await props.fetchFunction(pagination, cleanFilters.value);

    // Check if this is still the latest fetch request (race condition handling)
    if (state.fetchId !== fetchId) {
      return;
    }

    console.log(
      `Pagination: ${JSON.stringify(
        {
          pagination,
        },
        null,
        2
      )}`
    );
    console.log(`Filters: ${JSON.stringify(cleanFilters.value, null, 2)}`);

    // Update state with fetched data
    if (response) {
      state.pagination.rowsNumber = response.count;
      state.rows = response.results;
    }
  } catch (error) {
    console.error('Error fetching table data:', error);
    state.rows = [];
    state.pagination.rowsNumber = 0;
  } finally {
    // Only update loading if this is still the latest request
    if (state.fetchId === fetchId) {
      state.loading = false;
    }
  }
}

async function onRequest({ pagination }: { pagination: QTablePagination }) {
  console.log('onRequest');

  const { page, rowsPerPage, sortBy, descending } = pagination

  // Update pagination state
  state.pagination.page = page;
  state.pagination.rowsPerPage = rowsPerPage;
  state.pagination.sortBy = sortBy;
  state.pagination.descending = descending;

  // Fetch data with new pagination/sorting parameters
  await fetch();
}

// Watch for changes in filters and refetch data
watch(
  cleanFilters,
  async () => {
    await fetch();
  }
);

// Fetch data on component mount
onMounted(() => {
  fetch();
});

defineExpose({
  refresh: async () => await fetch(),
});
</script>

