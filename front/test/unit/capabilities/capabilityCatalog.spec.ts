import { describe, expect, it } from 'vitest';
import {
  CAPABILITY_CATALOG,
  getCapabilityDefinition,
  getCapabilityForPlugin,
  getNestedCapabilities,
  getTopLevelCapabilities,
} from '@capabilities/capabilityCatalog';
import { CLOUD_PLUGIN_ID, PERSONAS_PLUGIN_ID } from '@composables/usePlugins';

describe('capabilityCatalog', () => {
  it('définit les quatre capacités attendues', () => {
    const ids = CAPABILITY_CATALOG.map((cap) => cap.id);
    expect(ids).toEqual(['regards', 'projects', 'web_navigation', 'project_sync']);
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

  it('expose les capacités de premier niveau et imbriquées', () => {
    expect(getTopLevelCapabilities().map((cap) => cap.id)).toEqual([
      'regards',
      'projects',
      'web_navigation',
    ]);
    expect(getNestedCapabilities('projects').map((cap) => cap.id)).toEqual(['project_sync']);
    expect(getCapabilityDefinition('regards')?.primarySurface.type).toBe('side_chat');
    expect(getCapabilityDefinition('projects')?.primarySurface.tabKey).toBe(
      'workproba.projet:right_panel',
    );
    expect(getCapabilityDefinition('project_sync')?.primarySurface.type).toBe('nested');
    expect(getCapabilityDefinition('project_sync')?.pluginIds).toEqual(['workproba.cloud']);
  });

  it('résout la capacité à partir d\'un pluginId', () => {
    expect(getCapabilityForPlugin(PERSONAS_PLUGIN_ID)?.id).toBe('regards');
    expect(getCapabilityForPlugin(CLOUD_PLUGIN_ID)?.id).toBe('project_sync');
    expect(getCapabilityForPlugin('unknown.plugin')).toBeUndefined();
  });
});
