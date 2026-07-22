import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import MemoryCitationsBar from '@components/chat/MemoryCitationsBar.vue';
import { resetMemoryPanelForTests } from '@composables/useMemoryPanel';

const citations = [
  {
    id: 'mem-1',
    snippet: 'Le budget Q3 est validé.',
    source: 'manual',
    scope: 'project' as const,
  },
  {
    id: 'mem-2',
    snippet: 'Le format de sortie est PowerPoint (PPTX).',
    source: 'session_promotion',
    scope: 'project' as const,
  },
];

describe('MemoryCitationsBar', () => {
  it('affiche une chip repliée par défaut, sans pastilles visibles', () => {
    resetMemoryPanelForTests();
    const wrapper = mount(MemoryCitationsBar, {
      props: { citations },
      global: { stubs: { Lucide: true } },
    });

    const toggle = wrapper.find('.memory-citations__toggle');
    expect(toggle.exists()).toBe(true);
    expect(toggle.attributes('aria-expanded')).toBe('false');
    expect(toggle.text()).toContain('2 souvenirs utilisés');
    expect(wrapper.find('.memory-citations__chip').exists()).toBe(false);
    wrapper.unmount();
  });

  it('déplie les pastilles au clic et ouvre le panneau mémoire sur une citation', async () => {
    resetMemoryPanelForTests();
    const wrapper = mount(MemoryCitationsBar, {
      props: { citations },
      global: { stubs: { Lucide: true } },
    });

    await wrapper.find('.memory-citations__toggle').trigger('click');
    expect(wrapper.find('.memory-citations__toggle').attributes('aria-expanded')).toBe(
      'true',
    );
    expect(wrapper.find('.memory-citations__hint').exists()).toBe(true);

    const chips = wrapper.findAll('.memory-citations__chip');
    expect(chips).toHaveLength(2);
    expect(chips[0].text()).toContain('Le budget Q3 est validé.');
    await chips[0].trigger('click');
    wrapper.unmount();
  });

  it('respecte defaultExpanded', () => {
    resetMemoryPanelForTests();
    const wrapper = mount(MemoryCitationsBar, {
      props: { citations: [citations[0]], defaultExpanded: true },
      global: { stubs: { Lucide: true } },
    });

    expect(wrapper.find('.memory-citations__toggle').attributes('aria-expanded')).toBe(
      'true',
    );
    expect(wrapper.find('.memory-citations__chip').exists()).toBe(true);
    wrapper.unmount();
  });
});
