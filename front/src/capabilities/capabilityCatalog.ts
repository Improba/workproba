import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
  PROJET_PLUGIN_ID,
} from '@composables/usePlugins';

export type CapabilityId =
  | 'regards'
  | 'projects'
  | 'web_navigation'
  | 'project_sync';

export type CapabilityStateKind =
  | 'active'
  | 'available'
  | 'blocked'
  | 'unavailable'
  | 'needs_setup'
  | 'coming_soon';

export type PrimarySurfaceType =
  | 'right_panel'
  | 'side_chat'
  | 'central_route'
  | 'nested';

export interface PrimarySurface {
  type: PrimarySurfaceType;
  /** Onglet panneau droit (`pluginId:slot`). */
  tabKey?: string;
  /** Plugin cible pour side chat. */
  pluginId?: string;
  /** Route centrale (réservé V2.2+). */
  routeName?: string;
  /** Capacité parente pour les surfaces imbriquées. */
  parentCapabilityId?: CapabilityId;
}

export interface CapabilityDefinition {
  id: CapabilityId;
  titleKey: string;
  descriptionKey: string;
  homeKey: string;
  icon: string;
  pluginIds: string[];
  primarySurface: PrimarySurface;
  /** Capacité parente (ex. synchronisation sous projets). */
  parentId?: CapabilityId;
  /** Affichée comme « bientôt disponible » en mode guidé. */
  comingSoonInGuided?: boolean;
}

export interface CapabilityState {
  kind: CapabilityStateKind;
  managedByOrganization?: boolean;
}

export const CAPABILITY_CATALOG: readonly CapabilityDefinition[] = [
  {
    id: 'regards',
    titleKey: 'capabilities.regards.title',
    descriptionKey: 'capabilities.regards.description',
    homeKey: 'capabilities.regards.home',
    icon: 'users',
    pluginIds: [PERSONAS_PLUGIN_ID],
    primarySurface: {
      type: 'side_chat',
      pluginId: PERSONAS_PLUGIN_ID,
    },
  },
  {
    id: 'projects',
    titleKey: 'capabilities.projects.title',
    descriptionKey: 'capabilities.projects.description',
    homeKey: 'capabilities.projects.home',
    icon: 'folder-kanban',
    pluginIds: [PROJET_PLUGIN_ID],
    primarySurface: {
      type: 'right_panel',
      tabKey: `${PROJET_PLUGIN_ID}:right_panel`,
    },
  },
  {
    id: 'web_navigation',
    titleKey: 'capabilities.webNavigation.title',
    descriptionKey: 'capabilities.webNavigation.description',
    homeKey: 'capabilities.webNavigation.home',
    icon: 'globe',
    pluginIds: [BROWSER_PLUGIN_ID],
    primarySurface: {
      type: 'right_panel',
      tabKey: `${BROWSER_PLUGIN_ID}:right_panel`,
    },
  },
  {
    id: 'project_sync',
    titleKey: 'capabilities.projectSync.title',
    descriptionKey: 'capabilities.projectSync.description',
    homeKey: 'capabilities.projectSync.home',
    icon: 'cloud',
    pluginIds: [CLOUD_PLUGIN_ID],
    parentId: 'projects',
    primarySurface: {
      type: 'nested',
      parentCapabilityId: 'projects',
      tabKey: `${CLOUD_PLUGIN_ID}:right_panel`,
    },
  },
] as const;

export function getCapabilityDefinition(id: CapabilityId): CapabilityDefinition | undefined {
  return CAPABILITY_CATALOG.find((cap) => cap.id === id);
}

export function getCapabilityForPlugin(pluginId: string): CapabilityDefinition | undefined {
  return CAPABILITY_CATALOG.find((cap) => cap.pluginIds.includes(pluginId));
}

export function getTopLevelCapabilities(): CapabilityDefinition[] {
  return CAPABILITY_CATALOG.filter((cap) => !cap.parentId);
}

export function getNestedCapabilities(parentId: CapabilityId): CapabilityDefinition[] {
  return CAPABILITY_CATALOG.filter((cap) => cap.parentId === parentId);
}
