import type { ErrorReport, ErrorReportLayer } from '#types/errorReport';
import { SidecarHttpError } from '@services/aiSidecar';

export interface ErrorReportLabels {
  header: string;
  incident: string;
  code: string;
  message: string;
  layer: string;
  session: string;
  turn: string;
  work: string;
  app: string;
  time: string;
  detail: string;
  retryable: string;
}

export const DEFAULT_ERROR_REPORT_LABELS: ErrorReportLabels = {
  header: "Workproba - Error report / Rapport d'erreur",
  incident: 'Incident',
  code: 'Code',
  message: 'Message',
  layer: 'Layer / Couche',
  session: 'Session',
  turn: 'Turn / Tour',
  work: 'Work / Travail',
  app: 'App',
  time: 'Time / Heure',
  detail: 'Detail / Détail',
  retryable: 'Retryable / Réessayable',
};

const SECRET_PATTERNS = [
  /\bsk-[a-zA-Z0-9_-]{8,}\b/g,
  /\bBearer\s+[a-zA-Z0-9._-]{8,}\b/gi,
  /\bapi[_-]?key[=:]\s*\S+/gi,
  /\bpassword[=:]\s*\S+/gi,
  /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g,
  /\bAIza[0-9A-Za-z_-]{20,}\b/g,
  /\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b/g,
  /\bX-Api-Key[=:]\s*\S+/gi,
];

const HOME_PATH_PATTERN = /(?:\/home\/|\/Users\/)[^\s,)]+/g;
const WINDOWS_USERS_PATH_PATTERN = /(?:[A-Za-z]:\\Users\\)[^\s,)]+/g;

export function createIncidentId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `inc_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function resolvePlatform(): string | null {
  if (typeof navigator === 'undefined') return null;
  const platform = navigator.platform?.trim();
  if (platform) return platform;
  const ua = navigator.userAgent?.trim();
  return ua ? ua.slice(0, 120) : null;
}

function resolveAppVersion(): string | null {
  const version = process.env.APP_VERSION;
  return typeof version === 'string' && version.trim() ? version.trim() : null;
}

export function sanitizeErrorDetail(raw: string): string {
  let text = raw.trim();
  if (!text) return '';

  for (const pattern of SECRET_PATTERNS) {
    text = text.replace(pattern, '[redacted]');
  }

  text = text.replace(HOME_PATH_PATTERN, (match) => {
    const parts = match.split('/');
    return parts[parts.length - 1] || '[path]';
  });

  text = text.replace(WINDOWS_USERS_PATH_PATTERN, (match) => {
    const parts = match.split('\\');
    return parts[parts.length - 1] || '[path]';
  });

  if (text.length > 500) {
    return `${text.slice(0, 497)}...`;
  }
  return text;
}

export function buildErrorReport(
  partial: Partial<ErrorReport> & Pick<ErrorReport, 'code' | 'message'>,
): ErrorReport {
  return {
    incidentId: partial.incidentId ?? createIncidentId(),
    code: partial.code,
    message: sanitizeErrorDetail(partial.message),
    retryable: partial.retryable ?? false,
    layer: partial.layer ?? 'unknown',
    timestamp: partial.timestamp ?? new Date().toISOString(),
    appVersion: partial.appVersion ?? resolveAppVersion(),
    platform: partial.platform ?? resolvePlatform(),
    sessionId: partial.sessionId ?? null,
    turnId: partial.turnId ?? null,
    workId: partial.workId ?? null,
    detail: partial.detail ? sanitizeErrorDetail(partial.detail) : null,
  };
}

function appendLine(lines: string[], label: string, value: string | null | undefined): void {
  const trimmed = value?.trim();
  if (!trimmed) return;
  lines.push(`${label}: ${trimmed}`);
}

export function formatErrorReportBlob(
  report: ErrorReport,
  labels: ErrorReportLabels = DEFAULT_ERROR_REPORT_LABELS,
): string {
  const lines: string[] = [labels.header, ''];
  appendLine(lines, labels.incident, report.incidentId);
  appendLine(lines, labels.code, report.code);
  appendLine(lines, labels.message, report.message);
  appendLine(lines, labels.layer, report.layer);
  appendLine(lines, labels.session, report.sessionId);
  appendLine(lines, labels.turn, report.turnId);
  appendLine(lines, labels.work, report.workId);

  const appParts = [report.appVersion, report.platform].filter(Boolean);
  if (appParts.length) {
    lines.push(`${labels.app}: ${appParts.join(' · ')}`);
  }

  appendLine(lines, labels.time, report.timestamp);
  appendLine(lines, labels.retryable, report.retryable ? 'yes / oui' : 'no / non');
  appendLine(lines, labels.detail, report.detail);
  return lines.join('\n').trim();
}

export function buildSupportMailto(
  email: string,
  report: ErrorReport,
  subject: string,
  labels?: ErrorReportLabels,
): string {
  const body = formatErrorReportBlob(report, labels);
  const trimmedEmail = email.trim();
  return `mailto:${trimmedEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

export function unknownErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message.trim()) {
    return err.message.trim();
  }
  if (typeof err === 'string' && err.trim()) {
    return err.trim();
  }
  return fallback;
}

export function unknownErrorCode(err: unknown): string {
  if (err && typeof err === 'object' && 'code' in err) {
    const code = (err as { code?: unknown }).code;
    if (typeof code === 'string' && code.trim()) {
      return code.trim();
    }
  }
  if (err instanceof Error && err.name && err.name !== 'Error') {
    return err.name;
  }
  return 'unknown';
}

export function shouldIgnoreGlobalError(err: unknown): boolean {
  if (err instanceof Error) {
    if (err.name === 'AbortError') return true;
    const message = err.message.toLowerCase();
    if (message.includes('aborted')) return true;
  }
  if (err && typeof err === 'object' && 'name' in err) {
    const name = String((err as { name?: unknown }).name ?? '');
    if (name === 'AbortError') return true;
  }
  if (err instanceof SidecarHttpError) {
    return true;
  }
  return false;
}
