import { useRouter } from 'vue-router';
import { useQueryParams } from './use-query-params';
import { defineComponent, onMounted, onUnmounted, reactive, watch } from 'vue';

/**
 * Automatically deal with the use of filter values in the URL.
 * You must provide the names of the filters you want to use as input.
 * To access a filter value, use queryParamSearch.state.filterValues[filterName].
 *
 * @param filterNames The names of the filter to use (string[]).
 */
export const useQueryParamSearch = (filterNames: string[]) => {
  const router = useRouter();
  const queryParams = useQueryParams(router);

  const state = reactive({
    loading: false,
    filterValues: {} as {[key: string]: string | null | undefined},
  });

  const methods = {
    init: () => {
      state.loading = true;

      const filterValues: {[key: string]: string | null | undefined} = {};

      for (const filterName of filterNames) {
        const queryParamValue =
          queryParams.methods.findQueryParamValue(filterName);
        if (queryParamValue?.length) {
          filterValues[filterName] = queryParamValue as string;
        } else {
          filterValues[filterName] = null;
        }
      }

      state.filterValues = filterValues;

      state.loading = false;
    },
    clearQueryParams: () => {
      queryParams.methods.clearRouteQuery(filterNames);
    },
  };

  onMounted(() => {
    methods.init();
  });

  onUnmounted(() => {
    methods.clearQueryParams();
  });

  watch(
    () => state.filterValues,
    (newValues) => {
      const toBeCleared: string[] = [];
      const toUpdate: {[key: string]: string} = {};

      for (const filterName of filterNames) {
        const newValue = newValues[filterName];

        const queryParamValue =
          queryParams.methods.findQueryParamValue(filterName);
        if (queryParamValue !== newValue) {
          if (
            newValue === null ||
            newValue === undefined ||
            newValue.length === 0
          ) {
            toBeCleared.push(filterName);
          } else {
            toUpdate[filterName] = newValue;
          }
        }
      }

      if (toBeCleared.length) {
        queryParams.methods.clearRouteQuery(toBeCleared);
      }
      if (Object.keys(toUpdate).length) {
        queryParams.methods.updateRouteQuery(toUpdate, true);
      }
    },
    { deep: true }
  );

  watch(
    () => router.currentRoute.value.query,
    (newValues) => {
      const toBeUpdated: {[key: string]: string} = {};
      for (const filterName of filterNames) {
        const filterValue = state.filterValues[filterName];
        const queryParamValue =
          queryParams.methods.findQueryParamValue(filterName);
        if (queryParamValue !== filterValue) {
          toBeUpdated[filterName] = queryParamValue as string;
        }
      }

      if (Object.keys(toBeUpdated).length) {
        state.filterValues = { ...toBeUpdated };
      }
    },
    { deep: true }
  );

  return {
    state,
    methods,
  }
}
