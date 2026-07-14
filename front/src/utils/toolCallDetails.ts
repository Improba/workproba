import type { ChatToolCall } from '#types';
import { t } from './i18nT';

/**
 * Détails lisibles d'un appel d'outil pour la « vue détaillée ».
 */

export interface ToolCallDetailRow {
  label: string;
  value: string;
}

export interface ToolCallDetails {
  target?: string;
  location?: string;
  outcome?: string;
  rows: ToolCallDetailRow[];
}

function basename(value: string): string {
  const cleaned = value.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned) return '';
  const parts = cleaned.split(/[/\\]/);
  return parts[parts.length - 1] || cleaned;
}

function formatLocation(subdir: string): string {
  const cleaned = subdir.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned || cleaned === '.') return t('toolCalls.ofSpace');
  return t('toolCalls.ofFolder', { name: basename(cleaned) });
}

function formatLocationSubject(subdir: string): string {
  const cleaned = subdir.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned || cleaned === '.') return t('toolCalls.theSpace');
  return t('toolCalls.theFolder', { name: basename(cleaned) });
}

function formatQuery(query: string): string {
  const text = query.trim();
  if (!text) return '';
  if (text.length > 80) return `${text.slice(0, 77)}…`;
  return text;
}

function formatFilePath(path: string): string {
  const cleaned = path.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned) return '';
  const parts = cleaned.split(/[/\\]/);
  return parts[parts.length - 1] || cleaned;
}

function dirname(path: string): string {
  const cleaned = path.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned) return '';
  const parts = cleaned.split(/[/\\]/);
  parts.pop();
  if (parts.length === 0) return t('toolCalls.spaceRoot');
  return parts.join('/');
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function pluralize(key: string, count: number): string {
  return t(key, count, { count });
}

/** Construit le détail lisible d'un tool call (nom + args + résultat). */
export function buildToolCallDetails(toolCall: ChatToolCall): ToolCallDetails {
  const args = toolCall.args ?? {};
  const result = toolCall.result;
  const rows: ToolCallDetailRow[] = [];
  let target: string | undefined;
  let location: string | undefined;
  let outcome: string | undefined;

  switch (toolCall.name) {
    case 'list_files': {
      const subdir = asString(args.subdir);
      location = formatLocationSubject(subdir);
      target = t('toolCalls.listContent', { location: formatLocation(subdir) });
      if (result && typeof result === 'object') {
        const entries = asList((result as Record<string, unknown>).entries);
        const count = entries.length;
        outcome =
          count === 0
            ? t('toolCalls.noElements')
            : pluralize('toolCalls.elementsListed', count);
      }
      break;
    }
    case 'search_kb': {
      const query = formatQuery(asString(args.query));
      target = query
        ? t('toolCalls.searchQuery', { query })
        : t('toolCalls.searchFiles');
      location = t('toolCalls.spaceMemory');
      if (result && typeof result === 'object') {
        const results = asList((result as Record<string, unknown>).results);
        const count = results.length;
        outcome =
          count === 0
            ? t('toolCalls.noResults')
            : pluralize('toolCalls.resultsFound', count);
      }
      break;
    }
    case 'web_search': {
      const query = formatQuery(asString(args.query));
      target = query
        ? t('toolCalls.webSearchQuery', { query })
        : t('toolCalls.webSearchGeneric');
      location = t('toolCalls.publicWeb');
      if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>;
        const results = asList(r.results);
        const count = results.length;
        outcome =
          count === 0
            ? t('toolCalls.noResults')
            : pluralize('toolCalls.webResultsFound', count);
        const backend = asString(r.backend);
        if (backend) {
          rows.push({ label: t('toolCalls.webSearchBackend'), value: backend });
        }
        for (const item of results.slice(0, 5)) {
          if (!item || typeof item !== 'object') continue;
          const entry = item as Record<string, unknown>;
          const url = asString(entry.url);
          const title = asString(entry.title) || url;
          if (url) {
            rows.push({ label: title, value: url });
          }
        }
      }
      break;
    }
    case 'read_documents':
    case 'read_document': {
      const paths = asList(args.paths).map((p) => asString(p)).filter(Boolean);
      const docId = asString(args.document_id);
      if (paths.length) {
        target = paths.map(formatFilePath).join(', ');
        location =
          paths.length === 1
            ? t('toolCalls.inFolder', { path: dirname(paths[0]) })
            : undefined;
      } else if (docId) {
        target = formatFilePath(docId);
        location = t('toolCalls.inFolder', { path: dirname(docId) });
      }
      if (result && typeof result === 'object') {
        const meta = (result as Record<string, unknown>).metadata;
        if (meta && typeof meta === 'object') {
          const m = meta as Record<string, unknown>;
          const pages = asNumber(m.pages_total);
          const lines = asNumber(m.lines_returned);
          if (pages && pages > 0) {
            outcome = pluralize('toolCalls.pagesRead', pages);
          } else if (lines && lines > 0) {
            outcome = pluralize('toolCalls.linesReturned', lines);
          }
        }
      }
      break;
    }
    case 'run_code': {
      const lang = asString(args.language) || asString(args.lang) || 'code';
      target = t('toolCalls.runLanguage', { lang });
      location = t('toolCalls.isolatedSandbox');
      if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>;
        const stdout = asString(r.stdout);
        const files = asList(r.files);
        const plots = asList(r.plots);
        const parts: string[] = [];
        if (stdout) parts.push(t('toolCalls.outputProduced'));
        if (files.length) parts.push(pluralize('toolCalls.filesCount', files.length));
        if (plots.length) parts.push(pluralize('toolCalls.plotsCount', plots.length));
        outcome = parts.length ? parts.join(', ') : t('toolCalls.calculationDone');
      }
      break;
    }
    case 'generate_document': {
      const name = formatFilePath(
        asString(args.name) || asString(args.path) || toolCall.filePath || '',
      );
      target = name
        ? t('toolCalls.createDocument', { name })
        : t('toolCalls.createDocumentGeneric');
      if (toolCall.filePath) {
        location = t('toolCalls.inFolder', { path: dirname(toolCall.filePath) });
      }
      if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>;
        if (r.cancelled) outcome = t('toolCalls.creationCancelled');
        else if (toolCall.status === 'success') outcome = t('toolCalls.documentSaved');
      }
      break;
    }
    default: {
      target = toolCall.humanSummary || undefined;
    }
  }

  if (target) rows.push({ label: t('common.action'), value: target });
  if (location) rows.push({ label: t('common.location'), value: location });
  if (outcome) rows.push({ label: t('common.outcome'), value: outcome });

  const dur = durationLabel(toolCall);
  if (dur) rows.push({ label: t('common.duration'), value: dur });

  rows.push({ label: t('common.status'), value: statusLabel(toolCall.status) });

  return { target, location, outcome, rows };
}

export function statusLabel(status: ChatToolCall['status']): string {
  switch (status) {
    case 'running':
      return t('toolCalls.statusRunning');
    case 'awaiting_confirmation':
      return t('toolCalls.statusAwaitingConfirmation');
    case 'success':
      return t('toolCalls.statusSuccess');
    case 'error':
      return t('toolCalls.statusError');
    case 'pending':
    default:
      return t('toolCalls.statusPending');
  }
}

export function durationLabel(toolCall: ChatToolCall): string {
  const { startedAt, endedAt } = toolCall;
  if (!startedAt) return '';
  const end = endedAt ?? Date.now();
  const ms = Math.max(0, end - startedAt);
  if (ms < 1000) return t('toolCalls.durationMs', { ms });
  return t('toolCalls.durationSec', { sec: (ms / 1000).toFixed(1) });
}
