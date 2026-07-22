import { computed, type ComputedRef } from 'vue';
import {
  CAPABILITY_CATALOG,
  buildManagedCapabilityDefinition,
  connectorIdFromManagedCapability,
  getCapabilityDefinition,
  getNestedCapabilities,
  isManagedCapabilityId,
  managedCapabilityId,
  type CapabilityDefinition,
  type CapabilityId,
  type CapabilityState,
  type ManagedCapabilityId,
} from '@capabilities/capabilityCatalog';
import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  isUpcomingPluginId,
  usePlugins,
} from './usePlugins';
import { useAppSettings } from './useAppSettings';
import { useShellSurfaces } from './useShellSurfaces';
import { useCloud } from './useCloud';

export interface CapabilityView {
  definition: CapabilityDefinition;
  state: CapabilityState;
}

function isPluginBlockedByPreset(
  pluginId: string,
  settingsLocked: boolean,
  pluginsAllowed: string[] | null | undefined,
  permissionsNetwork: boolean,
  permissionsProjectSync: boolean,
  permissionsNetworkImprobaCloud: boolean,
): boolean {
  if (!settingsLocked) return false;
  if (pluginsAllowed?.length && !pluginsAllowed.includes(pluginId)) return true;
  if (
    !permissionsNetwork
    && (pluginId === BROWSER_PLUGIN_ID || pluginId === CLOUD_PLUGIN_ID)
  ) {
    return true;
  }
  if (!permissionsNetworkImprobaCloud && pluginId === CLOUD_PLUGIN_ID) {
    return true;
  }
  if (!permissionsProjectSync && pluginId === CLOUD_PLUGIN_ID) {
    return true;
  }
  return false;
}

function collectRequiredPluginIds(definition: CapabilityDefinition): string[] {
  const ids = [...definition.pluginIds];
  if (definition.parentId) {
    const parent = getCapabilityDefinition(definition.parentId);
    if (parent) {
      for (const pluginId of parent.pluginIds) {
        if (!ids.includes(pluginId)) ids.push(pluginId);
      }
    }
  }
  return ids;
}

function computeLocalCapabilityState(
  definition: CapabilityDefinition,
  pluginIdsInstalled: Set<string>,
  activePluginIds: Set<string>,
  settingsLocked: boolean,
  pluginsAllowed: string[] | null | undefined,
  permissionsNetwork: boolean,
  permissionsProjectSync: boolean,
  permissionsNetworkImprobaCloud: boolean,
  cloudEnrolled: boolean,
): CapabilityState {
  const requiredPluginIds = collectRequiredPluginIds(definition);

  const missingPlugins = requiredPluginIds.filter((id) => !pluginIdsInstalled.has(id));
  if (missingPlugins.length > 0) {
    return { kind: 'unavailable' };
  }

  const blockedPlugins = requiredPluginIds.filter((id) =>
    isPluginBlockedByPreset(
      id,
      settingsLocked,
      pluginsAllowed,
      permissionsNetwork,
      permissionsProjectSync,
      permissionsNetworkImprobaCloud,
    ),
  );
  const capabilityPluginsActive = definition.pluginIds.every((id) =>
    activePluginIds.has(id),
  );
  const dependenciesActive = requiredPluginIds.every((id) => activePluginIds.has(id));

  if (blockedPlugins.length > 0 && !capabilityPluginsActive) {
    return { kind: 'blocked', managedByOrganization: true };
  }

  if (definition.comingSoonInGuided && settingsLocked) {
    return { kind: 'coming_soon' };
  }

  if (definition.pluginIds.some((id) => isUpcomingPluginId(id))) {
    return { kind: 'coming_soon' };
  }

  if (capabilityPluginsActive && dependenciesActive) {
    if (definition.id === 'workproba_cloud' && !cloudEnrolled) {
      return { kind: 'needs_setup' };
    }
    return { kind: 'active' };
  }

  return { kind: 'available' };
}

export interface UseCapabilitiesReturn {
  capabilities: ComputedRef<CapabilityView[]>;
  getById: (id: CapabilityId) => CapabilityView | undefined;
  activateAndOpen: (id: CapabilityId) => Promise<void>;
  open: (id: CapabilityId) => void;
  deactivate: (id: CapabilityId) => Promise<void>;
  refreshManaged: () => Promise<void>;
}

export function useCapabilities(): UseCapabilitiesReturn {
  const { plugins, activePluginIds, activatePlugin, deactivatePlugin } = usePlugins();
  const {
    settings,
    settingsLocked,
    permissionsNetwork,
    permissionsProjectSync,
    permissionsNetworkImprobaCloud,
  } = useAppSettings();
  const {
    isEnrolled,
    connectors,
    init: initCloud,
    setManagedConnectorEnabled,
  } = useCloud();

  const {
    openRightPanel,
    openSideChat,
    closeCapabilities,
  } = useShellSurfaces();

  const pluginIdsInstalled = computed(
    () => new Set(plugins.value.map((p) => p.manifest.id)),
  );
  const activeIds = computed(() => new Set(activePluginIds.value));

  function buildLocalView(definition: CapabilityDefinition): CapabilityView {
    return {
      definition,
      state: computeLocalCapabilityState(
        definition,
        pluginIdsInstalled.value,
        activeIds.value,
        settingsLocked.value,
        settings.value.pluginsAllowed ?? null,
        permissionsNetwork.value,
        permissionsProjectSync.value,
        permissionsNetworkImprobaCloud.value,
        isEnrolled.value,
      ),
    };
  }

  function buildManagedViews(): CapabilityView[] {
    const cloudActive = activeIds.value.has(CLOUD_PLUGIN_ID);
    if (!cloudActive || !isEnrolled.value) {
      return [];
    }

    return connectors.value.map((connector) => {
      const definition = buildManagedCapabilityDefinition({
        connectorId: connector.id,
        name: connector.name,
        description: connector.description,
        enableByDefaultInProjects: connector.enableByDefaultInProjects,
      });
      const locallyEnabled = connector.enabled !== false;
      return {
        definition,
        state: {
          kind: (locallyEnabled ? 'active' : 'available') as CapabilityState['kind'],
          managedByOrganization: true,
        },
      };
    });
  }

  const capabilities = computed(() => [
    ...CAPABILITY_CATALOG.map((definition) => buildLocalView(definition)),
    ...buildManagedViews(),
  ]);

  function getById(id: CapabilityId): CapabilityView | undefined {
    if (isManagedCapabilityId(id)) {
      return buildManagedViews().find((view) => view.definition.id === id);
    }
    const definition = getCapabilityDefinition(id);
    return definition ? buildLocalView(definition) : undefined;
  }

  function openSurface(definition: CapabilityDefinition): void {
    const surface = definition.primarySurface;

    switch (surface.type) {
      case 'right_panel':
        openRightPanel(surface.tabKey ?? 'files');
        break;
      case 'side_chat':
        if (surface.pluginId) openSideChat(surface.pluginId);
        break;
      case 'nested': {
        if (surface.tabKey) {
          openRightPanel(surface.tabKey);
          break;
        }
        const parent = surface.parentCapabilityId
          ? getCapabilityDefinition(surface.parentCapabilityId)
          : undefined;
        if (parent?.primarySurface.tabKey) {
          openRightPanel(parent.primarySurface.tabKey);
        }
        break;
      }
      case 'central_route':
        break;
      default:
        break;
    }
  }

  function open(id: CapabilityId): void {
    const view = getById(id);
    if (!view || view.state.kind === 'blocked' || view.state.kind === 'unavailable') {
      return;
    }
    // Capacités managées (ex. Ihora) : pas de domicile à ouvrir.
    if (isManagedCapabilityId(id) || view.definition.source === 'managed') {
      return;
    }
    openSurface(view.definition);
  }

  async function activateAndOpen(id: CapabilityId): Promise<void> {
    const view = getById(id);
    if (!view) return;
    if (view.state.kind === 'blocked' || view.state.kind === 'unavailable') return;
    if (view.state.kind === 'coming_soon') return;

    if (isManagedCapabilityId(id) || view.definition.source === 'managed') {
      const connectorId =
        view.definition.managedConnectorId
        ?? connectorIdFromManagedCapability(id as ManagedCapabilityId);
      const ok = await setManagedConnectorEnabled(connectorId, true);
      if (!ok) {
        throw new Error('managed_capability_enable_failed');
      }
      // Pas d'ouverture de panneau : activation locale uniquement.
      return;
    }

    const pluginIdsToActivate = [...view.definition.pluginIds];
    if (view.definition.parentId) {
      const parent = getCapabilityDefinition(view.definition.parentId);
      if (parent) {
        for (const pluginId of parent.pluginIds) {
          if (!pluginIdsToActivate.includes(pluginId)) {
            pluginIdsToActivate.unshift(pluginId);
          }
        }
      }
    }

    for (const pluginId of pluginIdsToActivate) {
      if (!activeIds.value.has(pluginId)) {
        await activatePlugin(pluginId);
      }
    }

    closeCapabilities();
    openSurface(view.definition);
  }

  async function deactivate(id: CapabilityId): Promise<void> {
    if (isManagedCapabilityId(id)) {
      const connectorId = connectorIdFromManagedCapability(id);
      const ok = await setManagedConnectorEnabled(connectorId, false);
      if (!ok) {
        throw new Error('managed_capability_disable_failed');
      }
      return;
    }

    const definition = getCapabilityDefinition(id);
    if (!definition) return;

    for (const nested of getNestedCapabilities(id)) {
      await deactivate(nested.id);
    }
    // Les vues managées sous Workproba Cloud sont dérivées de connectors + enroll :
    // elles disparaissent d'elles-mêmes une fois le plugin cloud désactivé.

    for (const pluginId of definition.pluginIds) {
      if (activeIds.value.has(pluginId)) {
        await deactivatePlugin(pluginId);
      }
    }
  }

  async function refreshManaged(): Promise<void> {
    // initCloud() rafraîchit déjà status + connectors si enrollé.
    await initCloud();
  }

  return {
    capabilities,
    getById,
    activateAndOpen,
    open,
    deactivate,
    refreshManaged,
  };
}

export function getNestedCapabilityViews(parentId: CapabilityId): CapabilityDefinition[] {
  return getNestedCapabilities(parentId);
}

export function findManagedCapabilityId(
  connectorId: string,
): ManagedCapabilityId {
  return managedCapabilityId(connectorId);
}

export function parseManagedConnectorId(
  id: ManagedCapabilityId,
): string {
  return connectorIdFromManagedCapability(id);
}
