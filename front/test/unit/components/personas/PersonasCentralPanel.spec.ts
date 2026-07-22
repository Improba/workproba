import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import PersonasCentralPanel from '@components/personas/PersonasCentralPanel.vue';

const personas = ref([
  {
    id: 'p1',
    name: 'Nathalie',
    role: 'PO',
    avatar_color: '#ffcc49',
    system_prompt: 'Tu es la PO.',
  },
  {
    id: 'p2',
    name: 'Marc',
    role: 'Technicien',
    avatar_color: '#4a90d9',
    system_prompt: '',
  },
]);

const sets = ref([
  {
    id: 'builtin',
    name: 'Improba',
    personas: personas.value,
  },
]);

const settingsLocked = ref(false);

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settingsLocked,
  }),
}));

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    sets,
    activeSet: ref(sets.value[0]),
    personas,
    builtinPersonas: personas,
    selectablePersonas: personas,
    loading: ref(false),
    refresh: vi.fn().mockResolvedValue(undefined),
    setActiveSet: vi.fn(),
    listMeetings: vi.fn(() => []),
    listDiscussions: vi.fn(() => []),
    listCustomSets: vi.fn(() => []),
    saveCustomSet: vi.fn(),
  }),
  estimateSessionCalls: vi.fn(() => 0),
}));

describe('PersonasCentralPanel', () => {
  beforeEach(() => {
    settingsLocked.value = false;
  });

  function mountPanel() {
    return mount(PersonasCentralPanel, {
      props: {
        pluginActive: true,
        pluginDataDir: '/tmp/personas',
      },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasConfidentialityHint: true,
          PersonasHistoryPanel: true,
          QDialog: {
            template: '<div><slot /></div>',
          },
        },
      },
    });
  }

  it('affiche les personas et émet discuss au clic sur la carte', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('Nathalie');
    expect(wrapper.text()).not.toContain('Jeux de personas');

    await wrapper.find('.personas-central__card-main').trigger('click');

    expect(wrapper.emitted('discuss')?.[0]).toEqual([['p1']]);
  });

  it('émet ask-opinion avec l\'id du persona', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    const opinionBtn = wrapper
      .findAll('.personas-central__card-secondary')
      .find((b) => b.text().includes('Son avis'));
    await opinionBtn!.trigger('click');

    expect(wrapper.emitted('ask-opinion')?.[0]).toEqual([['p1']]);
  });

  it('masque la personnalisation des jeux en mode verrouillé', async () => {
    settingsLocked.value = true;
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('.personas-central__advanced').exists()).toBe(false);
  });

  it('affiche la section personnaliser hors mode verrouillé', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('.personas-central__advanced').exists()).toBe(true);
    expect(wrapper.text()).toContain('Personnaliser');
  });
});
