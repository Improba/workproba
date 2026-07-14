import type { BrowserAgentToolName } from '@utils/browserTools';

export interface BrowserAiActionOverlay {
  toolName: BrowserAgentToolName | string;
  label: string;
}

/** Libellé court pour le badge d'action IA sur le screenshot. */
export function buildBrowserAiActionOverlay(
  toolName: string,
  result: Record<string, unknown>,
): BrowserAiActionOverlay | null {
  const summary =
    typeof result.human_summary === 'string' ? result.human_summary.trim() : '';
  if (summary) {
    return { toolName, label: summary };
  }

  switch (toolName) {
    case 'browser_navigate':
      if (typeof result.url === 'string' && result.url) {
        return { toolName, label: result.url };
      }
      break;
    case 'browser_click':
      return { toolName, label: 'Click' };
    case 'browser_type':
      return { toolName, label: 'Type' };
    case 'browser_scroll':
      return { toolName, label: 'Scroll' };
    case 'browser_press':
      return { toolName, label: 'Key' };
    case 'browser_extract':
      return { toolName, label: 'Extract' };
    case 'browser_back':
      return { toolName, label: 'Back' };
    case 'browser_forward':
      return { toolName, label: 'Forward' };
    default:
      break;
  }
  return null;
}
