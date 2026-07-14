import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import OpenSpaceButton from '../../../../src/components/workspace/OpenSpaceButton.vue';
import fr from '../../../../src/i18n/fr/index';

describe('OpenSpaceButton', () => {
  it('affiche le libellé espace par défaut', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'fr',
      messages: { fr },
    });

    const wrapper = mount(OpenSpaceButton, {
      global: {
        plugins: [i18n],
        stubs: {
          Lucide: true,
          'q-spinner': true,
        },
      },
    });

    expect(wrapper.text()).toContain('Ouvrir un espace');
    expect(wrapper.text()).not.toContain('dossier');
  });

  it('accepte un libellé personnalisé', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'fr',
      messages: { fr },
    });

    const wrapper = mount(OpenSpaceButton, {
      props: { label: 'Changer d\'espace' },
      global: {
        plugins: [i18n],
        stubs: {
          Lucide: true,
          'q-spinner': true,
        },
      },
    });

    expect(wrapper.text()).toContain('Changer d\'espace');
  });
});
