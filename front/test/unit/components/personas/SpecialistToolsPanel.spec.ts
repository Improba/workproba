import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import SpecialistToolsPanel from '@components/personas/SpecialistToolsPanel.vue';
import type { PersonaInfo } from '@services/aiSidecar';

const businessAgent: PersonaInfo = {
  id: 'org.rh',
  name: 'Agent RH',
  role: 'RH',
  description: 'Regard RH',
  avatar_color: '#336699',
  is_business_agent: true,
  tools: {
    allowed: [
      { connector_id: 'ihora', tool: 'list_absences' },
      { connector_id: 'ihora', tool: 'get_timesheet' },
    ],
  },
};

describe('SpecialistToolsPanel', () => {
  it('affiche les outils allowed avec badges read/write', async () => {
    const wrapper = mount(SpecialistToolsPanel, {
      props: {
        persona: businessAgent,
        connectors: [
          {
            id: 'ihora',
            name: 'iHora',
            tools: [
              { name: 'list_absences', effect: 'read' },
              { name: 'get_timesheet', effect: 'write' },
            ],
          },
        ],
      },
      global: {
        mocks: {
          t: (key: string) => key,
        },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('list_absences');
    expect(wrapper.text()).toContain('get_timesheet');
    expect(wrapper.findAll('.specialist-tools__badge')).toHaveLength(2);
  });

  it('n\'affiche rien sans tools allowed', async () => {
    const wrapper = mount(SpecialistToolsPanel, {
      props: {
        persona: {
          id: 'p1',
          name: 'Legacy',
          role: 'PO',
          description: '',
          avatar_color: '#fff',
        },
      },
      global: {
        mocks: {
          t: (key: string) => key,
        },
      },
    });
    await flushPromises();

    expect(wrapper.find('.specialist-tools').exists()).toBe(false);
  });
});
