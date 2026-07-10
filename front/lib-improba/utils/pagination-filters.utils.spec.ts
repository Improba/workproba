import { describe, expect, it } from 'vitest';

import { checkIfCanRemoveFilters } from './pagination-filters.utils';

describe('pagination-filters.utils', () => {
  it('checkIfCanRemoveFilters returns true when only "all" is selected', () => {
    expect(checkIfCanRemoveFilters([], [{ label: 'All', value: 'all' }])).toBe(
      true,
    );
  });

  it('checkIfCanRemoveFilters returns false when a specific filter is selected', () => {
    expect(
      checkIfCanRemoveFilters(
        [{ label: 'Active', value: 'active' }],
        [{ label: 'Active', value: 'active' }],
      ),
    ).toBe(false);
  });
});
