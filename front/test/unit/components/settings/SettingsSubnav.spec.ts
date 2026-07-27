import { mount } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SettingsSubnav from '@components/settings/SettingsSubnav.vue';

const push = vi.fn();
const back = vi.fn();
let historyBack: string | undefined;

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
    back,
    options: {
      history: {
        state: {
          get back() {
            return historyBack;
          },
        },
      },
    },
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settingsLocked: { value: false },
  }),
}));

const mountSubnav = () =>
  mount(SettingsSubnav, {
    props: { active: 'models' },
    global: {
      stubs: {
        Lucide: true,
        RouterLink: {
          template: '<a><slot /></a>',
        },
      },
    },
  });

describe('SettingsSubnav', () => {
  beforeEach(() => {
    push.mockReset();
    back.mockReset();
    historyBack = undefined;
  });

  it('revient en arrière hors paramètres', async () => {
    historyBack = '/chat/abc';
    const wrapper = mountSubnav();

    await wrapper.find('.settings-subnav__back').trigger('click');

    expect(back).toHaveBeenCalledOnce();
    expect(push).not.toHaveBeenCalled();
  });

  it('retourne à l’accueil sans historique utilisable', async () => {
    historyBack = '/settings/plugins';
    const wrapper = mountSubnav();

    await wrapper.find('.settings-subnav__close').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'home' });
    expect(back).not.toHaveBeenCalled();
  });
});
