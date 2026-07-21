import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  PERSONAS_PLUGIN_ID,
  PROJET_PLUGIN_ID,
} from '@composables/usePlugins';

export type LocalCapabilityId =
  | 'regards'
  | 'projects'
  | 'web_navigation'
  | 'workproba_cloud';

export type ManagedCapabilityId = `managed:${string}`;

export type CapabilityId = LocalCapabilityId | ManagedCapabilityId;

export type CapabilitySource = 'local' | 'managed';

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
  /** Capacité parente (ex. sous Workproba Cloud). */
  parentId?: CapabilityId;
  /** Affichée comme « bientôt disponible » en mode guidé. */
  comingSoonInGuided?: boolean;
  /** Origine produit : locale (plugin) ou managée (via Workproba Cloud). */
  source?: CapabilitySource;
  /** Id connecteur cloud quand `source === 'managed'`. */
  managedConnectorId?: string;
  /** Titre / description résolus (API), sans clé i18n. */
  resolvedTitle?: string;
  resolvedDescription?: string;
}

export interface CapabilityState {
  kind: CapabilityStateKind;
  managedByOrganization?: boolean;
}

/** Connecteurs techniques masqués en mode guidé dans le hub Capacités. */
export const GUIDED_HIDDEN_MANAGED_CONNECTOR_IDS: readonly string[] = [
  'echo',
  'ihora.shaped',
];

/**
 * Ordre produit : Workproba Cloud en premier (seul connecteur bureau),
 * puis capacités locales. La gestion de projet (`projects`) est une
 * sous-capacité de Workproba Cloud.
 */
export const CAPABILITY_CATALOG: readonly CapabilityDefinition[] = [
  {
    id: 'workproba_cloud',
    titleKey: 'capabilities.workprobaCloud.title',
    descriptionKey: 'capabilities.workprobaCloud.description',
    homeKey: 'capabilities.workprobaCloud.home',
    icon: 'cloud',
    pluginIds: [CLOUD_PLUGIN_ID],
    primarySurface: {
      type: 'right_panel',
      tabKey: `${CLOUD_PLUGIN_ID}:right_panel`,
    },
    source: 'local',
  },
  {
    id: 'projects',
    titleKey: 'capabilities.projects.title',
    descriptionKey: 'capabilities.projects.description',
    homeKey: 'capabilities.projects.home',
    icon: 'folder-kanban',
    pluginIds: [PROJET_PLUGIN_ID],
    parentId: 'workproba_cloud',
    primarySurface: {
      type: 'right_panel',
      tabKey: `${PROJET_PLUGIN_ID}:right_panel`,
    },
    source: 'local',
  },
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
    source: 'local',
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
    source: 'local',
  },
] as const;

export function isManagedCapabilityId(id: CapabilityId): boolean {
  return typeof id === 'string' && id.startsWith('managed:');
}

export function managedCapabilityId(connectorId: string): ManagedCapabilityId {
  return `managed:${connectorId}`;
}

export function connectorIdFromManagedCapability(
  id: ManagedCapabilityId,
): string {
  return id.slice('managed:'.length);
}

export function getCapabilityDefinition(
  id: CapabilityId,
): CapabilityDefinition | undefined {
  if (isManagedCapabilityId(id)) return undefined;
  return CAPABILITY_CATALOG.find((cap) => cap.id === id);
}

export function getCapabilityForPlugin(
  pluginId: string,
): CapabilityDefinition | undefined {
  return CAPABILITY_CATALOG.find((cap) => cap.pluginIds.includes(pluginId));
}

export function getTopLevelCapabilities(): CapabilityDefinition[] {
  return CAPABILITY_CATALOG.filter((cap) => !cap.parentId);
}

export function getNestedCapabilities(
  parentId: CapabilityId,
): CapabilityDefinition[] {
  return CAPABILITY_CATALOG.filter((cap) => cap.parentId === parentId);
}

export function buildManagedCapabilityDefinition(input: {
  connectorId: string;
  name: string;
  description?: string;
}): CapabilityDefinition {
  const id = managedCapabilityId(input.connectorId);
  const title = input.name.trim() || input.connectorId;
  return {
    id,
    titleKey: 'capabilities.managed.title',
    descriptionKey: 'capabilities.managed.description',
    homeKey: 'capabilities.managed.home',
    icon: 'puzzle',
    pluginIds: [CLOUD_PLUGIN_ID],
    parentId: 'workproba_cloud',
    source: 'managed',
    managedConnectorId: input.connectorId,
    resolvedTitle: title,
    resolvedDescription: input.description?.trim() || undefined,
    primarySurface: {
      // Pas de domicile UI : activation locale uniquement.
      type: 'nested',
      parentCapabilityId: 'workproba_cloud',
    },
  };
}
