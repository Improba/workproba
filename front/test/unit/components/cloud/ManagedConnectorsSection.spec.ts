import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ManagedConnectorsSection from '@components/cloud/ManagedConnectorsSection.vue';
import type { ManagedConnector } from '@services/aiSidecar';

const sampleConnectors: ManagedConnector[] = [
  {
    id: 'ihora',
    name: 'Ihora',
    description: 'RH org',
    tools: [
      {
        name: 'list_absences',
        description: 'Lister les absences',
        visibility: 'guided',
      },
      {
        name: 'get_timesheet',
        description: 'Timesheet avancé',
        visibility: 'advanced',
      },
    ],
  },
];

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('ManagedConnectorsSection', () => {
  it('affiche les tools guidés sous chaque connecteur', () => {
    const wrapper = mount(ManagedConnectorsSection, {
      props: {
        connectors: sampleConnectors,
        loading: false,
        error: null,
      },
    });

    expect(wrapper.text()).toContain('list_absences');
    expect(wrapper.text()).toContain('Lister les absences');
    expect(wrapper.text()).not.toContain('get_timesheet');
  });

  it('affiche aussi les tools avancés en mode technique', () => {
    const wrapper = mount(ManagedConnectorsSection, {
      props: {
        connectors: sampleConnectors,
        loading: false,
        error: null,
        showAdvancedTools: true,
      },
    });

    expect(wrapper.text()).toContain('get_timesheet');
    expect(wrapper.text()).toContain('Timesheet avancé');
  });
});
