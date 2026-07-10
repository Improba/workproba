import { computed, ref } from 'vue';

export interface UserProfile {
  name: string;
  organisation: string;
}

const STORAGE_KEY = 'workproba:userProfile';

const DEFAULT_PROFILE: UserProfile = {
  name: 'Sylvain Meylan',
  organisation: 'Improba',
};

function readStored(): UserProfile {
  if (typeof localStorage === 'undefined') return { ...DEFAULT_PROFILE };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PROFILE };
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    return {
      name: typeof parsed.name === 'string' && parsed.name.trim() ? parsed.name : DEFAULT_PROFILE.name,
      organisation:
        typeof parsed.organisation === 'string' && parsed.organisation.trim()
          ? parsed.organisation
          : DEFAULT_PROFILE.organisation,
    };
  } catch {
    return { ...DEFAULT_PROFILE };
  }
}

function persist(profile: UserProfile): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // localStorage indisponible (mode privé) : on garde en mémoire.
  }
}

const profile = ref<UserProfile>(readStored());

const initials = computed(() => {
  const name = profile.value.name.trim();
  if (!name) return '?';
  const first = name.charAt(0);
  return first.toUpperCase();
});

export interface UseUserProfileReturn {
  profile: typeof profile;
  initials: typeof initials;
  save: (next: Partial<UserProfile>) => void;
}

export function useUserProfile(): UseUserProfileReturn {
  function save(next: Partial<UserProfile>): void {
    const merged: UserProfile = {
      name: typeof next.name === 'string' && next.name.trim() ? next.name : profile.value.name,
      organisation:
        typeof next.organisation === 'string' && next.organisation.trim()
          ? next.organisation
          : profile.value.organisation,
    };
    profile.value = merged;
    persist(merged);
  }

  return { profile, initials, save };
}
