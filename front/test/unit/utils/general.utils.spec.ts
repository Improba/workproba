import { describe, expect, it } from 'vitest';

import {
  capitalizeFirstLetter,
  mergeDeep,
  replaceAll,
} from '@lib-improba/utils/general.utils';

describe('general.utils', () => {
  it('capitalizeFirstLetter uppercases the first character', () => {
    expect(capitalizeFirstLetter('hello')).toBe('Hello');
  });

  it('replaceAll substitutes every occurrence', () => {
    expect(replaceAll('a b a', ' ', '-')).toBe('a-b-a');
  });

  it('mergeDeep merges nested objects immutably at top level', () => {
    const a = { x: 1, nested: { a: 1 } };
    const b = { y: 2, nested: { b: 2 } };
    expect(mergeDeep({ ...a }, b)).toEqual({
      x: 1,
      y: 2,
      nested: { a: 1, b: 2 },
    });
  });
});
