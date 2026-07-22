export const pluginSlotComponents: Record<string, () => Promise<{ default: unknown }>> = {
  'workproba.projet:right_panel': () => import('@components/workproba/ProjectPanel.vue'),
  'workproba.browser:right_panel': () => import('@components/browser/BrowserPanel.vue'),
  'workproba.personas:side_chat': () => import('@components/personas/PersonasSideChat.vue'),
};

export const pluginSlotMeta: Record<string, { labelKey: string; icon: string }> = {
  'workproba.projet:right_panel': { labelKey: 'plugin.workproba.projet.tabLabel', icon: 'folder-kanban' },
  'workproba.browser:right_panel': { labelKey: 'browser.tabLabel', icon: 'globe' },
  'workproba.personas:side_chat': { labelKey: 'plugin.workproba.personas.sideChat.title', icon: 'users' },
};
