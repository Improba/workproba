import { describe, expect, it } from 'vitest';

import { formatNumber } from '@lib-improba/utils/number-format.utils';

describe('number-format.utils', () => {
  it('formatNumber rounds to given decimals by default', () => {
    expect(formatNumber(1.236)).toBe(1);
    expect(formatNumber(1.236, { decimals: 2, type: 'round' })).toBe(1.24);
  });

  it('formatNumber floors and ceils correctly', () => {
    expect(formatNumber(1.239, { decimals: 2, type: 'floor' })).toBe(1.23);
    expect(formatNumber(1.231, { decimals: 2, type: 'ceil' })).toBe(1.24);
  });
});
