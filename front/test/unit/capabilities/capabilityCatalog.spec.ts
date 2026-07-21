import { describe, expect, it } from 'vitest';
import {
  CAPABILITY_CATALOG,
  GUIDED_HIDDEN_MANAGED_CONNECTOR_IDS,
  buildManagedCapabilityDefinition,
  getCapabilityDefinition,
  getCapabilityForPlugin,
  getNestedCapabilities,
  getTopLevelCapabilities,
  isManagedCapabilityId,
  managedCapabilityId,
} from '@capabilities/capabilityCatalog';
import { CLOUD_PLUGIN_ID, PERSONAS_PLUGIN_ID, PROJET_PLUGIN_ID } from '@composables/usePlugins';

describe('capabilityCatalog', () => {
  it('place Workproba Cloud en premier et nest la gestion de projet', () => {
    const ids = CAPABILITY_CATALOG.map((cap) => cap.id);
    expect(ids).toEqual(['workproba_cloud', 'projects', 'regards', 'web_navigation']);
  });

  it('chaque capacité a un titre, une icône et un domicile', () => {
    for (const cap of CAPABILITY_CATALOG) {
      expect(cap.titleKey, cap.id).toMatch(/^capabilities\./);
      expect(cap.icon.trim(), cap.id).not.toBe('');
      expect(cap.homeKey, cap.id).toMatch(/^capabilities\./);
      expect(cap.descriptionKey, cap.id).toMatch(/^capabilities\./);
      expect(cap.pluginIds.length, cap.id).toBeGreaterThan(0);
      expect(cap.primarySurface.type, cap.id).toBeTruthy();
    }
  });

  it('expose le top-level et les enfants sous Workproba Cloud', () => {
    expect(getTopLevelCapabilities().map((cap) => cap.id)).toEqual([
      'workproba_cloud',
      'regards',
      'web_navigation',
    ]);
    expect(getNestedCapabilities('workproba_cloud').map((cap) => cap.id)).toEqual(['projects']);
    expect(getCapabilityDefinition('projects')?.parentId).toBe('workproba_cloud');
    expect(getCapabilityDefinition('workproba_cloud')?.pluginIds).toEqual([CLOUD_PLUGIN_ID]);
    expect(getCapabilityDefinition('projects')?.pluginIds).toEqual([PROJET_PLUGIN_ID]);
  });

  it('résout la capacité à partir d\'un pluginId', () => {
    expect(getCapabilityForPlugin(PERSONAS_PLUGIN_ID)?.id).toBe('regards');
    expect(getCapabilityForPlugin(CLOUD_PLUGIN_ID)?.id).toBe('workproba_cloud');
    expect(getCapabilityForPlugin(PROJET_PLUGIN_ID)?.id).toBe('projects');
    expect(getCapabilityForPlugin('unknown.plugin')).toBeUndefined();
  });

  it('construit des capacités managées sous Workproba Cloud', () => {
    const managed = buildManagedCapabilityDefinition({
      connectorId: 'ihora',
      name: 'IHora',
      description: 'Absences et temps',
    });
    expect(managed.id).toBe('managed:ihora');
    expect(isManagedCapabilityId(managed.id)).toBe(true);
    expect(managedCapabilityId('ihora')).toBe('managed:ihora');
    expect(managed.parentId).toBe('workproba_cloud');
    expect(managed.source).toBe('managed');
    expect(managed.resolvedTitle).toBe('IHora');
    expect(GUIDED_HIDDEN_MANAGED_CONNECTOR_IDS).toContain('echo');
    expect(GUIDED_HIDDEN_MANAGED_CONNECTOR_IDS).toContain('ihora.shaped');
  });
});
