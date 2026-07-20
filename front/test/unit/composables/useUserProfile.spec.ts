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
    const { needsOnboarding, profile, hasIdentity } = useUserProfile();

    expect(profile.value.name).toBe('');
    expect(hasIdentity.value).toBe(false);
    expect(needsOnboarding.value).toBe(true);
  });

  it('ignore le profil legacy Sylvain Meylan / Improba', async () => {
    storage.set(
      'workproba:userProfile',
      JSON.stringify({ name: 'Sylvain Meylan', organisation: 'Improba' }),
    );

    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { needsOnboarding, profile, hasIdentity } = useUserProfile();

    expect(profile.value.name).toBe('');
    expect(hasIdentity.value).toBe(false);
    expect(needsOnboarding.value).toBe(true);
  });

  it('ignore le profil legacy Sylvain / Improba', async () => {
    storage.set(
      'workproba:userProfile',
      JSON.stringify({ name: 'Sylvain', organisation: 'Improba' }),
    );

    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { profile, hasIdentity } = useUserProfile();

    expect(profile.value).toEqual({ name: '', organisation: '' });
    expect(hasIdentity.value).toBe(false);
  });

  it('purge une organisation legacy Improba seule', async () => {
    storage.set(
      'workproba:userProfile',
      JSON.stringify({ name: '', organisation: 'Improba' }),
    );

    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { profile } = useUserProfile();

    expect(profile.value.organisation).toBe('');
  });

  it('complete l\'onboarding et persiste le profil', async () => {
    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { completeOnboarding, needsOnboarding, profile, profileOnboardingDone, hasIdentity } = useUserProfile();

    await completeOnboarding({ name: 'Sylvie Martin', organisation: 'Acme RH' });

    expect(profile.value).toEqual({ name: 'Sylvie Martin', organisation: 'Acme RH' });
    expect(profileOnboardingDone.value).toBe(true);
    expect(hasIdentity.value).toBe(true);
    expect(needsOnboarding.value).toBe(false);
    expect(storage.get('workproba:profileOnboardingDone')).toBe('true');
  });

  it('clearProfile remet le profil à vide', async () => {
    storage.set(
      'workproba:userProfile',
      JSON.stringify({ name: 'Alice', organisation: 'Beta' }),
    );
    storage.set('workproba:profileOnboardingDone', 'true');

    const { useUserProfile } = await import('../../../src/composables/useUserProfile');
    const { clearProfile, profile, profileOnboardingDone, hasIdentity } = useUserProfile();

    await clearProfile();

    expect(profile.value).toEqual({ name: '', organisation: '' });
    expect(profileOnboardingDone.value).toBe(false);
    expect(hasIdentity.value).toBe(false);
    expect(storage.get('workproba:userProfile')).toBeUndefined();
    expect(storage.get('workproba:profileOnboardingDone')).toBeUndefined();
  });
});
