import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import PersonasSideChat from '@components/personas/PersonasSideChat.vue';

const personas = ref([
  {
    id: 'p1',
    name: 'Alice',
    role: 'PO',
    avatar_color: '#ffcc49',
    system_prompt: '',
  },
]);

const askOpinion = vi.fn().mockResolvedValue({
  question: 'Test ?',
  opinions: [],
  streaming: false,
});

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    personas,
    selectablePersonas: personas,
    loading: ref(false),
    refresh: vi.fn().mockResolvedValue(undefined),
    askOpinion,
    discuss: vi.fn(),
    saveDiscussion: vi.fn(),
    findPersona: (id: string) => personas.value.find((p) => p.id === id),
  }),
  discussionMessagesToStored: vi.fn(),
  formatDiscussionMarkdown: vi.fn(() => '# Discussion'),
}));

vi.mock('@composables/usePlugins', () => ({
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  usePlugins: () => ({
    getPluginDataDir: vi.fn().mockResolvedValue('/tmp/personas'),
    isPersonasPluginActive: ref(true),
    isProjetPluginActive: ref(false),
  }),
}));

vi.mock('@composables/useProject', () => ({
  useProject: () => ({
    activeDataDir: ref('/tmp/workspace'),
  }),
}));

vi.mock('@composables/useSideChat', () => ({
  useSideChat: () => ({
    consumeInitial: () => ({
      personaIds: ['p1'],
      mode: 'avis' as const,
      draft: '',
      discussionSeed: null,
    }),
    launchToken: ref(0),
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('PersonasSideChat', () => {
  beforeEach(() => {
    askOpinion.mockClear();
  });

  it('affiche le composant et bascule le placeholder selon le mode', async () => {
    const wrapper = mount(PersonasSideChat, {
      props: { pluginId: 'workproba.personas' },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasOpinionCard: true,
          PersonasPicker: true,
          PersonasConfidentialityHint: true,
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.personas-side-chat').exists()).toBe(true);
    expect(wrapper.find('.personas-side-chat__input').attributes('placeholder')).toBe(
      'Posez votre question aux personas…',
    );

    await wrapper.findAll('.personas-side-chat__mode')[1]?.trigger('click');
    expect(wrapper.find('.personas-side-chat__input').attributes('placeholder')).toBe(
      'Écrivez à la persona…',
    );
  });

  it('envoie une question en mode avis via askOpinion', async () => {
    const wrapper = mount(PersonasSideChat, {
      props: { pluginId: 'workproba.personas' },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasOpinionCard: true,
          PersonasPicker: true,
          PersonasConfidentialityHint: true,
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    const textarea = wrapper.find('.personas-side-chat__input');
    await textarea.setValue('Quel avis ?');
    await wrapper.find('form.personas-side-chat__composer').trigger('submit.prevent');
    await flushPromises();

    expect(askOpinion).toHaveBeenCalledWith(
      '/tmp/personas',
      ['p1'],
      'Quel avis ?',
      undefined,
      '/tmp/workspace',
      false,
    );
  });
});
