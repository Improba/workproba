import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ChatModelMenuContent from '@components/chat/ChatModelMenuContent.vue';

const quasarStubs = {
  Lucide: { template: '<span />' },
  'q-list': { template: '<div><slot /></div>' },
  'q-item': {
    template:
      '<div class="chat-model-menu-content__item" role="button" @click="$emit(\'click\')"><slot /></div>',
  },
  'q-item-section': { template: '<div><slot /></div>' },
  'q-item-label': { template: '<span><slot /></span>' },
  'q-separator': true,
};

function mountMenuContent(props: Record<string, unknown> = {}) {
  return mount(ChatModelMenuContent, {
    props: {
      modelValue: 'none',
      provider: 'mistral',
      model: 'mistral-medium-latest',
      ...props,
    },
    global: {
      stubs: quasarStubs,
    },
  });
}

describe('ChatModelMenuContent', () => {
  it('affiche les sections modèle et raisonnement', () => {
    const wrapper = mountMenuContent();
    expect(wrapper.find('.chat-model-menu-content__head').exists()).toBe(true);
    expect(wrapper.text()).toContain('Modèle');
    expect(wrapper.text()).toContain('Raisonnement');
    wrapper.unmount();
  });

  it('émet update:modelValue quand le raisonnement change', async () => {
    const wrapper = mountMenuContent({ modelValue: 'none' });
    const items = wrapper.findAll('.chat-model-menu-content__item');
    const highItem = items.find((item) => item.text().includes('Élevé'));
    expect(highItem).toBeTruthy();
    await highItem!.trigger('click');

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['high']);
    wrapper.unmount();
  });

  it('émet update:model et update:modelValue quand le modèle change', async () => {
    const wrapper = mountMenuContent({
      modelValue: 'low',
      provider: 'mistral',
      model: 'mistral-small-latest',
    });

    const items = wrapper.findAll('.chat-model-menu-content__item');
    const target = items.find((item) => item.text().includes('Mistral Medium'));
    expect(target).toBeTruthy();
    await target!.trigger('click');

    expect(wrapper.emitted('update:model')?.[0]).toEqual(['mistral-medium-latest']);
    expect(wrapper.emitted('update:modelValue')?.length).toBeGreaterThan(0);
    wrapper.unmount();
  });
});
