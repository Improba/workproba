import { describe, expect, it, vi } from 'vitest';
import {
  clearExpansionState,
  collapseThinking,
  expansionEpoch,
  useActivityGroupExpansion,
  useMemoryCitationsExpansion,
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
    const memory = useMemoryCitationsExpansion(() => 'mem-1');
    const activity = useActivityGroupExpansion(() => 'group-1');

    tool.isTechView.value = true;
    tool.showRaw.value = true;
    thinking.expanded.value = true;
    memory.expanded.value = true;
    activity.expanded.value = true;

    const epochBefore = expansionEpoch.value;
    clearExpansionState();

    expect(tool.isTechView.value).toBe(false);
    expect(tool.showRaw.value).toBe(false);
    expect(thinking.expanded.value).toBe(false);
    expect(memory.expanded.value).toBe(false);
    expect(activity.expanded.value).toBe(false);
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

describe('useActivityGroupExpansion', () => {
  it('toggle bascule l état et incrémente expansionEpoch', () => {
    clearExpansionState();
    const activity = useActivityGroupExpansion(() => 'group-1');

    expect(activity.expanded.value).toBe(false);
    const epochBefore = expansionEpoch.value;

    activity.toggle();
    expect(activity.expanded.value).toBe(true);
    expect(expansionEpoch.value).toBe(epochBefore + 1);
  });
});

describe('useMemoryCitationsExpansion', () => {
  it('toggle bascule l état et incrémente expansionEpoch', () => {
    clearExpansionState();
    const memory = useMemoryCitationsExpansion(() => 'cite-1');

    expect(memory.expanded.value).toBe(false);
    const epochBefore = expansionEpoch.value;

    memory.toggle();
    expect(memory.expanded.value).toBe(true);
    expect(expansionEpoch.value).toBe(epochBefore + 1);

    memory.toggle();
    expect(memory.expanded.value).toBe(false);
    expect(expansionEpoch.value).toBe(epochBefore + 2);
  });

  it('respecte defaultExpanded tant qu il n y a pas d override', () => {
    clearExpansionState();
    const memory = useMemoryCitationsExpansion(() => 'cite-default', () => true);

    expect(memory.expanded.value).toBe(true);

    memory.expanded.value = false;
    expect(memory.expanded.value).toBe(false);

    clearExpansionState();
    const memoryAgain = useMemoryCitationsExpansion(() => 'cite-default', () => true);
    expect(memoryAgain.expanded.value).toBe(true);
  });
});
