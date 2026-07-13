import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PersonasHistoryPanel from '@components/personas/PersonasHistoryPanel.vue';

const meetings = [
  {
    meeting_id: 'mtg-1',
    topic: 'Budget Q3',
    persona_ids: ['p1', 'p2'],
    rounds: 2,
    created_at: '2026-07-01T10:00:00Z',
    transcript: 'Transcript de la réunion.',
  },
];

const discussions = [
  {
    discussion_id: 'disc-1',
    persona_ids: ['p1'],
    updated_at: '2026-07-02T14:00:00Z',
    messages: [
      {
        role: 'user' as const,
        content: 'Question initiale',
        persona_id: undefined,
        persona_name: undefined,
        role_label: undefined,
        avatar_color: undefined,
        avatar_icon: undefined,
      },
    ],
  },
];

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    listMeetings: vi.fn(() => meetings),
    listDiscussions: vi.fn(() => discussions),
    syncHistory: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe('PersonasHistoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function mountPanel(mode: 'all' | 'meeting' | 'discuss' = 'all') {
    return mount(PersonasHistoryPanel, {
      props: {
        mode,
        defaultExpanded: true,
        pluginDataDir: '/tmp/personas',
      },
      global: {
        stubs: { Lucide: true },
      },
    });
  }

  it('affiche le transcript sans relancer la réunion au clic sur une réunion', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.personas-history__item').trigger('click');

    expect(wrapper.text()).toContain('Transcript de la réunion.');
    expect(wrapper.emitted('relaunch-meeting')).toBeUndefined();
  });

  it('émet relaunch-meeting uniquement via le bouton Relancer', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.personas-history__relaunch').trigger('click');

    expect(wrapper.emitted('relaunch-meeting')?.[0]).toEqual([
      { personaIds: ['p1', 'p2'], topic: 'Budget Q3', rounds: 2 },
    ]);
  });

  it('émet resume-discussion au clic sur une discussion', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    const discussionBtn = wrapper
      .findAll('.personas-history__item')
      .find((b) => b.text().includes('Question initiale'));
    await discussionBtn!.trigger('click');

    const payload = wrapper.emitted('resume-discussion')?.[0]?.[0] as {
      discussionId: string;
      personaIds: string[];
      messages: Array<{ content: string }>;
    };
    expect(payload.discussionId).toBe('disc-1');
    expect(payload.personaIds).toEqual(['p1']);
    expect(payload.messages[0]?.content).toBe('Question initiale');
  });
});
