import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import PersonasMeetingView from '@components/personas/PersonasMeetingView.vue';
import type { MeetingState } from '@composables/usePersonas';

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    findPersona: (id: string) => ({ id, name: id, role: '', avatar_color: '#000' }),
    activeSet: { value: null },
  }),
  formatMeetingMarkdown: vi.fn(() => ''),
}));

vi.mock('@composables/usePlugins', () => ({
  usePlugins: () => ({
    isProjetPluginActive: { value: false },
  }),
}));

function meetingStateWithError(error: string): MeetingState {
  return {
    topic: 'Sujet',
    personaIds: ['p1'],
    rounds: 2,
    turns: [],
    summary: '',
    streaming: false,
    error,
  };
}

describe('PersonasMeetingView', () => {
  it('affiche le message cloud pour cloud_not_enrolled', () => {
    const wrapper = mount(PersonasMeetingView, {
      props: {
        personas: [],
        meetingState: meetingStateWithError('cloud_not_enrolled'),
      },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasPicker: true,
          PersonasHistoryPanel: true,
          PersonasConfidentialityHint: true,
          PublishToProjectDialog: true,
        },
      },
    });

    expect(wrapper.find('.personas-meeting__error').text()).toContain(
      'Connectez-vous à Improba Cloud',
    );
    expect(wrapper.find('.personas-meeting__error').text()).not.toContain(
      'La réunion a échoué',
    );
  });

  it('affiche le message clé API pour missing_api_key', () => {
    const wrapper = mount(PersonasMeetingView, {
      props: {
        personas: [],
        meetingState: meetingStateWithError('missing_api_key'),
      },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasPicker: true,
          PersonasHistoryPanel: true,
          PersonasConfidentialityHint: true,
          PublishToProjectDialog: true,
        },
      },
    });

    expect(wrapper.find('.personas-meeting__error').text()).toContain('Clé API manquante');
  });

  it('affiche meetingFailed pour une erreur non readiness', () => {
    const wrapper = mount(PersonasMeetingView, {
      props: {
        personas: [],
        meetingState: meetingStateWithError('stream_timeout'),
      },
      global: {
        stubs: {
          Lucide: true,
          PersonaAvatar: true,
          PersonasPicker: true,
          PersonasHistoryPanel: true,
          PersonasConfidentialityHint: true,
          PublishToProjectDialog: true,
        },
      },
    });

    expect(wrapper.find('.personas-meeting__error').text()).toContain(
      'La réunion a échoué',
    );
  });
});
