import {
  computed,
  readonly,
  ref,
  watch,
  type ComputedRef,
  type Ref,
  type WritableComputedRef,
} from 'vue';
import type { DiscussionMessage } from '@composables/usePersonas';
import { usePluginSlots } from './usePluginSlots';

const open = ref(false);
const activePluginId = ref<string | null>(null);
const initialPersonaIds = ref<string[]>([]);
const initialMode = ref<'avis' | 'discussion' | null>(null);
const initialDraft = ref('');
const initialDiscussionSeed = ref<string | null>(null);
const initialResume = ref<{
  discussionId: string;
  personaIds: string[];
  messages: DiscussionMessage[];
} | null>(null);
const launchToken = ref(0);

let sideChatWatcherStarted = false;

function ensureSideChatWatcher(): void {
  if (sideChatWatcherStarted) return;
  sideChatWatcherStarted = true;

  const { sideChatPluginPanels } = usePluginSlots();

  watch(
    sideChatPluginPanels,
    (panels) => {
      const ids = panels.map((p) => p.pluginId);
      if (ids.length === 0) {
        open.value = false;
        activePluginId.value = null;
        return;
      }
      if (activePluginId.value && !ids.includes(activePluginId.value)) {
        activePluginId.value = ids[0] ?? null;
      }
    },
    { immediate: true },
  );
}

export interface SideChatResumePayload {
  discussionId: string;
  personaIds: string[];
  messages: DiscussionMessage[];
}

export interface UseSideChatReturn {
  sideChatOpen: WritableComputedRef<boolean>;
  activeSideChatPluginId: ComputedRef<string | null>;
  openSideChat: (
    pluginId: string,
    opts?: {
      mode?: 'avis' | 'discussion';
      personaIds?: string[];
      draft?: string;
      discussionSeed?: string;
      resume?: SideChatResumePayload;
    },
  ) => void;
  closeSideChat: () => void;
  consumeInitial: () => {
    personaIds: string[];
    mode: 'avis' | 'discussion' | null;
    draft: string;
    discussionSeed: string | null;
    resume: SideChatResumePayload | null;
  };
  launchToken: Readonly<Ref<number>>;
  hasSideChat: ComputedRef<boolean>;
}

export function resetSideChatStateForTests(): void {
  open.value = false;
  activePluginId.value = null;
  initialPersonaIds.value = [];
  initialMode.value = null;
  initialDraft.value = '';
  initialDiscussionSeed.value = null;
  initialResume.value = null;
  launchToken.value = 0;
}

export function useSideChat(): UseSideChatReturn {
  ensureSideChatWatcher();
  const { sideChatPluginPanels } = usePluginSlots();

  const hasSideChat = computed(() => sideChatPluginPanels.value.length > 0);

  const sideChatOpen = computed({
    get: () => open.value,
    set: (value: boolean) => {
      open.value = value;
    },
  });

  const activeSideChatPluginId = computed(() => activePluginId.value);

  function openSideChat(
    pluginId: string,
    opts?: {
      mode?: 'avis' | 'discussion';
      personaIds?: string[];
      draft?: string;
      discussionSeed?: string;
      resume?: SideChatResumePayload;
    },
  ): void {
    activePluginId.value = pluginId;
    open.value = true;
    let hasPayload = false;
    if (opts?.mode !== undefined) {
      initialMode.value = opts.mode;
      hasPayload = true;
    }
    if (opts?.personaIds !== undefined) {
      initialPersonaIds.value = [...opts.personaIds];
      hasPayload = true;
    }
    if (opts?.draft !== undefined) {
      initialDraft.value = opts.draft;
      hasPayload = true;
    }
    if (opts?.discussionSeed !== undefined) {
      initialDiscussionSeed.value = opts.discussionSeed;
      hasPayload = true;
    }
    if (opts?.resume !== undefined) {
      initialResume.value = {
        discussionId: opts.resume.discussionId,
        personaIds: [...opts.resume.personaIds],
        messages: opts.resume.messages.map((m) => ({ ...m })),
      };
      hasPayload = true;
    }
    if (hasPayload) {
      launchToken.value += 1;
    }
  }

  function closeSideChat(): void {
    open.value = false;
  }

  function consumeInitial(): {
    personaIds: string[];
    mode: 'avis' | 'discussion' | null;
    draft: string;
    discussionSeed: string | null;
    resume: SideChatResumePayload | null;
  } {
    const result = {
      personaIds: [...initialPersonaIds.value],
      mode: initialMode.value,
      draft: initialDraft.value,
      discussionSeed: initialDiscussionSeed.value,
      resume: initialResume.value
        ? {
            discussionId: initialResume.value.discussionId,
            personaIds: [...initialResume.value.personaIds],
            messages: initialResume.value.messages.map((m) => ({ ...m })),
          }
        : null,
    };
    initialPersonaIds.value = [];
    initialMode.value = null;
    initialDraft.value = '';
    initialDiscussionSeed.value = null;
    initialResume.value = null;
    return result;
  }

  return {
    sideChatOpen,
    activeSideChatPluginId,
    openSideChat,
    closeSideChat,
    consumeInitial,
    launchToken: readonly(launchToken),
    hasSideChat,
  };
}
