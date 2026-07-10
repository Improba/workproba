/**
 * Sorts an array of Object by one property, alphabetically
 */
export const sortArray = <T extends any[]>(array: T, prop: string): T =>
  array.sort((a, b) => (a[prop] > b[prop] ? 1 : a[prop] < b[prop] ? -1 : 0));

/**
 * Removes duplicates, if present
 */
export const removeDuplicates = <T extends unknown>(target: T[]): T[] => [
  ...new Set(target),
];

export const sum = (array: number[]): number =>
  array.reduce((a, b) => a + b, 0);

export const average = (array: number[]): number => sum(array) / array.length;

export const mergeObjectsArrayInSingleObject = <
  T extends Record<string, unknown>,
>(
  finalObject: T,
  currentObject: T,
): T => Object.assign(finalObject, currentObject);

export const arrayToObject = (array: string[]): { [key: string]: boolean } => {
  return array.reduce((acc: any, curr: any) => ((acc[curr] = true), acc), {});
};
