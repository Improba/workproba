import { defineComponent, ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { notifyCreate, startPersonasMeeting, fetchPersonasMeetings, fetchPersonasMeeting, fetchPersonasDiscussions, fetchPersonasDiscussion } = vi.hoisted(() => ({
  notifyCreate: vi.fn(),
  startPersonasMeeting: vi.fn(),
  fetchPersonasMeetings: vi.fn(),
  fetchPersonasMeeting: vi.fn(),
  fetchPersonasDiscussions: vi.fn(),
  fetchPersonasDiscussion: vi.fn(),
}));

vi.mock('quasar', () => ({
  Notify: { create: notifyCreate },
}));

vi.mock('@services/aiSidecar', () => ({
  askPersonasOpinion: vi.fn(),
  buildSidecarSecurityContext: vi.fn(),
  discussWithPersonas: vi.fn(),
  estimatePersonasCost: vi.fn(),
  fetchPersonasSets: vi.fn().mockResolvedValue([
    {
      id: 'builtin',
      name: 'Builtin',
      personas: [{ id: 'p1', name: 'Alice', role: 'PO', description: '', avatar_color: '#f00' }],
    },
  ]),
  fetchPersonasMeetings,
  fetchPersonasMeeting,
  fetchPersonasDiscussions,
  fetchPersonasDiscussion,
  startPersonasMeeting,
}));

vi.mock('@composables/useAppSettings', () => ({
  buildActiveProviderSet: () => null,
  useAppSettings: () => ({
    locale: ref('fr'),
    settingsLocked: ref(false),
    permissionsNetwork: ref(true),
    settingsMode: ref('guided'),
    codeExecute: ref(true),
    auditEnabled: ref(null),
  }),
}));

vi.mock('@utils/providerSetNotify', () => ({
  ensureProviderSetChatReady: () => true,
  ensureProviderSetEmbeddingsReady: () => true,
  chatErrorMessageForReadiness: (reason: string) => reason,
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    providerReadiness: ref(null),
  }),
}));

vi.mock('@composables/useLlmSessionContext', () => ({
  useLlmSessionContext: () => ({
    buildContextProviderSet: () => ({
      id: 'mistral-default',
      name: 'Mistral',
      chat: { provider: 'mistral', model: 'mistral-small-latest', apiKey: 'k' },
      embeddings: null,
      vision: { mode: 'none' },
      capabilities: { reasoning: 'medium', vision: false, tools: true },
      badges: [],
      description: '',
      isDefault: true,
      isBuiltin: true,
    }),
    buildContextLlmConfigs: () => ({ chat: null, embedding: null }),
  }),
}));

vi.mock('@composables/usePlugins', () => ({
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  CLOUD_PLUGIN_ID: 'workproba.cloud',
  usePlugins: () => ({
    isPersonasPluginActive: ref(true),
    getPluginDataDir: async () => '/tmp/cloud-plugin',
  }),
}));

import {
  meetingStateToStored,
  syncPersonasHistory,
  usePersonas,
  type MeetingState,
} from '@composables/usePersonas';

function mountPersonas() {
  let api!: ReturnType<typeof usePersonas>;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = usePersonas();
        return {};
      },
      template: '<div />',
    }),
  );
  return { api, unmount: () => wrapper.unmount() };
}

describe('usePersonas', () => {
  beforeEach(() => {
    notifyCreate.mockClear();
    startPersonasMeeting.mockReset();
    fetchPersonasMeetings.mockReset();
    fetchPersonasMeeting.mockReset();
    fetchPersonasDiscussions.mockReset();
    fetchPersonasDiscussion.mockReset();
    localStorage.clear();
  });

  it('capture meeting_id depuis meeting_started et done', async () => {
    startPersonasMeeting.mockImplementation(
      async (
        _payload: unknown,
        onEvent: (type: string, data: Record<string, unknown>) => void,
      ) => {
        onEvent('meeting_started', { meeting_id: 'mtg_back_42' });
        onEvent('meeting_turn', {
          round: 1,
          persona_id: 'p1',
          persona_name: 'Alice',
          content: 'Bonjour',
        });
        onEvent('done', { meeting_id: 'mtg_back_42' });
      },
    );

    const { api, unmount } = mountPersonas();
    const state = await api.startMeeting('/tmp/personas', ['p1'], 'Sujet test', 2);
    unmount();

    expect(state.meetingId).toBe('mtg_back_42');
    const stored = meetingStateToStored(state);
    expect(stored.meeting_id).toBe('mtg_back_42');
  });

  it('émet un toast sur event warning', async () => {
    startPersonasMeeting.mockImplementation(
      async (
        _payload: unknown,
        onEvent: (type: string, data: Record<string, unknown>) => void,
      ) => {
        onEvent('warning', { warnings: ['personas.warning.maxPersonas'] });
        onEvent('done', { meeting_id: 'mtg_warn' });
      },
    );

    const { api, unmount } = mountPersonas();
    await api.startMeeting('/tmp/personas', ['p1'], 'Sujet', 1);
    unmount();

    expect(notifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'warning' }),
    );
  });

  it('passe meeting_id au POST meeting quand fourni', async () => {
    startPersonasMeeting.mockImplementation(async () => {});

    const { api, unmount } = mountPersonas();
    await api.startMeeting(
      '/tmp/personas',
      ['p1'],
      'Sujet',
      2,
      undefined,
      null,
      false,
      'mtg_tool_99',
    );
    unmount();

    expect(startPersonasMeeting).toHaveBeenCalledWith(
      expect.objectContaining({ meetingId: 'mtg_tool_99' }),
      expect.any(Function),
      expect.anything(),
    );
  });

  it('normalise transcript array depuis le back', async () => {
    localStorage.setItem(
      'workproba.personas.meetings',
      JSON.stringify([
        {
          meeting_id: 'local_only',
          topic: 'Local',
          persona_ids: ['p1'],
          created_at: '2026-01-01T00:00:00.000Z',
          transcript: 'local transcript',
        },
      ]),
    );

    fetchPersonasMeetings.mockResolvedValue([
      {
        meeting_id: 'back_1',
        topic: 'Back meeting',
        persona_ids: ['p1'],
        rounds: 2,
        created_at: '2026-02-01T00:00:00.000Z',
      },
    ]);
    fetchPersonasMeeting.mockResolvedValue({
      meeting_id: 'back_1',
      topic: 'Back meeting',
      persona_ids: ['p1'],
      rounds: 2,
      created_at: '2026-02-01T00:00:00.000Z',
      transcript: [
        { round: 1, persona_name: 'Alice', content: 'Bonjour' },
      ],
      summary: { persona_name: 'Alice', content: 'Synthèse back' },
    });
    fetchPersonasDiscussions.mockResolvedValue([]);
    fetchPersonasDiscussion.mockResolvedValue(null);

    await syncPersonasHistory('/tmp/personas');

    const stored = JSON.parse(
      localStorage.getItem('workproba.personas.meetings') ?? '[]',
    ) as Array<{ meeting_id: string; transcript: string }>;

    const backMeeting = stored.find((m) => m.meeting_id === 'back_1');
    expect(backMeeting?.transcript).toContain('Alice');
    expect(backMeeting?.transcript).toContain('Synthèse back');
    expect(stored.some((m) => m.meeting_id === 'local_only')).toBe(true);
  });

  it('consomme meeting_facilitator avec isFacilitator', async () => {
    startPersonasMeeting.mockImplementation(
      async (
        _payload: unknown,
        onEvent: (type: string, data: Record<string, unknown>) => void,
      ) => {
        onEvent('meeting_started', { meeting_id: 'mtg_fac' });
        onEvent('meeting_facilitator', { round: 1, label: 'Transition tour 1' });
        onEvent('done', { meeting_id: 'mtg_fac' });
      },
    );

    const { api, unmount } = mountPersonas();
    const state = await api.startMeeting('/tmp/personas', ['p1'], 'Sujet', 1);
    unmount();

    expect(state.turns).toHaveLength(1);
    expect(state.turns[0]?.isFacilitator).toBe(true);
    expect(state.turns[0]?.content).toBe('Transition tour 1');
  });

  it('stocke summaryPersonaName depuis meeting_summary', async () => {
    startPersonasMeeting.mockImplementation(
      async (
        _payload: unknown,
        onEvent: (type: string, data: Record<string, unknown>) => void,
      ) => {
        onEvent('meeting_summary', { content: 'Résumé final', persona_name: 'Alice' });
        onEvent('done', { meeting_id: 'mtg_sum' });
      },
    );

    const { api, unmount } = mountPersonas();
    const state: MeetingState = await api.startMeeting('/tmp/personas', ['p1'], 'Sujet', 1);
    unmount();

    expect(state.summary).toBe('Résumé final');
    expect(state.summaryPersonaName).toBe('Alice');
  });
});
