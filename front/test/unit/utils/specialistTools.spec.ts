import { describe, expect, it } from 'vitest';
import type { ManagedConnector } from '@services/aiSidecar';
import {
  isBusinessAgent,
  parseSpecialistTools,
  resolveManagedToolEffect,
  specialistAllowedTools,
} from '@utils/specialistTools';

describe('specialistTools', () => {
  it('parse les tools allowed d\'un agent métier', () => {
    const tools = parseSpecialistTools({
      allowed: [{ connector_id: 'ihora', tool: 'list_absences' }],
      forbidden: [],
    });
    expect(tools?.allowed).toEqual([{ connector_id: 'ihora', tool: 'list_absences' }]);
  });

  it('détecte un agent métier', () => {
    expect(isBusinessAgent({ is_business_agent: true } as never)).toBe(true);
    expect(isBusinessAgent({} as never)).toBe(false);
  });

  it('résout l\'effect read/write depuis le cache connecteurs', () => {
    const connectors: ManagedConnector[] = [
      {
        id: 'ihora',
        name: 'iHora',
        tools: [
          { name: 'list_absences', effect: 'read' },
          { name: 'update_project_member', effect: 'write' },
        ],
      },
    ];
    expect(
      resolveManagedToolEffect(connectors, { connector_id: 'ihora', tool: 'list_absences' }),
    ).toBe('read');
    expect(
      resolveManagedToolEffect(connectors, { connector_id: 'ihora', tool: 'update_project_member' }),
    ).toBe('write');
    expect(
      resolveManagedToolEffect(connectors, { connector_id: 'unknown', tool: 'foo' }),
    ).toBeNull();
  });

  it('extrait les tools allowed d\'un persona', () => {
    const persona = {
      id: 'org.gestionnaire',
      tools: {
        allowed: [{ connector_id: 'ihora', tool: 'get_timesheet' }],
      },
    };
    expect(specialistAllowedTools(persona as never)).toEqual([
      { connector_id: 'ihora', tool: 'get_timesheet' },
    ]);
  });
});
