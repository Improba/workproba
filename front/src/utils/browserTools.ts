/** Outils agent du plugin workproba.browser (aligné sur manifest.py). */
export const BROWSER_AGENT_TOOL_NAMES = [
  'browser_navigate',
  'browser_click',
  'browser_extract',
  'browser_type',
  'browser_scroll',
  'browser_press',
  'browser_back',
  'browser_forward',
] as const;

export type BrowserAgentToolName = (typeof BROWSER_AGENT_TOOL_NAMES)[number];

export function isBrowserAgentTool(name: string): name is BrowserAgentToolName {
  return (BROWSER_AGENT_TOOL_NAMES as readonly string[]).includes(name);
}

/** Retire screenshot_b64 avant sérialisation dans l'historique modèle. */
export function sanitizeBrowserToolResultForHistory(
  toolName: string,
  result: unknown,
): unknown {
  if (!isBrowserAgentTool(toolName) || result == null || typeof result !== 'object') {
    return result;
  }
  const record = { ...(result as Record<string, unknown>) };
  delete record.screenshot_b64;
  return record;
}
