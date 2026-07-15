import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import MemoryCitationsBar from '@components/chat/MemoryCitationsBar.vue';
import { resetMemoryPanelForTests } from '@composables/useMemoryPanel';

describe('MemoryCitationsBar', () => {
  it('affiche des puces violettes cliquables pour chaque citation', () => {
    resetMemoryPanelForTests();
    const wrapper = mount(MemoryCitationsBar, {
      props: {
        citations: [
          {
            id: 'mem-1',
            snippet: 'Le budget Q3 est validé.',
            source: 'manual',
            scope: 'project',
          },
        ],
      },
      global: {
        stubs: { Lucide: true },
      },
    });

    const chip = wrapper.find('.memory-citations__chip');
    expect(chip.exists()).toBe(true);
    expect(chip.text()).toContain('Le budget Q3 est validé.');
    chip.trigger('click');
    wrapper.unmount();
  });
});
