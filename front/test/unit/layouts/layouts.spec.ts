import { beforeEach, describe, expect, it, vi } from 'vitest';
import { shallowMount } from '@vue/test-utils';
import EmptyLayout from '../../../src/layouts/EmptyLayout.vue';
import StandardLayout from '../../../src/layouts/StandardLayout.vue';

const { state } = vi.hoisted(() => ({
  state: {
    routerPush: vi.fn(),
  },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: state.routerPush,
  }),
}));

vi.mock('@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue', () => ({
  default: {
    name: 'ThemeToggler',
    template: '<div class="theme-toggler-mock" />',
  },
}));

const standardStubs = {
  'q-layout': { template: '<div><slot /></div>' },
  'q-header': { template: '<div><slot /></div>' },
  'q-toolbar': { template: '<div><slot /></div>' },
  'q-tabs': { template: '<div><slot /></div>' },
  'q-route-tab': { template: '<div><slot /></div>' },
  'q-space': true,
  'q-page-container': { template: '<div><slot /></div>' },
  'q-list': { template: '<div><slot /></div>' },
  'q-item': { template: '<div><slot /></div>' },
  'q-item-section': { template: '<button><slot /></button>' },
  MBtnDropdown: { template: '<div><slot /></div>' },
  ThemeToggler: true,
};

describe('layouts smoke tests', () => {
  beforeEach(() => {
    state.routerPush.mockReset();
  });

  it('EmptyLayout rend son slot', () => {
    const wrapper = shallowMount(EmptyLayout, {
      slots: { default: '<div id="inner-slot">Inner content</div>' },
    });

    expect(wrapper.find('#inner-slot').exists()).toBe(true);
    expect(wrapper.text()).toContain('Inner content');
  });

  it('StandardLayout affiche le logo Workproba', () => {
    const wrapper = shallowMount(StandardLayout, {
      global: { stubs: standardStubs },
    });

    expect(wrapper.text()).toContain('Workproba');
  });

  it('StandardLayout rend son slot par défaut', () => {
    const wrapper = shallowMount(StandardLayout, {
      slots: { default: '<div id="layout-slot">Contenu page</div>' },
      global: { stubs: standardStubs },
    });

    expect(wrapper.find('#layout-slot').exists()).toBe(true);
    expect(wrapper.text()).toContain('Contenu page');
  });
});

