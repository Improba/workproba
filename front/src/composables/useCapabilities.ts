import { computed, type ComputedRef } from 'vue';
import {
  CAPABILITY_CATALOG,
  getCapabilityDefinition,
  getNestedCapabilities,
  type CapabilityDefinition,
  type CapabilityId,
  type CapabilityState,
} from '@capabilities/capabilityCatalog';
import {
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  isUpcomingPluginId,
  usePlugins,
} from './usePlugins';
import { useAppSettings } from './useAppSettings';
import { useShellSurfaces } from './useShellSurfaces';

export interface CapabilityView {
  definition: CapabilityDefinition;
  state: CapabilityState;
}

function isGuidedMode(settingsLocked: boolean, settingsMode: string): boolean {
  return settingsLocked || settingsMode !== 'advanced';
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

function computeCapabilityState(
  definition: CapabilityDefinition,
  pluginIdsInstalled: Set<string>,
  activePluginIds: Set<string>,
  settingsLocked: boolean,
  settingsMode: string,
  pluginsAllowed: string[] | null | undefined,
  permissionsNetwork: boolean,
  permissionsProjectSync: boolean,
  permissionsNetworkImprobaCloud: boolean,
): CapabilityState {
  const guided = isGuidedMode(settingsLocked, settingsMode);
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

  if (definition.comingSoonInGuided && guided) {
    return { kind: 'coming_soon' };
  }

  if (definition.pluginIds.some((id) => isUpcomingPluginId(id))) {
    return { kind: 'coming_soon' };
  }

  if (capabilityPluginsActive && dependenciesActive) {
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
}

export function useCapabilities(): UseCapabilitiesReturn {
  const { plugins, activePluginIds, activatePlugin, deactivatePlugin } = usePlugins();
  const { settings, settingsLocked, settingsMode, permissionsNetwork, permissionsProjectSync, permissionsNetworkImprobaCloud } = useAppSettings();

  const {
    openRightPanel,
    openSideChat,
    closeCapabilities,
  } = useShellSurfaces();

  const pluginIdsInstalled = computed(
    () => new Set(plugins.value.map((p) => p.manifest.id)),
  );
  const activeIds = computed(() => new Set(activePluginIds.value));

  function buildView(definition: CapabilityDefinition): CapabilityView {
    return {
      definition,
      state: computeCapabilityState(
        definition,
        pluginIdsInstalled.value,
        activeIds.value,
        settingsLocked.value,
        settingsMode.value,
        settings.value.pluginsAllowed ?? null,
        permissionsNetwork.value,
        permissionsProjectSync.value,
        permissionsNetworkImprobaCloud.value,
      ),
    };
  }

  const capabilities = computed(() =>
    CAPABILITY_CATALOG.map((definition) => buildView(definition)),
  );

  function getById(id: CapabilityId): CapabilityView | undefined {
    const definition = getCapabilityDefinition(id);
    return definition ? buildView(definition) : undefined;
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
    openSurface(view.definition);
  }

  async function activateAndOpen(id: CapabilityId): Promise<void> {
    const view = getById(id);
    if (!view) return;
    if (view.state.kind === 'blocked' || view.state.kind === 'unavailable') return;
    if (view.state.kind === 'coming_soon') return;

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
    const definition = getCapabilityDefinition(id);
    if (!definition) return;

    for (const nested of getNestedCapabilities(id)) {
      await deactivate(nested.id);
    }

    for (const pluginId of definition.pluginIds) {
      if (activeIds.value.has(pluginId)) {
        await deactivatePlugin(pluginId);
      }
    }
  }

  return {
    capabilities,
    getById,
    activateAndOpen,
    open,
    deactivate,
  };
}

export function getNestedCapabilityViews(parentId: CapabilityId): CapabilityDefinition[] {
  return getNestedCapabilities(parentId);
}
