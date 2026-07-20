import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import PersonasSideChat from '@components/personas/PersonasSideChat.vue';
import { ProviderSetNotReadyError } from '@utils/providerSetErrors';
import { Notify } from 'quasar';

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

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activeDataDir: ref('/tmp/workspace'),
  }),
}));

const initialPayload = ref({
  personaIds: ['p1'],
  mode: 'avis' as const,
  draft: '',
  discussionSeed: null as string | null,
  conversationContext: '',
  autoAsk: false,
  resume: null as null,
});

vi.mock('@composables/useSideChat', () => ({
  useSideChat: () => ({
    consumeInitial: () => ({ ...initialPayload.value }),
    peekInitial: () => ({ ...initialPayload.value }),
    launchToken: ref(0),
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('PersonasSideChat', () => {
  beforeEach(() => {
    askOpinion.mockClear();
    initialPayload.value = {
      personaIds: ['p1'],
      mode: 'avis',
      draft: '',
      discussionSeed: null,
      conversationContext: '',
      autoAsk: false,
      resume: null,
    };
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
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.personas-side-chat').exists()).toBe(true);
    expect(wrapper.find('.personas-side-chat__input').attributes('placeholder')).toBe(
      'Posez votre question…',
    );

    await wrapper.findAll('.personas-side-chat__mode')[1]?.trigger('click');
    expect(wrapper.find('.personas-side-chat__input').attributes('placeholder')).toBe(
      'Écrivez au regard sélectionné…',
    );
  });

  it('affiche l\'état vide avec invitation à choisir quand aucun regard sélectionné', async () => {
    initialPayload.value = {
      personaIds: [],
      mode: 'avis',
      draft: '',
      discussionSeed: null,
      conversationContext: '',
      autoAsk: false,
      resume: null,
    };

    const wrapper = mount(PersonasSideChat, {
      props: { pluginId: 'workproba.personas' },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasOpinionCard: true,
          PersonasPicker: true,
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Choisissez d\'abord qui consulter.');
    expect(wrapper.find('.personas-side-chat__choose-first').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Aucun échange pour l\'instant.');
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

  it('auto-demande l\'avis avec le contexte quand autoAsk est activé', async () => {
    initialPayload.value = {
      personaIds: ['p1'],
      mode: 'avis',
      draft: '',
      discussionSeed: null,
      conversationContext: 'Utilisateur : Bonjour',
      autoAsk: true,
      resume: null,
    };

    mount(PersonasSideChat, {
      props: { pluginId: 'workproba.personas' },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasOpinionCard: true,
          PersonasPicker: true,
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    expect(askOpinion).toHaveBeenCalledWith(
      '/tmp/personas',
      ['p1'],
      'Quel est ton avis sur notre échange en cours ?',
      'Utilisateur : Bonjour',
      '/tmp/workspace',
      false,
    );
  });

  it('ne toast pas askFailed quand readiness a déjà notifié', async () => {
    const notifyCreate = vi.mocked(Notify.create);
    notifyCreate.mockClear();
    askOpinion.mockRejectedValueOnce(new ProviderSetNotReadyError('missing_api_key'));

    const wrapper = mount(PersonasSideChat, {
      props: { pluginId: 'workproba.personas' },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasOpinionCard: true,
          PersonasPicker: true,
          PublishToProjectDialog: true,
        },
      },
    });

    await flushPromises();

    const textarea = wrapper.find('.personas-side-chat__input');
    await textarea.setValue('Question sans modèle');
    await wrapper.find('form.personas-side-chat__composer').trigger('submit.prevent');
    await flushPromises();

    const negativeToasts = notifyCreate.mock.calls.filter(
      ([opts]) => typeof opts === 'object' && opts !== null && opts.color === 'negative',
    );
    expect(negativeToasts).toHaveLength(0);
  });
});
