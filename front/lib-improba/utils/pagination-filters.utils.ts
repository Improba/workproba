import type { CommonPrimitives } from './type-aliases.utils';

/**
 * Force selection 'all' filter :
 * - if incoming values are empty
 * - or, if user has selected 'all' filter explicitly
 */
export const checkIfCanRemoveFilters = <
  T extends Record<string, string>[],
  U extends Record<string, string>[]
>(
  currentState: T,
  childState: U
): boolean => {
  const selectHasAllFilter = childState.find((e) => e.value === 'all');
  const selectHasOnlyAllFilter = selectHasAllFilter && childState.length === 1;
  if (selectHasOnlyAllFilter) return true;

  const stateHasFiltersExceptAllFilter = currentState.find(
    (e) => e.value !== 'all'
  );

  const forceSelectionOfAllFilter =
    childState.length === 0 ||
    (!!selectHasAllFilter && !!stateHasFiltersExceptAllFilter);

  return forceSelectionOfAllFilter;
};

export type ISelectOption<T extends CommonPrimitives = string> = {
  label: string;
  value: T;
};

export type IDateSelectOption<T extends CommonPrimitives = string> =
  ISelectOption<T> & {
    minDate: () => Date | undefined;
    maxDate: () => Date | undefined;
  };
