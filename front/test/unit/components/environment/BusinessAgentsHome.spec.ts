import { shallowMount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BusinessAgentsHome from '@components/environment/BusinessAgentsHome.vue';
import type { ManagedConnector, PersonaInfo } from '@services/aiSidecar';

const agent: PersonaInfo = {
  id: 'org.rh',
  name: 'Camille RH',
  role: 'Référente ressources humaines',
  description: 'Répond aux questions RH et consulte les dossiers autorisés.',
  avatar_color: '#e0a93a',
  is_business_agent: true,
  tools: {
    allowed: [
      { connector_id: 'ihora', tool: 'employee.read' },
      { connector_id: 'ihora', tool: 'leave.read' },
    ],
  },
};

const connectors: ManagedConnector[] = [
  {
    id: 'ihora',
    name: 'Ihora',
    enabled: true,
    tools: [],
  },
];

describe('BusinessAgentsHome', () => {
  it('présente les outils à travers l’agent, regroupés par connecteur', () => {
    const wrapper = shallowMount(BusinessAgentsHome, {
      props: { agents: [agent], connectors },
      global: { stubs: { Lucide: true, PersonaAvatar: true } },
    });

    expect(wrapper.text()).toContain('Camille RH');
    expect(wrapper.text()).toContain('Ihora');
    expect(wrapper.text()).not.toContain('employee.read');
  });

  it('distingue la fiche agent de la demande adressée à Workproba', async () => {
    const wrapper = shallowMount(BusinessAgentsHome, {
      props: { agents: [agent], connectors },
      global: { stubs: { Lucide: true, PersonaAvatar: true } },
    });

    await wrapper.find('.business-agents-home__profile').trigger('click');
    expect(wrapper.emitted('view-agent')?.[0]).toEqual([agent]);

    await wrapper.find('.business-agents-home__consult').trigger('click');
    expect(wrapper.emitted('consult')?.[0]).toEqual([agent]);
  });
});
