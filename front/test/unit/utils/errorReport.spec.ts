import { describe, expect, it } from 'vitest';
import {
  buildErrorReport,
  buildSupportMailto,
  createIncidentId,
  formatErrorReportBlob,
  sanitizeErrorDetail,
  shouldIgnoreGlobalError,
} from '@utils/errorReport';
import { SidecarHttpError } from '@services/aiSidecar';

describe('errorReport utils', () => {
  it('createIncidentId returns a non-empty string', () => {
    const id = createIncidentId();
    expect(id.length).toBeGreaterThan(8);
  });

  it('sanitizeErrorDetail redacts secrets and truncates', () => {
    const raw =
      'Bearer abcdefghijklmnop /home/syl/workdir/secret/file.txt ' + 'x'.repeat(600);
    const sanitized = sanitizeErrorDetail(raw);
    expect(sanitized).toContain('[redacted]');
    expect(sanitized).not.toContain('/home/syl');
    expect(sanitized.length).toBeLessThanOrEqual(500);
  });

  it('sanitizeErrorDetail redacts JWT and GitHub tokens', () => {
    const jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U';
    const token = 'ghp_abcdefghijklmnopqrstuvwxyz1234567890';
    const sanitized = sanitizeErrorDetail(`auth ${jwt} key ${token}`);
    expect(sanitized).not.toContain(jwt);
    expect(sanitized).not.toContain(token);
    expect(sanitized).toContain('[redacted]');
  });

  it('sanitizeErrorDetail redacts Windows user paths to basename', () => {
    const sanitized = sanitizeErrorDetail('file at C:\\Users\\alice\\secret\\config.json');
    expect(sanitized).not.toContain('C:\\Users\\alice');
    expect(sanitized).toContain('config.json');
  });

  it('buildErrorReport sanitizes message in formatErrorReportBlob output', () => {
    const blob = formatErrorReportBlob(
      buildErrorReport({
        code: 'agent_error',
        message: 'Auth failed Bearer abcdefghijklmnop at /home/user/secret/data.txt',
        retryable: false,
        layer: 'chat',
        incidentId: 'inc-sec',
        timestamp: '2026-07-19T10:00:00.000Z',
      }),
    );
    expect(blob).toContain('[redacted]');
    expect(blob).not.toContain('Bearer abcdefghijklmnop');
    expect(blob).not.toContain('/home/user/secret');
    expect(blob).toContain('data.txt');
  });

  it('formatErrorReportBlob omits empty fields', () => {
    const blob = formatErrorReportBlob(
      buildErrorReport({
        code: 'agent_error',
        message: 'Something failed',
        retryable: true,
        layer: 'chat',
        incidentId: 'inc-1',
        timestamp: '2026-07-19T10:00:00.000Z',
        appVersion: '1.0.0',
        platform: 'Linux',
      }),
    );
    expect(blob).toContain('Incident: inc-1');
    expect(blob).toContain('Code: agent_error');
    expect(blob).toContain('Workproba - Error report');
    expect(blob).not.toContain('Session:');
    expect(blob).not.toContain('Work:');
  });

  it('shouldIgnoreGlobalError ignores AbortError', () => {
    expect(shouldIgnoreGlobalError(new DOMException('Aborted', 'AbortError'))).toBe(true);
    expect(shouldIgnoreGlobalError(Object.assign(new Error('fetch aborted'), { name: 'AbortError' }))).toBe(
      true,
    );
    expect(shouldIgnoreGlobalError(new Error('The operation was aborted'))).toBe(true);
    expect(shouldIgnoreGlobalError(new Error('Something else'))).toBe(false);
  });

  it('shouldIgnoreGlobalError ignores SidecarHttpError', () => {
    expect(shouldIgnoreGlobalError(new SidecarHttpError(502, 'sidecar_down', 'Sidecar unavailable'))).toBe(
      true,
    );
    expect(shouldIgnoreGlobalError(new Error('plain failure'))).toBe(false);
  });

  it('buildSupportMailto encodes subject and body', () => {
    const report = buildErrorReport({
      code: 'turn_timeout',
      message: 'Timeout',
      retryable: true,
      layer: 'sidecar',
      incidentId: 'inc-2',
      timestamp: '2026-07-19T10:00:00.000Z',
      appVersion: null,
      platform: null,
    });
    const href = buildSupportMailto('support@example.com', report, 'Workproba error');
    expect(href.startsWith('mailto:support@example.com?')).toBe(true);
    expect(href).toContain(encodeURIComponent('Workproba error'));
    expect(href).toContain(encodeURIComponent('inc-2'));
  });
});
