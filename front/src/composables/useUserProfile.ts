import { computed, ref } from 'vue';

export interface UserProfile {
  name: string;
  organisation: string;
}

const STORAGE_KEY = 'workproba:userProfile';
const PROFILE_ONBOARDING_KEY = 'workproba:profileOnboardingDone';

const LEGACY_DEFAULT_NAME = 'Sylvain Meylan';
const LEGACY_DEFAULT_ORG = 'Improba';
const LEGACY_NAMES = [LEGACY_DEFAULT_NAME, 'Sylvain'];
const LEGACY_ORGS = [LEGACY_DEFAULT_ORG];

const EMPTY_PROFILE: UserProfile = {
  name: '',
  organisation: '',
};

function isLegacyDefault(profile: UserProfile): boolean {
  const name = profile.name.trim();
  const org = profile.organisation.trim();
  if (name === LEGACY_DEFAULT_NAME && org === LEGACY_DEFAULT_ORG) return true;
  if (LEGACY_NAMES.includes(name) && (!org || LEGACY_ORGS.includes(org))) return true;
  if (!name && LEGACY_ORGS.includes(org)) return true;
  return false;
}

function sanitizeProfile(profile: UserProfile): UserProfile {
  if (isLegacyDefault(profile)) return { ...EMPTY_PROFILE };
  let name = profile.name.trim();
  let organisation = profile.organisation.trim();
  if (LEGACY_NAMES.includes(name)) name = '';
  if (LEGACY_ORGS.includes(organisation)) organisation = '';
  return { name, organisation };
}

function readProfileOnboardingDone(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(PROFILE_ONBOARDING_KEY) === 'true';
}

function persistProfileOnboardingDone(done: boolean): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(PROFILE_ONBOARDING_KEY, String(done));
}

function readStored(): UserProfile {
  if (typeof localStorage === 'undefined') return { ...EMPTY_PROFILE };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...EMPTY_PROFILE };
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    const name = typeof parsed.name === 'string' ? parsed.name.trim() : '';
    const organisation = typeof parsed.organisation === 'string' ? parsed.organisation.trim() : '';
    return sanitizeProfile({ name, organisation });
  } catch {
    return { ...EMPTY_PROFILE };
  }
}

function persistLocal(profile: UserProfile): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // localStorage indisponible (mode privé) : on garde en mémoire.
  }
}

async function persistToAppSettings(profile: UserProfile): Promise<void> {
  try {
    const { isDesktopApp } = await import('@composables/useDesktop');
    if (!isDesktopApp()) return;
    const { useAppSettings } = await import('@composables/useAppSettings');
    const { settings, save, load, loaded } = useAppSettings();
    if (!loaded.value) {
      await load();
    }
    await save({
      ...settings.value,
      userName: profile.name || null,
      userOrg: profile.organisation || null,
      profileOnboardingDone: profileOnboardingDone.value,
    });
  } catch {
    // Tauri indisponible : localStorage suffit.
  }
}

async function hydrateFromAppSettings(): Promise<void> {
  try {
    const { isDesktopApp, getAppSettings } = await import('@composables/useDesktop');
    if (!isDesktopApp()) return;
    const settings = await getAppSettings();
    const name = settings.userName?.trim() ?? '';
    const organisation = settings.userOrg?.trim() ?? '';
    const sanitized = sanitizeProfile({ name, organisation });
    if (sanitized.name || sanitized.organisation) {
      profile.value = sanitized;
      persistLocal(profile.value);
    }
    if (settings.profileOnboardingDone) {
      profileOnboardingDone.value = true;
      persistProfileOnboardingDone(true);
    }
  } catch {
    // Lecture settings échouée : on garde le localStorage.
  }
}

const profile = ref<UserProfile>(readStored());
const profileOnboardingDone = ref<boolean>(readProfileOnboardingDone());
const loaded = ref(true);

let desktopBootstrapStarted = false;

async function bootstrapFromDesktop(): Promise<void> {
  try {
    const { isDesktopApp } = await import('@composables/useDesktop');
    if (!isDesktopApp()) return;
    loaded.value = false;
    await hydrateFromAppSettings();
  } catch {
    // Mock partiel en tests ou Tauri indisponible.
  } finally {
    loaded.value = true;
  }
}

function ensureDesktopBootstrap(): void {
  if (desktopBootstrapStarted) return;
  desktopBootstrapStarted = true;
  void bootstrapFromDesktop();
}

const hasIdentity = computed(
  () => Boolean(profile.value.name.trim() || profile.value.organisation.trim()),
);

const initials = computed(() => {
  const name = profile.value.name.trim();
  if (!name) return '?';
  return name.charAt(0).toUpperCase();
});

const needsOnboarding = computed(
  () => loaded.value && !profileOnboardingDone.value && !profile.value.name.trim(),
);

const displayName = computed(() => profile.value.name.trim() || '');

const displayOrganisation = computed(() => profile.value.organisation.trim() || '');

export interface UseUserProfileReturn {
  profile: typeof profile;
  initials: typeof initials;
  loaded: typeof loaded;
  hasIdentity: typeof hasIdentity;
  needsOnboarding: typeof needsOnboarding;
  profileOnboardingDone: typeof profileOnboardingDone;
  displayName: typeof displayName;
  displayOrganisation: typeof displayOrganisation;
  save: (next: Partial<UserProfile>) => void;
  completeOnboarding: (next: Partial<UserProfile>) => Promise<void>;
  clearProfile: () => Promise<void>;
}

export function useUserProfile(): UseUserProfileReturn {
  ensureDesktopBootstrap();

  function save(next: Partial<UserProfile>): void {
    const merged: UserProfile = sanitizeProfile({
      name: typeof next.name === 'string' ? next.name.trim() : profile.value.name,
      organisation:
        typeof next.organisation === 'string'
          ? next.organisation.trim()
          : profile.value.organisation,
    });
    profile.value = merged;
    persistLocal(merged);
    void persistToAppSettings(merged);
  }

  async function completeOnboarding(next: Partial<UserProfile>): Promise<void> {
    const name = typeof next.name === 'string' ? next.name.trim() : profile.value.name.trim();
    if (!name) return;

    const merged: UserProfile = sanitizeProfile({
      name,
      organisation:
        typeof next.organisation === 'string'
          ? next.organisation.trim()
          : profile.value.organisation.trim(),
    });
    profile.value = merged;
    persistLocal(merged);
    profileOnboardingDone.value = true;
    persistProfileOnboardingDone(true);
    await persistToAppSettings(merged);
  }

  async function clearProfile(): Promise<void> {
    profile.value = { ...EMPTY_PROFILE };
    profileOnboardingDone.value = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(PROFILE_ONBOARDING_KEY);
    }
    await persistToAppSettings({ ...EMPTY_PROFILE });
  }

  return {
    profile,
    initials,
    loaded,
    hasIdentity,
    needsOnboarding,
    profileOnboardingDone,
    displayName,
    displayOrganisation,
    save,
    completeOnboarding,
    clearProfile,
  };
}
