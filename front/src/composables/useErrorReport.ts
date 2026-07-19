import { ref } from 'vue';
import type { Ref } from 'vue';
import { Notify } from 'quasar';
import type { ChatError } from '#types';
import type { ErrorReport, ErrorReportLayer } from '#types/errorReport';
import { getAppSettings } from '@composables/useDesktop';
import { t } from '@utils/i18nT';
import {
  buildErrorReport,
  buildSupportMailto,
  createIncidentId,
  formatErrorReportBlob,
  sanitizeErrorDetail,
  shouldIgnoreGlobalError,
  unknownErrorCode,
  unknownErrorMessage,
} from '@utils/errorReport';

const open = ref(false);
const report = ref<ErrorReport | null>(null);
const supportEmail = ref<string | null>(null);
const onRetry: Ref<(() => void) | null> = ref(null);

let lastOpenAt = 0;
let lastOpenKey = '';

function layerFromChatErrorCode(code: string): ErrorReportLayer {
  if (code === 'sidecar_unreachable') return 'sidecar';
  return 'chat';
}

function openMailto(href: string): void {
  if (typeof document === 'undefined') return;
  // open_external_url is http(s)-only; transient anchor avoids hijacking the Tauri webview.
  try {
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } catch {
    if (typeof window !== 'undefined') {
      window.location.href = href;
    }
  }
}

async function ensureSupportEmail(): Promise<void> {
  try {
    const settings = await getAppSettings();
    const email = settings.supportEmail?.trim();
    supportEmail.value = email || null;
  } catch {
    supportEmail.value = null;
  }
}

function openReport(
  partial: ErrorReport | (Partial<ErrorReport> & Pick<ErrorReport, 'code' | 'message'>),
  retry?: () => void,
): void {
  report.value = buildErrorReport(partial);
  onRetry.value = retry ?? null;
  open.value = true;
  void ensureSupportEmail();
}

function openFromChatError(
  err: ChatError,
  correlation?: { turnId?: string | null; workId?: string | null; sessionId?: string | null },
  retry?: () => void,
): void {
  openReport(
    {
      code: err.code,
      message: err.message,
      retryable: err.retryable,
      layer: layerFromChatErrorCode(err.code),
      incidentId: err.incidentId ?? createIncidentId(),
      turnId: err.turnId ?? correlation?.turnId ?? null,
      workId: err.workId ?? correlation?.workId ?? null,
      sessionId: err.sessionId ?? correlation?.sessionId ?? null,
    },
    retry,
  );
}

function openFromUnknown(err: unknown, layer: ErrorReportLayer = 'unknown'): void {
  if (open.value) return;
  if (shouldIgnoreGlobalError(err)) return;
  const code = unknownErrorCode(err);
  const message = unknownErrorMessage(err, t('errors.unexpectedUiError'));
  const key = `${code}\0${message}`;
  const now = Date.now();
  if (key === lastOpenKey && now - lastOpenAt < 300) return;
  lastOpenKey = key;
  lastOpenAt = now;
  openReport({
    code,
    message,
    retryable: false,
    layer,
    detail: err instanceof Error ? sanitizeErrorDetail(err.message) : null,
  });
}

function close(): void {
  open.value = false;
  onRetry.value = null;
}

function runRetry(): void {
  const retry = onRetry.value;
  if (retry) {
    retry();
  }
  close();
}

async function copyReport(): Promise<boolean> {
  if (!report.value) return false;
  const blob = formatErrorReportBlob(report.value);
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(blob);
      return true;
    }
  } catch {
    // fallback below
  }
  return false;
}

async function contactSupport(): Promise<void> {
  if (!report.value) return;
  await ensureSupportEmail();
  const email = supportEmail.value?.trim();
  if (!email) {
    const copied = await copyReport();
    Notify.create({
      message: copied
        ? t('errors.reportContactNoEmail')
        : t('errors.reportCopyFailed'),
      color: 'warning',
      timeout: 4000,
    });
    return;
  }
  const subject = `${t('errors.reportTitle')} - ${report.value.code}`;
  const href = buildSupportMailto(email, report.value, subject);
  openMailto(href);
}

export interface ReportErrorOptions {
  code: string;
  message: string;
  retryable?: boolean;
  layer?: ErrorReportLayer;
  detail?: string | null;
  sessionId?: string | null;
  turnId?: string | null;
  workId?: string | null;
  incidentId?: string | null;
  onRetry?: () => void;
  /** When true, open the modal immediately. When false, show a toast with an action. */
  serious?: boolean;
}

function reportError(options: ReportErrorOptions): void {
  const built = buildErrorReport({
    code: options.code,
    message: options.message,
    retryable: options.retryable ?? false,
    layer: options.layer ?? 'unknown',
    detail: options.detail ?? null,
    sessionId: options.sessionId ?? null,
    turnId: options.turnId ?? null,
    workId: options.workId ?? null,
    incidentId: options.incidentId ?? createIncidentId(),
  });

  if (options.serious !== false) {
    openReport(built, options.onRetry);
    return;
  }

  report.value = built;
  onRetry.value = options.onRetry ?? null;
  void ensureSupportEmail();
  Notify.create({
    message: built.message,
    color: 'negative',
    timeout: 5000,
    actions: [
      {
        label: t('errors.reportOpenAction'),
        color: 'white',
        handler: () => {
          open.value = true;
        },
      },
    ],
  });
}

export function useErrorReport() {
  return {
    open,
    report,
    supportEmail,
    ensureSupportEmail,
    openReport,
    openFromChatError,
    openFromUnknown,
    close,
    runRetry,
    copyReport,
    contactSupport,
    reportError,
  };
}
