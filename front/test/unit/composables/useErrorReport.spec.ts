import { describe, expect, it, afterEach, vi } from 'vitest';
import { useErrorReport } from '@composables/useErrorReport';

describe('useErrorReport', () => {
  const {
    open,
    report,
    openFromUnknown,
    openFromChatError,
    reportError,
    close,
  } = useErrorReport();

  afterEach(() => {
    close();
    report.value = null;
  });

  it('openFromUnknown skips when dialog is already open', () => {
    openFromUnknown(new Error('first error'), 'ui');
    expect(open.value).toBe(true);
    expect(report.value?.message).toBe('first error');

    openFromUnknown(new Error('second error'), 'ui');
    expect(report.value?.message).toBe('first error');
  });

  it('openFromUnknown debounces duplicate code+message within 300ms', () => {
    vi.useFakeTimers();
    openFromUnknown(new Error('debounced error'), 'ui');
    expect(open.value).toBe(true);
    close();

    vi.advanceTimersByTime(310);

    openFromUnknown(new Error('debounced error'), 'ui');
    expect(open.value).toBe(true);
    close();

    openFromUnknown(new Error('debounced error'), 'ui');
    expect(open.value).toBe(false);

    vi.useRealTimers();
  });

  it('openFromChatError sets sidecar layer for sidecar_unreachable', () => {
    openFromChatError({
      code: 'sidecar_unreachable',
      message: 'Sidecar down',
      retryable: true,
    });
    expect(report.value?.layer).toBe('sidecar');
  });

  it('openFromChatError sets chat layer for other codes', () => {
    openFromChatError({
      code: 'agent_error',
      message: 'Agent failed',
      retryable: false,
    });
    expect(report.value?.layer).toBe('chat');
  });

  it('openFromChatError can replace while dialog is open', () => {
    openFromUnknown(new Error('global error'), 'ui');
    expect(report.value?.message).toBe('global error');

    openFromChatError(
      {
        code: 'agent_error',
        message: 'chat error',
        retryable: true,
      },
      { turnId: 'turn_1', sessionId: 'sess_1' },
    );
    expect(report.value?.message).toBe('chat error');
    expect(report.value?.turnId).toBe('turn_1');
    expect(report.value?.sessionId).toBe('sess_1');
  });

  it('reportError defaults layer to unknown', () => {
    reportError({
      code: 'custom_error',
      message: 'Something went wrong',
      serious: true,
    });
    expect(report.value?.layer).toBe('unknown');
  });
});
