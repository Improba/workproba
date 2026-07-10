import type { ChatToolCall } from '#types';

/**
 * Détails lisibles d'un appel d'outil pour la « vue détaillée ».
 *
 * Objectif (vue designer + front) : donner à l'utilisateur non-codeur un
 * contexte compréhensible — « où », « dans quoi », « combien », « combien de
 * temps » — plutôt qu'un dump JSON brut. Le brut technique reste accessible
 * dans un sous-bloc repliable (cf. ToolCallCard).
 */

export interface ToolCallDetailRow {
  label: string;
  value: string;
}

export interface ToolCallDetails {
  /** Phrase courte : la cible de l'action (fichier, dossier, requête…). */
  target?: string;
  /** Localisation / contexte (dans quel dossier, quel projet). */
  location?: string;
  /** Résultat lisible (combien d'éléments, pages, lignes, succès/erreur). */
  outcome?: string;
  /** Lignes ordonnées pour le rendu clé → valeur. */
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
  if (!cleaned || cleaned === '.') return 'du projet';
  return `du dossier ${basename(cleaned)}`;
}

function formatLocationSubject(subdir: string): string {
  const cleaned = subdir.trim().replace(/^[/\\]+|[/\\]+$/g, '');
  if (!cleaned || cleaned === '.') return 'le projet';
  return `le dossier ${basename(cleaned)}`;
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
  if (parts.length === 0) return 'racine du projet';
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
      target = `Liste du contenu ${formatLocation(subdir)}`;
      if (result && typeof result === 'object') {
        const entries = asList((result as Record<string, unknown>).entries);
        const count = entries.length;
        outcome =
          count === 0
            ? 'Aucun élément trouvé'
            : `${count} ${count === 1 ? 'élément' : 'éléments'} listés`;
      }
      break;
    }
    case 'search_kb': {
      const query = formatQuery(asString(args.query));
      target = query ? `Recherche : « ${query} »` : 'Recherche dans les fichiers';
      location = 'la mémoire du projet';
      if (result && typeof result === 'object') {
        const results = asList((result as Record<string, unknown>).results);
        const count = results.length;
        outcome =
          count === 0
            ? 'Aucun résultat'
            : `${count} ${count === 1 ? 'résultat' : 'résultats'} trouvé${count === 1 ? '' : 's'}`;
      }
      break;
    }
    case 'read_documents':
    case 'read_document': {
      const paths = asList(args.paths).map((p) => asString(p)).filter(Boolean);
      const docId = asString(args.document_id);
      if (paths.length) {
        target = paths.map(formatFilePath).join(', ');
        location = paths.length === 1 ? `dans ${dirname(paths[0])}` : undefined;
      } else if (docId) {
        target = formatFilePath(docId);
        location = `dans ${dirname(docId)}`;
      }
      if (result && typeof result === 'object') {
        const meta = (result as Record<string, unknown>).metadata;
        if (meta && typeof meta === 'object') {
          const m = meta as Record<string, unknown>;
          const pages = asNumber(m.pages_total);
          const lines = asNumber(m.lines_returned);
          if (pages && pages > 0) outcome = `${pages} page${pages === 1 ? '' : 's'} lue${pages === 1 ? '' : 's'}`;
          else if (lines && lines > 0) outcome = `${lines} ligne${lines === 1 ? '' : 's'} renvoyée${lines === 1 ? '' : 's'}`;
        }
      }
      break;
    }
    case 'run_code': {
      const lang = asString(args.language) || asString(args.lang) || 'code';
      target = `Exécution de ${lang}`;
      location = 'sandbox isolé';
      if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>;
        const stdout = asString(r.stdout);
        const files = asList(r.files);
        const plots = asList(r.plots);
        const parts: string[] = [];
        if (stdout) parts.push('sortie produite');
        if (files.length) parts.push(`${files.length} fichier${files.length === 1 ? '' : 's'}`);
        if (plots.length) parts.push(`${plots.length} graphique${plots.length === 1 ? '' : 's'}`);
        outcome = parts.length ? parts.join(', ') : 'Calcul terminé';
      }
      break;
    }
    case 'generate_document': {
      const name = formatFilePath(asString(args.name) || asString(args.path) || toolCall.filePath || '');
      target = name ? `Création de ${name}` : 'Création d’un document';
      if (toolCall.filePath) location = `dans ${dirname(toolCall.filePath)}`;
      if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>;
        if (r.cancelled) outcome = 'Création annulée';
        else if (toolCall.status === 'success') outcome = 'Document enregistré';
      }
      break;
    }
    default: {
      target = toolCall.humanSummary || undefined;
  }
  }

  if (target) rows.push({ label: 'Action', value: target });
  if (location) rows.push({ label: 'Emplacement', value: location });
  if (outcome) rows.push({ label: 'Résultat', value: outcome });

  const dur = durationLabel(toolCall);
  if (dur) rows.push({ label: 'Durée', value: dur });

  rows.push({ label: 'Statut', value: statusLabel(toolCall.status) });

  return { target, location, outcome, rows };
}

export function statusLabel(status: ChatToolCall['status']): string {
  switch (status) {
    case 'running':
      return 'En cours…';
    case 'awaiting_confirmation':
      return 'En attente de confirmation';
    case 'success':
      return 'Terminé';
    case 'error':
      return 'Échec';
    case 'pending':
    default:
      return 'En attente';
  }
}

export function durationLabel(toolCall: ChatToolCall): string {
  const { startedAt, endedAt } = toolCall;
  if (!startedAt) return '';
  const end = endedAt ?? Date.now();
  const ms = Math.max(0, end - startedAt);
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}
