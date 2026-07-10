import { describe, expect, it } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import MBtn from '../../../../lib-improba/components/mastok/MBtn.vue';

const QBtnStub = {
  name: 'QBtn',
  template:
    '<button :data-color="color" :data-flat="flat" @click="$emit(\'click\')"><slot /></button>',
  emits: ['click'],
  props: {
    color: { type: String, default: '' },
    flat: { type: Boolean, default: false },
  },
};

describe('MBtn', () => {
  it('rend le slot utilisateur et applique la couleur attendue', () => {
    const wrapper = shallowMount(MBtn, {
      props: { secondary: true },
      slots: { default: 'Valider' },
      global: {
        stubs: {
          'q-btn': QBtnStub,
        },
      },
    });

    const qBtn = wrapper.findComponent(QBtnStub);

    expect(wrapper.text()).toContain('Valider');
    expect(qBtn.attributes('data-color')).toBe('neutral-lowest');
  });

  it('propage le clic utilisateur', async () => {
    const wrapper = shallowMount(MBtn, {
      slots: { default: 'Cliquer' },
      global: {
        stubs: {
          'q-btn': QBtnStub,
        },
      },
    });

    await wrapper.find('button').trigger('click');

    expect(wrapper.emitted('click')).toHaveLength(1);
  });

  it('rend lucideIcon quand demandé et conserve flat=true', () => {
    const wrapper = shallowMount(MBtn, {
      props: {
        flat: true,
        danger: true,
        lucideIcon: 'trash',
      },
      global: {
        stubs: {
          'q-btn': QBtnStub,
        },
      },
    });

    const qBtn = wrapper.findComponent(QBtnStub);

    expect(qBtn.attributes('data-flat')).toBe('true');
    expect(wrapper.find('lucide-stub').exists()).toBe(true);
  });
});
