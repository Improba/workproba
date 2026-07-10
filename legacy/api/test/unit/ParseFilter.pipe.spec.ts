import { BadRequestException } from '@nestjs/common';

import { ParseFilterPipe } from '@lib-improba/pipes/ParseFilter.pipe';

describe('ParseFilterPipe', () => {
  const pipe = new ParseFilterPipe();
  const metadata = { type: 'query' as const, data: 'filter' };

  it('returns undefined when value is undefined', () => {
    expect(pipe.transform(undefined, metadata)).toBeUndefined();
  });

  it('replaces leading and trailing wildcards with %', () => {
    expect(pipe.transform('*foo*', metadata)).toBe('%foo%');
  });

  it('throws when value is not a string', () => {
    expect(() => pipe.transform(42, metadata)).toThrow(BadRequestException);
  });
});
