import { BadRequestException } from '@nestjs/common';

import { ParseIntOrUndefinedPipe } from '@lib-improba/pipes/ParseIntOrUndefined.pipe';

describe('ParseIntOrUndefinedPipe', () => {
  const pipe = new ParseIntOrUndefinedPipe();
  const metadata = { type: 'query' as const, data: 'page' };

  it('returns undefined when value is undefined', () => {
    expect(pipe.transform(undefined as unknown as string, metadata)).toBeUndefined();
  });

  it('parses a valid integer string', () => {
    expect(pipe.transform('12', metadata)).toBe(12);
  });

  it('throws when value is not a number', () => {
    expect(() => pipe.transform('abc', metadata)).toThrow(BadRequestException);
  });
});
