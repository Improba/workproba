import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ChatModelControl from '@components/chat/ChatModelControl.vue';

const quasarStubs = {
  Lucide: { template: '<span />' },
  'q-menu': { template: '<div class="chat-model-control__menu"><slot /></div>' },
  'q-list': { template: '<div><slot /></div>' },
  'q-item': {
    template:
      '<div class="chat-model-control__item" role="button" @click="$emit(\'click\')"><slot /></div>',
  },
  'q-item-section': { template: '<div><slot /></div>' },
  'q-item-label': { template: '<span><slot /></span>' },
  'q-separator': true,
};

function mountControl(props: Record<string, unknown> = {}) {
  return mount(ChatModelControl, {
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

describe('ChatModelControl', () => {
  it('attache le menu comme enfant direct du déclencheur (pattern Quasar)', () => {
    const wrapper = mountControl();
    const trigger = wrapper.find('.chat-model-control__trigger');
    expect(trigger.exists()).toBe(true);
    expect(trigger.find('.chat-model-control__menu').exists()).toBe(true);
    wrapper.unmount();
  });

  it('ouvre le menu au clic sur le déclencheur', async () => {
    const wrapper = mount(ChatModelControl, {
      props: {
        modelValue: 'none',
        provider: 'mistral',
        model: 'mistral-medium-latest',
      },
      global: {
        stubs: {
          ...quasarStubs,
          'q-menu': {
            template: '<div v-if="open" class="chat-model-control__menu"><slot /></div>',
            data() {
              return { open: false };
            },
            mounted() {
              const trigger = this.$el.parentElement;
              trigger?.addEventListener('click', () => {
                this.open = !this.open;
              });
            },
          },
        },
      },
    });

    const trigger = wrapper.find('.chat-model-control__trigger');
    expect(wrapper.find('.chat-model-control__menu').exists()).toBe(false);
    await trigger.trigger('click');
    expect(wrapper.find('.chat-model-control__menu').exists()).toBe(true);
    wrapper.unmount();
  });

  it('émet update:modelValue quand le raisonnement change', async () => {
    const wrapper = mountControl({ modelValue: 'none' });
    const items = wrapper.findAll('.chat-model-control__item');
    const highItem = items.find((item) => item.text().includes('Élevé'));
    expect(highItem).toBeTruthy();
    await highItem!.trigger('click');

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['high']);
    wrapper.unmount();
  });

  it('émet update:model et update:modelValue quand le modèle change', async () => {
    const wrapper = mountControl({
      modelValue: 'low',
      provider: 'mistral',
      model: 'mistral-small-latest',
    });

    const items = wrapper.findAll('.chat-model-control__item');
    const target = items.find((item) => item.text().includes('Mistral Medium'));
    expect(target).toBeTruthy();
    await target!.trigger('click');

    expect(wrapper.emitted('update:model')?.[0]).toEqual(['mistral-medium-latest']);
    expect(wrapper.emitted('update:modelValue')?.length).toBeGreaterThan(0);
    wrapper.unmount();
  });
});
