import {
  ref,
  watch,
  reactive,
  type Ref,
  onUnmounted,
  UnwrapNestedRefs,
} from 'vue';
import { useRouter, type Router, type LocationQueryValue } from 'vue-router';

// ============================================================================
// Types
// ============================================================================

/**
 * Parser function type that converts a URL query string to type T.
 * Receives null when the query parameter is not present in the URL.
 *
 * @param value - The raw string value from the URL query parameter (or null if not present)
 * @returns The parsed value of type T
 *
 * @example
 * ```ts
 * const numberParser: SingleQueryParamParser<number> = (value) => {
 *   return value ? parseInt(value, 10) : 0;
 * };
 * ```
 */
export type SingleQueryParamParser<T> = (value: string | null) => T;

/**
 * Serializer function type that converts type T to a URL query string.
 * Should return null to remove the parameter from the URL.
 *
 * @param value - The value to serialize
 * @returns The serialized string (or null to remove from URL)
 *
 * @example
 * ```ts
 * const numberSerializer: SingleQueryParamSerializer<number> = (value) => {
 *   return String(value);
 * };
 * ```
 */
export type SingleQueryParamSerializer<T> = (value: T) => string | null;

// ============================================================================
// Built-in Parsers & Serializers
// ============================================================================

/**
 * Parser for number values.
 * Returns 0 if the value cannot be parsed as a number.
 *
 * @example
 * ```ts
 * const page = useSingleQueryParam<number>('page', {
 *   parse: NUMBER_PARSER,
 *   serialize: NUMBER_SERIALIZER
 * });
 * ```
 */
export const NUMBER_PARSER: SingleQueryParamParser<number> = (value) => {
  if (!value) return 0;
  const parsed = parseInt(value, 10);
  return isNaN(parsed) ? 0 : parsed;
};

/**
 * Serializer for number values.
 * Converts numbers to strings.
 */
export const NUMBER_SERIALIZER: SingleQueryParamSerializer<number> = (
  value
) => {
  return String(value);
};

/**
 * Parser for boolean values.
 * Treats 'true', '1', and non-empty strings as true, everything else as false.
 *
 * @example
 * ```ts
 * const showArchived = useSingleQueryParam<boolean>('archived', {
 *   parse: BOOLEAN_PARSER,
 *   serialize: BOOLEAN_SERIALIZER
 * });
 * ```
 */
export const BOOLEAN_PARSER: SingleQueryParamParser<boolean> = (value) => {
  if (!value) return false;
  return value === 'true' || value === '1';
};

/**
 * Serializer for boolean values.
 * Converts true to 'true' and false to 'false'.
 */
export const BOOLEAN_SERIALIZER: SingleQueryParamSerializer<boolean> = (
  value
) => {
  return value ? 'true' : 'false';
};

/**
 * Creates a parser for array values with a custom separator.
 * Splits the string by the separator and filters out empty strings.
 *
 * @param separator - The separator to use for splitting (default: ',')
 * @returns A parser function for string arrays
 *
 * @example
 * ```ts
 * // Comma-separated tags: ?tags=vue,typescript,quasar
 * const tags = useSingleQueryParam<string[]>('tags', {
 *   parse: ARRAY_PARSER,
 *   serialize: ARRAY_SERIALIZER
 * });
 *
 * // Slash-separated path: ?path=users/admin/settings
 * const path = useSingleQueryParam<string[]>('path', {
 *   parse: ARRAY_PARSER('/'),
 *   serialize: ARRAY_SERIALIZER('/')
 * });
 * ```
 */
export function ARRAY_PARSER(
  separator = ','
): SingleQueryParamParser<string[]> {
  return (value) => {
    if (!value) return [];
    return value.split(separator).filter((s) => s.trim() !== '');
  };
}

/**
 * Creates a serializer for array values with a custom separator.
 * Joins the array elements with the separator.
 * Returns null for empty arrays (removes parameter from URL).
 *
 * @param separator - The separator to use for joining (default: ',')
 * @returns A serializer function for string arrays
 */
export function ARRAY_SERIALIZER(
  separator = ','
): SingleQueryParamSerializer<string[]> {
  return (value) => {
    if (!value || value.length === 0) return null;
    return value.join(separator);
  };
}

/**
 * Options for configuring a single query parameter
 */
interface UseSingleQueryParamOptions<T> {
  /**
   * Custom parser function to convert URL string to type T
   * If not provided, treats values as strings
   */
  parse?: SingleQueryParamParser<T>;

  /**
   * Custom serializer function to convert type T to URL string
   * If not provided, uses String() conversion
   */
  serialize?: SingleQueryParamSerializer<T>;

  /**
   * Custom router instance (optional, will use useRouter() if not provided)
   */
  router?: Router;

  /**
   * Replace history instead of push when updating URL
   * @default true
   */
  replace?: boolean;
}

// ============================================================================
// Composable
// ============================================================================

/**
 * Modern, type-safe composable for managing a single URL query parameter
 * with automatic synchronization between the URL and a reactive ref.
 *
 * @param name - The name of the query parameter
 * @param options - Configuration options including optional parse/serialize callbacks
 * @returns A reactive ref that syncs with the URL query parameter
 *
 * @example
 * ```ts
 * // String parameter (no parser needed, defaults to string)
 * const search = useSingleQueryParam<string>('q');
 * search.value = 'hello'; // Updates URL to ?q=hello
 *
 * // Number parameter with built-in parsers
 * const page = useSingleQueryParam<number>('page', {
 *   parse: NUMBER_PARSER,
 *   serialize: NUMBER_SERIALIZER
 * });
 * page.value = 2; // Updates URL to ?page=2
 *
 * // Boolean parameter with built-in parsers
 * const showArchived = useSingleQueryParam<boolean>('archived', {
 *   parse: BOOLEAN_PARSER,
 *   serialize: BOOLEAN_SERIALIZER
 * });
 * showArchived.value = true; // Updates URL to ?archived=true
 *
 * // Array parameter with comma separator (default)
 * const tags = useSingleQueryParam<string[]>('tags', {
 *   parse: ARRAY_PARSER,
 *   serialize: ARRAY_SERIALIZER
 * });
 * tags.value = ['vue', 'typescript']; // Updates URL to ?tags=vue,typescript
 *
 * // Array parameter with custom separator
 * const path = useSingleQueryParam<string[]>('path', {
 *   parse: ARRAY_PARSER('/'),
 *   serialize: ARRAY_SERIALIZER('/')
 * });
 * path.value = ['users', 'admin', 'settings']; // Updates URL to ?path=users/admin/settings
 *
 * // Custom parser and serializer
 * const customValue = useSingleQueryParam<Date | null>('date', {
 *   parse: (v) => v ? new Date(v) : null,
 *   serialize: (v) => v ? v.toISOString() : null
 * });
 * ```
 */
export function useSingleQueryParam<T = string>(
  name: string,
  options: UseSingleQueryParamOptions<T> = {}
): Ref<T | null> {
  const { parse, serialize, router: customRouter, replace = true } = options;

  const router = customRouter ?? useRouter();

  // Default parser: extract string from query value
  const defaultParse = (
    value: LocationQueryValue | LocationQueryValue[]
  ): string | null => {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return Array.isArray(value) ? value[0] ?? null : value;
  };

  // Default serializer: convert to string
  const defaultSerialize = (value: T): string | null => {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return String(value);
  };

  // Parse initial value from URL
  const rawValue = router.currentRoute.value.query[name];
  const stringValue = defaultParse(rawValue);
  const initialValue = parse ? parse(stringValue) : (stringValue as T);

  // Create reactive ref
  const paramValue = ref<T | null>(initialValue) as Ref<T | null>;

  // Flag to prevent infinite loops when syncing URL -> ref
  let isUpdatingFromUrl = false;

  // Watch for changes in the ref and update URL
  const stopValueWatcher = watch(
    paramValue,
    async (newValue) => {
      // Skip if we're updating from URL to prevent loop
      if (isUpdatingFromUrl) return;

      const serialized = serialize
        ? serialize(newValue as T)
        : defaultSerialize(newValue as T);

      const query = { ...router.currentRoute.value.query };

      if (serialized === null || serialized === '') {
        // Remove parameter from URL if value is null/empty
        delete query[name];
      } else {
        // Update parameter in URL
        query[name] = serialized;
      }

      const routeUpdate = {
        query,
        hash: router.currentRoute.value.hash,
      };

      // Update URL (replace by default to avoid polluting history)
      if (replace) {
        await router.replace(routeUpdate);
      } else {
        await router.push(routeUpdate);
      }
    },
    { deep: true }
  );

  // Watch for changes in URL and update ref
  const stopUrlWatcher = watch(
    () => router.currentRoute.value.query[name],
    (newQueryValue) => {
      isUpdatingFromUrl = true;

      const stringValue = defaultParse(newQueryValue);
      const parsed = parse ? parse(stringValue) : (stringValue as T);

      // Only update if value actually changed
      if (JSON.stringify(parsed) !== JSON.stringify(paramValue.value)) {
        paramValue.value = parsed;
      }

      isUpdatingFromUrl = false;
    }
  );

  // Cleanup watchers on unmount to prevent memory leaks
  onUnmounted(() => {
    stopValueWatcher();
    stopUrlWatcher();
  });

  return paramValue;
}

/**
 * Methods returned by useManyQueryParams
 */
export interface IUseManyQueryParamsMethods {
  /**
   * Clears all query parameters managed by this composable
   * @param replace - Whether to replace history instead of push (default: true)
   */
  clearAllQueryParams: (replace?: boolean) => Promise<void>;
}

/**
 * Return type of useManyQueryParams composable
 */
export interface IUseManyQueryParams<T> {
  filters: UnwrapNestedRefs<T>;
  methods: IUseManyQueryParamsMethods;
}

interface IUseManyQueryParamsOptions {
  replace?: boolean;
  router?: Router;
}

/**
 * Modern composable for managing multiple URL query parameters at once.
 * All parameters are treated as strings by default.
 * Returns an object with state (filters) and methods (clearAllQueryParams).
 *
 * @param filterNames - Array of parameter names to manage
 * @param options - Additional options (replace, router)
 * @returns Object with reactive filters state and utility methods
 *
 * @example
 * ```ts
 * const { filters, methods } = useManyQueryParams(['search', 'status', 'page']);
 *
 * // Update a filter (automatically updates URL)
 * filters.search = 'hello';
 * filters.page = '2';
 *
 * // Clear all query params
 * await methods.clearAllQueryParams();
 * ```
 */
export function useManyQueryParams<T extends Record<string, string | null>>(
  filterNames: string[],
  options: IUseManyQueryParamsOptions = {}
): IUseManyQueryParams<T> {
  const { replace = true, router: customRouter } = options;
  const router = customRouter ?? useRouter();

  // Initialize state from URL
  const state = reactive({} as T);

  // Parse initial values for each parameter (as strings)
  for (const name of filterNames) {
    const queryValue = router.currentRoute.value.query[name];
    (state as any)[name] = Array.isArray(queryValue)
      ? queryValue[0] ?? null
      : queryValue ?? null;
  }

  // Flag to prevent infinite loops when syncing URL -> state
  let isUpdatingFromUrl = false;

  // Watch state changes and update URL
  const stopStateWatcher = watch(
    state,
    async () => {
      if (isUpdatingFromUrl) return;

      const query = { ...router.currentRoute.value.query };

      // Update query for each parameter
      for (const name of filterNames) {
        const value = (state as any)[name];

        if (value === null || value === undefined || value === '') {
          delete query[name];
        } else {
          query[name] = String(value);
        }
      }

      const routeUpdate = {
        query,
        hash: router.currentRoute.value.hash,
      };

      if (replace) {
        await router.replace(routeUpdate);
      } else {
        await router.push(routeUpdate);
      }
    },
    { deep: true }
  );

  // Watch URL changes and update state
  const stopUrlWatcher = watch(
    () => router.currentRoute.value.query,
    (newQuery) => {
      isUpdatingFromUrl = true;

      for (const name of filterNames) {
        const queryValue = newQuery[name];
        const parsedValue = Array.isArray(queryValue)
          ? queryValue[0] ?? null
          : queryValue ?? null;

        if (parsedValue !== (state as any)[name]) {
          (state as any)[name] = parsedValue;
        }
      }

      isUpdatingFromUrl = false;
    }
  );

  // Cleanup watchers on unmount to prevent memory leaks
  onUnmounted(() => {
    console.log('useManyQueryParams: removing watchers');
    stopStateWatcher();
    stopUrlWatcher();
  });

  // Methods object
  const methods: IUseManyQueryParamsMethods = {
    /**
     * Clears all query parameters managed by this composable
     */
    clearAllQueryParams: async (replaceHistory = true) => {
      const query = { ...router.currentRoute.value.query };

      for (const name of filterNames) {
        delete query[name];
      }

      const routeUpdate = {
        query,
        hash: router.currentRoute.value.hash,
      };

      if (replaceHistory) {
        await router.replace(routeUpdate);
      } else {
        await router.push(routeUpdate);
      }
    },
  };

  return {
    filters: state,
    methods,
  };
}

