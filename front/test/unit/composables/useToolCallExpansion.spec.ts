import { describe, expect, it, vi } from 'vitest';
import {
  clearExpansionState,
  expansionEpoch,
  useThinkingExpansion,
  useToolCallExpansion,
} from '@composables/useToolCallExpansion';

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    toolCallView: { value: 'simple' },
  }),
}));

describe('useToolCallExpansion', () => {
  it('clearExpansionState vide les maps d expansion', () => {
    const tool = useToolCallExpansion(() => 'tool-1');
    const thinking = useThinkingExpansion(() => 'think-1');

    tool.isTechView.value = true;
    tool.showRaw.value = true;
    thinking.expanded.value = true;

    const epochBefore = expansionEpoch.value;
    clearExpansionState();

    expect(tool.isTechView.value).toBe(false);
    expect(tool.showRaw.value).toBe(false);
    expect(thinking.expanded.value).toBe(false);
    expect(expansionEpoch.value).toBe(epochBefore + 1);
  });
});
