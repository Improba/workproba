import { describe, expect, it, vi } from 'vitest';
import {
  clearExpansionState,
  collapseThinking,
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

  it('collapseThinking replie un bloc raisonnement déplié', () => {
    clearExpansionState();
    const thinking = useThinkingExpansion(() => 'think-collapse');

    thinking.expanded.value = true;
    expect(thinking.expanded.value).toBe(true);

    const epochBefore = expansionEpoch.value;
    collapseThinking('think-collapse');

    expect(thinking.expanded.value).toBe(false);
    expect(expansionEpoch.value).toBe(epochBefore + 1);
  });

  it('collapseThinking est un no-op si déjà replié', () => {
    clearExpansionState();
    const thinking = useThinkingExpansion(() => 'think-idle');
    const epochBefore = expansionEpoch.value;

    collapseThinking('think-idle');

    expect(thinking.expanded.value).toBe(false);
    expect(expansionEpoch.value).toBe(epochBefore);
  });
});
