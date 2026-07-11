import { computed, defineAsyncComponent, type Component, type ComputedRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { pluginSlotComponents, pluginSlotMeta } from '../plugins/pluginSlotComponents';
import { usePlugins } from './usePlugins';
import type { PluginInfo } from './useDesktop';

export interface PluginSlotTab {
  key: string;
  pluginId: string;
  label: string;
  icon: string;
  component: Component;
}

function buildSlotTabs(
  slotName: string,
  activePluginIds: string[],
  plugins: PluginInfo[],
  t: (key: string) => string,
): PluginSlotTab[] {
  const tabs: PluginSlotTab[] = [];

  for (const pluginId of activePluginIds) {
    const plugin = plugins.find((p) => p.manifest.id === pluginId);
    if (!plugin?.manifest.uiSlots.includes(slotName)) continue;

    const key = `${pluginId}:${slotName}`;
    const loader = pluginSlotComponents[key];
    if (!loader) continue;

    const meta = pluginSlotMeta[key];
    tabs.push({
      key,
      pluginId,
      label: meta ? t(meta.labelKey) : pluginId,
      icon: meta?.icon ?? 'puzzle',
      component: defineAsyncComponent(loader),
    });
  }

  return tabs;
}

export interface UsePluginSlotsReturn {
  rightPanelPluginTabs: ComputedRef<PluginSlotTab[]>;
  sideChatPluginPanels: ComputedRef<PluginSlotTab[]>;
}

export function usePluginSlots(): UsePluginSlotsReturn {
  const { plugins, activePluginIds } = usePlugins();
  const { t } = useI18n();

  const rightPanelPluginTabs = computed(() =>
    buildSlotTabs('right_panel', activePluginIds.value, plugins.value, t),
  );

  const sideChatPluginPanels = computed(() =>
    buildSlotTabs('side_chat', activePluginIds.value, plugins.value, t),
  );

  return {
    rightPanelPluginTabs,
    sideChatPluginPanels,
  };
}
