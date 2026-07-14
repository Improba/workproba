import type { ChatToolCall } from '#types';
import { t } from './i18nT';

/** Aligné sur `app.agent.confirmation` (SSE tool_call_result / ModelRetry). */
export const APPROVAL_DENIED_MARKER = 'workproba:approval_denied';
export const APPROVAL_TIMEOUT_MARKER = 'workproba:approval_timeout';

export function approvalGateRetryKind(text: string): 'denied' | 'timeout' | null {
  if (text.includes(APPROVAL_DENIED_MARKER)) return 'denied';
  if (text.includes(APPROVAL_TIMEOUT_MARKER)) return 'timeout';
  return null;
}

/**
 * Détecte un refus ou timeout de confirmation (format actuel ou legacy `cancelled`).
 */
export function isWriteApprovalCancelled(
  result: unknown,
  status?: ChatToolCall['status'],
): boolean {
  if (result && typeof result === 'object') {
    const record = result as Record<string, unknown>;
    if (record.cancelled === true) return true;
    const content = record.content;
    if (typeof content === 'string' && approvalGateRetryKind(content) !== null) {
      return true;
    }
  }
  if (typeof result === 'string' && approvalGateRetryKind(result) !== null) {
    return true;
  }
  if (status === 'error' && result == null) return false;
  return approvalGateRetryKind(JSON.stringify(result ?? '')) !== null;
}

/** Refus ou expiration de gate (résultat structuré ou résumé SSE backend). */
export function isApprovalGateCancelledToolCall(
  toolCall: Pick<ChatToolCall, 'result' | 'status' | 'humanSummary'>,
): boolean {
  if (isWriteApprovalCancelled(toolCall.result, toolCall.status)) {
    return true;
  }
  if (toolCall.status !== 'error') return false;
  const summary = toolCall.humanSummary?.trim() ?? '';
  if (!summary) return false;
  return (
    summary === t('toolCalls.actionCancelled') ||
    summary === t('errors.agentConfirmationTimeout')
  );
}
