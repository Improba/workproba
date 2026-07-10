import { describe, expect, it } from 'vitest';
import { buildAgentTurnPayload, resolveUiMode } from '@services/aiSidecar';

describe('aiSidecar payload', () => {
  it('resolveUiMode renvoie locked si settingsLocked', () => {
    expect(resolveUiMode(true, 'guided')).toBe('locked');
    expect(resolveUiMode(true, 'advanced')).toBe('locked');
  });

  it('resolveUiMode reprend settingsMode sinon', () => {
    expect(resolveUiMode(false, 'guided')).toBe('guided');
    expect(resolveUiMode(false, 'advanced')).toBe('advanced');
  });

  it('buildAgentTurnPayload inclut ui_mode', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      'guided',
    );
    expect(payload.ui_mode).toBe('guided');
  });
});
