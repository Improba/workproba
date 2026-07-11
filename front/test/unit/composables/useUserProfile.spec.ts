import { beforeEach, describe, expect, it, vi } from 'vitest';

const storage = new Map<string, string>();

vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => {
    storage.set(key, value);
  },
  removeItem: (key: string) => {
    storage.delete(key);
  },
  clear: () => {
    storage.clear();
  },
});

vi.mock('@composables/useDesktop', () => ({
  isDesktopApp: () => false,
  getAppSettings: vi.fn(),
  saveAppSettings: vi.fn(),
}));

describe('useUserProfile', () => {
  beforeEach(() => {
    storage.clear();
    vi.resetModules();
  });

  it('demande l\'onboarding sans profil enregistré', async () => {
    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { needsOnboarding, profile } = useUserProfile();

    expect(profile.value.name).toBe('');
    expect(needsOnboarding.value).toBe(true);
  });

  it('ignore le profil legacy Sylvain / Improba', async () => {
    storage.set(
      'workproba:userProfile',
      JSON.stringify({ name: 'Sylvain Meylan', organisation: 'Improba' }),
    );

    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { needsOnboarding, profile } = useUserProfile();

    expect(profile.value.name).toBe('');
    expect(needsOnboarding.value).toBe(true);
  });

  it('complete l\'onboarding et persiste le profil', async () => {
    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { completeOnboarding, needsOnboarding, profile, profileOnboardingDone } = useUserProfile();

    await completeOnboarding({ name: 'Sylvie Martin', organisation: 'Acme RH' });

    expect(profile.value).toEqual({ name: 'Sylvie Martin', organisation: 'Acme RH' });
    expect(profileOnboardingDone.value).toBe(true);
    expect(needsOnboarding.value).toBe(false);
    expect(storage.get('workproba:profileOnboardingDone')).toBe('true');
  });
});
