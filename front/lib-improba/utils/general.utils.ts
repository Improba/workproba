export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const capitalizeFirstLetter = (string: string): string => {
  return string.charAt(0).toUpperCase() + string.slice(1);
};

export const replaceAll = (
  str: string,
  toBeReplaced: string,
  toReplaceWith: string
): string => {
  // Replace ' ' by '-'
  // toto titi => [toto,titi]
  const splittedFromToBeReplaced = str.split(toBeReplaced);
  // [toto,titi] => toto-titi
  const joinedWithToReplaceWith = splittedFromToBeReplaced.join(toReplaceWith);

  return joinedWithToReplaceWith;
};

/**
 * Performs a deep merge of objects and returns new object. Does not modify
 * objects (immutable) and merges arrays via concatenation.
 * https://stackoverflow.com/questions/27936772/how-to-deep-merge-instead-of-shallow-merge
 * const obj3 = mergeDeep(obj1, obj2);
 *
 * @param {...object} objects - Objects to merge
 * @returns {object} New object with merged key/values
 */
export const mergeDeep = (...objects: any): any => {
  const isObject = (obj: any) => obj && typeof obj === 'object';

  return objects.reduce((prev: any, obj: any) => {
    Object.keys(obj).forEach((key) => {
      const pVal = prev[key];
      const oVal = obj[key];

      if (Array.isArray(pVal) && Array.isArray(oVal)) {
        prev[key] = pVal.concat(...oVal);
      } else if (isObject(pVal) && isObject(oVal)) {
        prev[key] = mergeDeep(pVal, oVal);
      } else {
        prev[key] = oVal;
      }
    });

    return prev;
  }, {});
};
