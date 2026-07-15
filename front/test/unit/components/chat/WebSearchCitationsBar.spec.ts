import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import WebSearchCitationsBar from '@components/chat/WebSearchCitationsBar.vue';

vi.mock('@composables/useDesktop', () => ({
  openExternalUrl: vi.fn(),
}));

import { openExternalUrl } from '@composables/useDesktop';

describe('WebSearchCitationsBar', () => {
  it('affiche des puces cliquables pour chaque source web', async () => {
    const wrapper = mount(WebSearchCitationsBar, {
      props: {
        citations: [
          {
            title: 'Météo France',
            url: 'https://meteofrance.com/',
            snippet: 'Prévisions.',
          },
        ],
      },
      global: {
        stubs: { Lucide: true },
      },
    });

    expect(wrapper.text()).toContain('Météo France');
    const chip = wrapper.find('.web-search-citations__chip');
    expect(chip.exists()).toBe(true);
    await chip.trigger('click');
    expect(openExternalUrl).toHaveBeenCalledWith('https://meteofrance.com/');
    wrapper.unmount();
  });
});
