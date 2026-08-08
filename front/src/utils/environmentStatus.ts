export type EnvironmentChipState = 'connected' | 'idle' | 'working' | 'error';

export function resolveEnvironmentChipState(input: {
  sidecarState: EnvironmentChipState;
  hasEffectiveEngine: boolean;
  cloudConnected: boolean;
}): EnvironmentChipState {
  if (input.sidecarState === 'error') return 'error';
  if (!input.hasEffectiveEngine) return 'error';
  if (input.sidecarState === 'working') return 'working';
  if (input.cloudConnected || input.sidecarState === 'connected') return 'connected';
  return 'idle';
}

type TranslateFn = (key: string, params?: Record<string, unknown>) => string;

export function resolveEnvironmentStatusLabel(input: {
  loading: boolean;
  sidecarState: EnvironmentChipState;
  hasEffectiveEngine: boolean;
  cloudConnected: boolean;
  t: TranslateFn;
}): string {
  if (input.loading) return input.t('common.loading');
  if (input.sidecarState === 'error') return input.t('shell.titlebarSidecarError');
  if (input.sidecarState === 'working') return input.t('shell.titlebarSidecarWorking');
  if (!input.hasEffectiveEngine) return input.t('environment.engineMissing');
  if (input.cloudConnected) return input.t('environment.cloudConnected');
  return input.t('environment.localEnvironment');
}
