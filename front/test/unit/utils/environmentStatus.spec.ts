import { describe, expect, it } from 'vitest';
import { resolveEnvironmentChipState, resolveEnvironmentStatusLabel } from '@utils/environmentStatus';

const t = (key: string) => key;

describe('resolveEnvironmentChipState', () => {
  it('signale une erreur sidecar ou un moteur absent', () => {
    expect(resolveEnvironmentChipState({
      sidecarState: 'error',
      hasEffectiveEngine: true,
      cloudConnected: true,
    })).toBe('error');

    expect(resolveEnvironmentChipState({
      sidecarState: 'connected',
      hasEffectiveEngine: false,
      cloudConnected: true,
    })).toBe('error');
  });

  it('priorise working puis connected', () => {
    expect(resolveEnvironmentChipState({
      sidecarState: 'working',
      hasEffectiveEngine: true,
      cloudConnected: false,
    })).toBe('working');

    expect(resolveEnvironmentChipState({
      sidecarState: 'connected',
      hasEffectiveEngine: true,
      cloudConnected: false,
    })).toBe('connected');

    expect(resolveEnvironmentChipState({
      sidecarState: 'idle',
      hasEffectiveEngine: true,
      cloudConnected: true,
    })).toBe('connected');
  });

  it('retombe sur idle en local sans cloud', () => {
    expect(resolveEnvironmentChipState({
      sidecarState: 'idle',
      hasEffectiveEngine: true,
      cloudConnected: false,
    })).toBe('idle');
  });
});

describe('resolveEnvironmentStatusLabel', () => {
  it('priorise sidecar et moteur avant le statut cloud', () => {
    expect(resolveEnvironmentStatusLabel({
      loading: false,
      sidecarState: 'error',
      hasEffectiveEngine: true,
      cloudConnected: true,
      t,
    })).toBe('shell.titlebarSidecarError');

    expect(resolveEnvironmentStatusLabel({
      loading: false,
      sidecarState: 'connected',
      hasEffectiveEngine: false,
      cloudConnected: true,
      t,
    })).toBe('environment.engineMissing');
  });
});
