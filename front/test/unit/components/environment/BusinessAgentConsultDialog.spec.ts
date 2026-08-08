import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import BusinessAgentConsultDialog from '@components/environment/BusinessAgentConsultDialog.vue';
import {
  resetBusinessAgentConsultationForTests,
  useBusinessAgentConsultation,
} from '@composables/useBusinessAgentConsultation';

const push = vi.fn();
const createSession = vi.fn().mockResolvedValue({ id: 'session-1' });
const setPendingChatLaunch = vi.fn();
const bumpSessions = vi.fn();

const activePath = ref('/tmp/workspace');
const activeSpaceId = ref('space-1');
const connectors = ref([]);

const agent = {
  id: 'org.rh',
  name: 'Camille RH',
  role: 'RH',
  description: 'Référente RH',
  avatar_color: '#e0a93a',
  is_business_agent: true,
  tools: { allowed: [{ connector_id: 'ihora', tool: 'employee.read' }] },
};

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@composables/useBusinessAgentConsultation', async () => {
  const actual = await vi.importActual<typeof import('@composables/useBusinessAgentConsultation')>(
    '@composables/useBusinessAgentConsultation',
  );
  return actual;
});

vi.mock('@composables/useOrganizationEnvironment', () => ({
  useOrganizationEnvironment: () => ({ connectors }),
}));

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activePath,
    activeSpaceId,
  }),
}));

vi.mock('@services/workspaceSession', () => ({
  createSession: (...args: unknown[]) => createSession(...args),
}));

vi.mock('@composables/usePendingChatLaunch', () => ({
  setPendingChatLaunch: (...args: unknown[]) => setPendingChatLaunch(...args),
}));

vi.mock('@composables/useSessionSync', () => ({
  bumpSessions: (...args: unknown[]) => bumpSessions(...args),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => (
      params ? `${key}:${JSON.stringify(params)}` : key
    ),
  }),
}));

describe('BusinessAgentConsultDialog', () => {
  beforeEach(() => {
    resetBusinessAgentConsultationForTests();
    const { requestConsultation } = useBusinessAgentConsultation();
    requestConsultation(agent);
    activePath.value = '/tmp/workspace';
    activeSpaceId.value = 'space-1';
    push.mockClear();
    createSession.mockClear();
    setPendingChatLaunch.mockClear();
    bumpSessions.mockClear();
  });

  it('ouvre une conversation Workproba avec un prompt de consultation', async () => {
    const wrapper = shallowMount(BusinessAgentConsultDialog, {
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          SpecialistToolsPanel: true,
          'q-dialog': {
            template: '<div><slot /></div>',
          },
        },
      },
    });

    await wrapper.find('textarea').setValue('Vérifier le dossier salarié');
    await wrapper.find('.business-agent-consult__submit').trigger('click');
    await flushPromises();

    expect(createSession).toHaveBeenCalledWith('space-1', '/tmp/workspace');
    expect(setPendingChatLaunch).toHaveBeenCalledWith({
      text: expect.stringContaining('org.rh'),
      attachments: [],
    });
    expect(bumpSessions).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: 'chat_session', params: { id: 'session-1' } });
  });
});
