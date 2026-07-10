import { useRouter, Router } from 'vue-router';

const queryStore = {
  query: {} as {[key: string]: any},
};

export const useQueryParams = (router?: Router) => {
  // ***************************
  // Query param manipulation tools
  // ***************************

  const Router = router ?? useRouter();

  const methods = {
    findQueryParamValue: (queryParamName: string): string => {
      const value = queryStore.query[queryParamName];
      return <string>value;
    },
    updateRouteQuery: async (query: {[key: string]: any}, replace = false) => {
      queryStore.query = { ...queryStore.query, ...query };

      if (replace) {
        await Router.replace({
          path: `${window.location.pathname}`,
          query: { ...queryStore.query },
        });
      } else {
        await Router.push({
          path: `${window.location.pathname}`,
          query: { ...queryStore.query },
        });
      }
    },
    initRouteQuery: async () => {
      if (process.env.MODE === 'ssr') {
        return;
      }

      const searchParams = new URLSearchParams(window.location.search);
      // Iterating the search parameters
      const queryParams: { [key: string]: string } = {};
      for (const p of <any>searchParams) {
        queryParams[p[0]] = p[1];
      }
      await methods.updateRouteQuery(queryParams, true);
    },
    clearRouteQuery: async (params: string[], replace = false) => {
      // Before clearing the query params, we need to init the query params to reinject the most recent ones
      await methods.initRouteQuery();

      for (const param of params) {
        if (queryStore?.query && queryStore.query[param]) {
          delete queryStore.query[param];
        }
      }
      if (replace) {
        await Router.replace({
          path: `${window.location.pathname}`,
          query: { ...queryStore.query },
        });
      } else {
        await Router.push({
          path: `${window.location.pathname}`,
          query: { ...queryStore.query },
        });
      }

    },
  };

  return {
    methods,
  };
};
