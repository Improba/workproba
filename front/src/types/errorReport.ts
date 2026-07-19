export type ErrorReportLayer = 'chat' | 'sidecar' | 'tauri' | 'ui' | 'unknown';

export interface ErrorReport {
  incidentId: string;
  code: string;
  message: string;
  retryable: boolean;
  layer: ErrorReportLayer;
  timestamp: string;
  appVersion: string | null;
  platform: string | null;
  sessionId?: string | null;
  turnId?: string | null;
  workId?: string | null;
  detail?: string | null;
}
