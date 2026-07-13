import { computed, ref, type ComputedRef, type Ref } from 'vue';
import { Notify } from 'quasar';
import type { PersonasOpinionCard } from '#types';
import {
  askPersonasOpinion,
  buildSidecarSecurityContext,
  discussWithPersonas,
  estimatePersonasCost,
  fetchPersonasDiscussions,
  fetchPersonasDiscussion,
  fetchPersonasMeeting,
  fetchPersonasMeetings,
  fetchPersonasSets,
  savePersonasSet,
  deletePersonasSet,
  startPersonasMeeting,
  type PersonaInfo,
  type PersonaSet,
  type PersonasCostEstimate,
  type PersonasEstimateMode,
  type PersonasMeetingTranscriptTurn,
} from '@services/aiSidecar';
import { buildActiveProviderSet, useAppSettings } from '@composables/useAppSettings';
import { useLlmSessionContext } from '@composables/useLlmSessionContext';
import { ensureProviderSetChatReady } from '@utils/providerSetNotify';
import { providerSetToSidecar } from '@utils/providerSets';
import { t } from '@utils/i18nT';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';

const MEETINGS_STORAGE_KEY = 'workproba.personas.meetings';
const DISCUSSIONS_STORAGE_KEY = 'workproba.personas.discussions';
const CUSTOM_SETS_STORAGE_KEY = 'workproba.personas.customSets';
const ACTIVE_SET_STORAGE_KEY = 'workproba.personas.activeSetId';
const BUILTIN_SET_ID = 'default';
const MAX_STORED_MEETINGS = 50;
const MAX_STORED_DISCUSSIONS = 50;

export interface StoredMeeting {
  meeting_id: string;
  topic: string;
  persona_ids: string[];
  rounds?: number;
  created_at: string;
  transcript: string;
}

export interface StoredDiscussion {
  discussion_id: string;
  persona_ids: string[];
  messages: Array<{
    role: 'user' | 'persona';
    content: string;
    persona_id?: string;
    persona_name?: string;
    role_label?: string;
    avatar_color?: string;
    avatar_icon?: string;
  }>;
  updated_at: string;
}

export interface MeetingTurn {
  round: number;
  personaId: string;
  personaName: string;
  personaRole: string;
  avatarColor: string;
  avatarIcon?: string;
  content: string;
  isFacilitator?: boolean;
}

export interface MeetingState {
  topic: string;
  personaIds: string[];
  rounds: number;
  turns: MeetingTurn[];
  summary: string;
  summaryPersonaName?: string;
  meetingId?: string;
  streaming: boolean;
  error: string | null;
}

export interface DiscussionMessage {
  id: string;
  role: 'user' | 'persona';
  content: string;
  personaId?: string;
  personaName?: string;
  personaRole?: string;
  avatarColor?: string;
  avatarIcon?: string;
  streaming?: boolean;
}

const sets = ref<PersonaSet[]>([]);
const activeSetId = ref<string | null>(readActiveSetId());
const loading = ref(false);
const loadError = ref<string | null>(null);
const historyVersion = ref(0);

const activeSet = computed(() => {
  if (!sets.value.length) return null;
  const found = sets.value.find((s) => s.id === activeSetId.value);
  return found ?? sets.value[0] ?? null;
});

const personas = computed(() => activeSet.value?.personas ?? []);

const builtinPersonas = computed(() => {
  const builtin = sets.value.find((s) => s.id === BUILTIN_SET_ID);
  if (builtin) return builtin.personas;
  const customIds = new Set(readCustomSets().map((s) => s.id));
  const nonCustom = sets.value.find((s) => !customIds.has(s.id));
  return nonCustom?.personas ?? [];
});

export interface UsePersonasReturn {
  sets: Ref<PersonaSet[]>;
  activeSet: ComputedRef<PersonaSet | null>;
  personas: ComputedRef<PersonaInfo[]>;
  builtinPersonas: ComputedRef<PersonaInfo[]>;
  selectablePersonas: ComputedRef<PersonaInfo[]>;
  loading: Ref<boolean>;
  loadError: Ref<string | null>;
  historyVersion: Ref<number>;
  refresh: (pluginDataDir: string) => Promise<void>;
  setActiveSet: (setId: string) => void;
  askOpinion: (
    pluginDataDir: string,
    personaIds: string[],
    question: string,
    context?: string,
    workspaceDataDir?: string | null,
    includeMemory?: boolean,
  ) => Promise<PersonasOpinionCard>;
  startMeeting: (
    pluginDataDir: string,
    personaIds: string[],
    topic: string,
    rounds?: number,
    onUpdate?: (state: MeetingState) => void,
    workspaceDataDir?: string | null,
    includeMemory?: boolean,
    meetingId?: string | null,
    abortSignal?: AbortSignal,
  ) => Promise<MeetingState>;
  discuss: (
    pluginDataDir: string,
    personaIds: string[],
    message: string,
    discussionId: string | null,
    history: DiscussionMessage[],
    onUpdate?: (messages: DiscussionMessage[]) => void,
    workspaceDataDir?: string | null,
    includeMemory?: boolean,
  ) => Promise<{ discussionId: string | null; messages: DiscussionMessage[] }>;
  estimateCost: (
    pluginDataDir: string,
    personaIds: string[],
    mode: PersonasEstimateMode,
    rounds?: number,
  ) => Promise<PersonasCostEstimate | null>;
  listMeetings: () => StoredMeeting[];
  getMeeting: (meetingId: string) => StoredMeeting | null;
  saveMeeting: (meeting: StoredMeeting) => void;
  listDiscussions: () => StoredDiscussion[];
  getDiscussion: (discussionId: string) => StoredDiscussion | null;
  saveDiscussion: (discussion: StoredDiscussion) => void;
  syncHistory: (pluginDataDir: string) => Promise<void>;
  listCustomSets: () => PersonaSet[];
  saveCustomSet: (pluginDataDir: string, set: PersonaSet) => Promise<void>;
  deleteCustomSet: (pluginDataDir: string, setId: string) => Promise<void>;
  findPersona: (personaId: string) => PersonaInfo | undefined;
}

function createOpinionId(): string {
  return `opinion_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function createMessageId(): string {
  return `pmsg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function createMeetingId(): string {
  return `mtg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function readStorage<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function writeStorage<T>(key: string, items: T[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch {
    /* quota ou mode privé */
  }
}

function readActiveSetId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_SET_STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistActiveSetId(setId: string): void {
  try {
    localStorage.setItem(ACTIVE_SET_STORAGE_KEY, setId);
  } catch {
    /* quota ou mode privé */
  }
}

function showPersonasWarnings(data: Record<string, unknown>): void {
  const raw = data.warnings;
  const warnings = Array.isArray(raw) ? raw.map((w) => String(w)) : [];
  if (warnings.length === 0) return;
  for (const warning of warnings.slice(0, 5)) {
    const message = warning.startsWith('personas.')
      ? t(warning)
      : t('personas.warning.generic', { message: warning });
    Notify.create({ message, color: 'warning', timeout: 5000 });
  }
}

function normalizeApiTranscript(
  transcript: string | PersonasMeetingTranscriptTurn[] | undefined,
  summary?: { persona_name?: string; content?: string } | null,
): string {
  if (typeof transcript === 'string') return transcript;
  if (!Array.isArray(transcript)) return '';
  const lines = transcript.map((turn) => {
    const round = turn.round ?? 1;
    const label = turn.persona_name ?? turn.persona_id ?? '';
    const content = turn.content ?? '';
    return t('personas.export.transcriptTurn', { round, label, content });
  });
  if (summary?.content) {
    const summaryLabel = summary.persona_name
      ? t('personas.export.summaryByPersona', { name: summary.persona_name })
      : t('personas.export.summary');
    lines.push(`\n--- ${summaryLabel} ---\n${summary.content}`);
  }
  return lines.join('\n\n');
}

function buildMeetingTranscript(state: MeetingState): string {
  const lines: string[] = [];
  for (const turn of state.turns) {
    const label = turn.isFacilitator
      ? t('personas.meeting.facilitator')
      : turn.personaName;
    lines.push(
      t('personas.export.transcriptTurn', { round: turn.round, label, content: turn.content }),
    );
  }
  if (state.summary) {
    const summaryLabel = state.summaryPersonaName
      ? t('personas.export.summaryByPersona', { name: state.summaryPersonaName })
      : t('personas.export.summary');
    lines.push(`\n--- ${summaryLabel} ---\n${state.summary}`);
  }
  return lines.join('\n\n');
}

export function formatMeetingMarkdown(state: MeetingState): string {
  const lines: string[] = [t('personas.export.meetingTitle', { topic: state.topic }), ''];
  for (const turn of state.turns) {
    const label = turn.isFacilitator
      ? t('personas.meeting.facilitator')
      : turn.personaName;
    lines.push(
      t('personas.export.meetingRound', { round: turn.round, label }),
      '',
      turn.content,
      '',
    );
  }
  if (state.summary) {
    const summaryHeading = state.summaryPersonaName
      ? t('personas.export.summaryByPersona', { name: state.summaryPersonaName })
      : t('personas.export.summary');
    lines.push(summaryHeading, '', state.summary);
  }
  return lines.join('\n');
}

export function formatDiscussionMarkdown(
  personaNames: string[],
  messages: DiscussionMessage[],
): string {
  const title = personaNames.length
    ? t('personas.export.discussionTitle', { names: personaNames.join(', ') })
    : t('personas.export.discussionTitleFallback');
  const lines: string[] = [`# ${title}`, ''];
  for (const msg of messages) {
    const label =
      msg.role === 'user' ? t('personas.export.you') : (msg.personaName ?? t('personas.export.persona'));
    lines.push(`**${label}**`, '', msg.content, '');
  }
  return lines.join('\n');
}

export function formatOpinionMarkdown(card: PersonasOpinionCard): string {
  const lines: string[] = [t('personas.export.opinionTitle', { topic: card.question }), ''];
  for (const opinion of card.opinions) {
    lines.push(`## ${opinion.personaName}`, '', opinion.content, '');
  }
  return lines.join('\n');
}

export function estimateSessionCalls(
  meetings: StoredMeeting[],
  discussions: StoredDiscussion[],
): number {
  let total = 0;
  for (const meeting of meetings) {
    const personaCount = meeting.persona_ids.length || 1;
    if (meeting.rounds) {
      total += meeting.rounds * personaCount;
      continue;
    }
    const rounds = (meeting.transcript.match(/\[(?:Tour|Round) \d+\]/g) ?? []).length;
    total += rounds > 0 ? rounds : personaCount * 3;
  }
  for (const discussion of discussions) {
    total += discussion.messages.filter((m) => m.role === 'persona').length;
  }
  return total;
}

export function meetingStateToStored(state: MeetingState, meetingId?: string): StoredMeeting {
  return {
    meeting_id: meetingId ?? state.meetingId ?? createMeetingId(),
    topic: state.topic,
    persona_ids: state.personaIds,
    rounds: state.rounds,
    created_at: new Date().toISOString(),
    transcript: buildMeetingTranscript(state),
  };
}

export function discussionMessagesToStored(
  discussionId: string,
  personaIds: string[],
  messages: DiscussionMessage[],
): StoredDiscussion {
  return {
    discussion_id: discussionId,
    persona_ids: personaIds,
    messages: messages.map((m) => ({
      role: m.role,
      content: m.content,
      persona_id: m.personaId,
      persona_name: m.personaName,
      role_label: m.personaRole,
      avatar_color: m.avatarColor,
      avatar_icon: m.avatarIcon,
    })),
    updated_at: new Date().toISOString(),
  };
}

/** Convertit le résultat outil `ask_personas` en carte d'avis inline. */
export function toolResultToOpinionCard(
  question: string,
  result: unknown,
): PersonasOpinionCard | null {
  if (!result || typeof result !== 'object') return null;
  const payload = result as Record<string, unknown>;
  const rawOpinions = payload.opinions;
  if (!Array.isArray(rawOpinions) || rawOpinions.length === 0) return null;

  return {
    id: createOpinionId(),
    question,
    opinions: rawOpinions.map((item) => {
      const opinion = item as Record<string, unknown>;
      const personaId = String(opinion.persona_id ?? '');
      const memoryCited = opinion.memory_citations === true;
      return {
        personaId,
        personaName: String(opinion.persona_name ?? personaId),
        personaRole: String(opinion.role ?? ''),
        avatarColor: String(opinion.avatar_color ?? 'var(--wp-gold)'),
        avatarIcon: String(opinion.avatar_icon ?? ''),
        content: String(opinion.content ?? ''),
        memoryCited,
        streaming: false,
      };
    }),
    streaming: false,
  };
}

function findPersona(personaId: string): PersonaInfo | undefined {
  const inActive = personas.value.find((p) => p.id === personaId);
  if (inActive) return inActive;
  for (const set of sets.value) {
    const found = set.personas.find((p) => p.id === personaId);
    if (found) return found;
  }
  return undefined;
}

function readCustomSets(): PersonaSet[] {
  return readStorage<PersonaSet>(CUSTOM_SETS_STORAGE_KEY);
}

function mergeSetsWithCustom(apiSets: PersonaSet[]): PersonaSet[] {
  const custom = readCustomSets();
  if (!custom.length) return apiSets;
  const apiIds = new Set(apiSets.map((s) => s.id));
  const merged = [...apiSets, ...custom.filter((s) => !apiIds.has(s.id))];
  return merged;
}

async function syncPersonasHistory(pluginDataDir: string): Promise<void> {
  const localMeetings = readStorage<StoredMeeting>(MEETINGS_STORAGE_KEY);
  const localDiscussions = readStorage<StoredDiscussion>(DISCUSSIONS_STORAGE_KEY);
  const meetingMap = new Map(localMeetings.map((m) => [m.meeting_id, { ...m }]));

  try {
    const backMeetings = await fetchPersonasMeetings(pluginDataDir);
    for (const summary of backMeetings) {
      const existing = meetingMap.get(summary.meeting_id);
      if (!existing) {
        const detail = await fetchPersonasMeeting(pluginDataDir, summary.meeting_id);
        meetingMap.set(summary.meeting_id, {
          meeting_id: summary.meeting_id,
          topic: summary.topic,
          persona_ids: summary.persona_ids,
          rounds: summary.rounds,
          created_at: summary.created_at,
          transcript: normalizeApiTranscript(detail?.transcript, detail?.summary),
        });
      } else {
        if (!existing.transcript) {
          const detail = await fetchPersonasMeeting(pluginDataDir, summary.meeting_id);
          if (detail?.transcript) {
            existing.transcript = normalizeApiTranscript(detail.transcript, detail.summary);
          }
        }
        if (!existing.rounds && summary.rounds) existing.rounds = summary.rounds;
      }
    }
    const mergedMeetings = [...meetingMap.values()].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    writeStorage(MEETINGS_STORAGE_KEY, mergedMeetings.slice(0, MAX_STORED_MEETINGS));

    const discussionMap = new Map(
      localDiscussions.map((d) => [d.discussion_id, { ...d }]),
    );
    const backDiscussions = await fetchPersonasDiscussions(pluginDataDir);
    for (const summary of backDiscussions) {
      const existing = discussionMap.get(summary.discussion_id);
      if (!existing) {
        const detail = await fetchPersonasDiscussion(pluginDataDir, summary.discussion_id);
        if (detail) {
          discussionMap.set(summary.discussion_id, {
            discussion_id: detail.discussion_id,
            persona_ids: detail.persona_ids,
            messages: detail.messages,
            updated_at: detail.last_message_at || detail.created_at,
          });
        }
      } else if (!existing.messages.length) {
        const detail = await fetchPersonasDiscussion(pluginDataDir, summary.discussion_id);
        if (detail?.messages.length) {
          existing.messages = detail.messages;
          existing.updated_at = detail.last_message_at || existing.updated_at;
        }
      }
    }
    const mergedDiscussions = [...discussionMap.values()].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
    writeStorage(DISCUSSIONS_STORAGE_KEY, mergedDiscussions.slice(0, MAX_STORED_DISCUSSIONS));
    historyVersion.value += 1;
  } catch {
    /* endpoints back absents ou réseau : garde le cache local */
  }
}

export function usePersonas(): UsePersonasReturn {
  const { locale, settingsLocked, permissionsNetwork, settingsMode } = useAppSettings();
  const { isPersonasPluginActive } = usePlugins();
  const { buildContextProviderSet } = useLlmSessionContext();

  const selectablePersonas = computed(() =>
    settingsMode.value === 'advanced' ? personas.value : builtinPersonas.value,
  );

  async function refresh(pluginDataDir: string): Promise<void> {
    if (!isPersonasPluginActive.value) {
      sets.value = [];
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      const list = await fetchPersonasSets(pluginDataDir);
      sets.value = mergeSetsWithCustom(list);
      if (!activeSetId.value && sets.value.length > 0) {
        activeSetId.value = sets.value[0]?.id ?? null;
        if (activeSetId.value) persistActiveSetId(activeSetId.value);
      }
      if (activeSetId.value && !sets.value.some((s) => s.id === activeSetId.value)) {
        const fallback =
          sets.value.find((s) => s.id === BUILTIN_SET_ID)?.id
          ?? sets.value[0]?.id
          ?? null;
        activeSetId.value = fallback;
        if (fallback) persistActiveSetId(fallback);
      }
      await syncPersonasHistory(pluginDataDir);
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'personas_load_failed';
      sets.value = mergeSetsWithCustom([]);
    } finally {
      loading.value = false;
    }
  }

  function setActiveSet(setId: string): void {
    activeSetId.value = setId;
    persistActiveSetId(setId);
  }

  async function askOpinion(
    pluginDataDir: string,
    personaIds: string[],
    question: string,
    context?: string,
    workspaceDataDir?: string | null,
    includeMemory = false,
  ): Promise<PersonasOpinionCard> {
    const card: PersonasOpinionCard = {
      id: createOpinionId(),
      question,
      opinions: personaIds.map((id) => {
        const p = findPersona(id);
        return {
          personaId: id,
          personaName: p?.name ?? id,
          personaRole: p?.role ?? '',
          avatarColor: p?.avatar_color ?? 'var(--wp-gold)',
          avatarIcon: p?.avatar_icon ?? '',
          content: '',
          streaming: true,
        };
      }),
      streaming: true,
    };

    const providerSet = buildContextProviderSet();
    if (!ensureProviderSetChatReady(providerSet)) {
      throw new Error('api_key_missing');
    }
    const providerSetPayload = providerSet ? providerSetToSidecar(providerSet) : null;

    const controller = new AbortController();
    let streamError: Error | null = null;

    try {
      await askPersonasOpinion(
        {
          pluginDataDir,
          personaIds,
          question,
          context,
          workspaceDataDir,
          includeMemory,
          providerSet: providerSetPayload,
          locale: locale.value,
        },
        (type, data) => {
          if (type === 'persona_opinion') {
            const personaId = String(data.persona_id ?? '');
            const block = card.opinions.find((o) => o.personaId === personaId);
            if (block) {
              if (data.content) {
                block.content = String(data.content);
              }
              if (data.memory_citations === true) {
                block.memoryCited = true;
              }
            }
          } else if (type === 'warning') {
            showPersonasWarnings(data);
          } else if (type === 'done') {
            card.streaming = false;
            card.opinions.forEach((o) => {
              o.streaming = false;
            });
          } else if (type === 'error') {
            card.streaming = false;
            streamError = new Error(String(data.message ?? 'ask_failed'));
          }
        },
        controller.signal,
      );
    } catch (err) {
      card.streaming = false;
      throw err;
    }

    if (streamError) throw streamError;

    card.streaming = false;
    if (card.opinions.length > 0 && card.opinions.some((o) => !o.content.trim())) {
      throw new Error('ask_failed');
    }
    return card;
  }

  async function startMeeting(
    pluginDataDir: string,
    personaIds: string[],
    topic: string,
    rounds = 3,
    onUpdate?: (state: MeetingState) => void,
    workspaceDataDir?: string | null,
    includeMemory = false,
    meetingId?: string | null,
    abortSignal?: AbortSignal,
  ): Promise<MeetingState> {
    const state: MeetingState = {
      topic,
      personaIds,
      rounds,
      turns: [],
      summary: '',
      meetingId: meetingId ?? undefined,
      streaming: true,
      error: null,
    };
    onUpdate?.(state);

    const providerSet = buildContextProviderSet();
    if (!ensureProviderSetChatReady(providerSet)) {
      state.error = 'api_key_missing';
      state.streaming = false;
      onUpdate?.(state);
      return state;
    }
    const providerSetPayload = providerSet ? providerSetToSidecar(providerSet) : null;
    const controller = new AbortController();
    const onExternalAbort = (): void => controller.abort();
    abortSignal?.addEventListener('abort', onExternalAbort, { once: true });

    const emitUpdate = (): void => {
      if (abortSignal?.aborted) return;
      onUpdate?.({ ...state });
    };

    try {
      await startPersonasMeeting(
        {
          pluginDataDir,
          personaIds,
          topic,
          rounds: Math.min(rounds, 5),
          meetingId: state.meetingId ?? meetingId ?? undefined,
          workspaceDataDir,
          includeMemory,
          providerSet: providerSetPayload,
          locale: locale.value,
        },
        (type, data) => {
          if (abortSignal?.aborted) return;
          if (type === 'meeting_started') {
            const startedId = String(data.meeting_id ?? '');
            state.meetingId = startedId || state.meetingId || createMeetingId();
            emitUpdate();
          } else if (type === 'meeting_facilitator') {
            const label = String(data.label ?? t('personas.meeting.facilitator'));
            const turn: MeetingTurn = {
              round: Number(data.round ?? 1),
              personaId: '__facilitator__',
              personaName: label,
              personaRole: '',
              avatarColor: 'var(--wp-accent)',
              content: label,
              isFacilitator: true,
            };
            state.turns.push(turn);
            emitUpdate();
          } else if (type === 'meeting_turn') {
            const personaId = String(data.persona_id ?? '');
            const p = findPersona(personaId);
            const turn: MeetingTurn = {
              round: Number(data.round ?? 1),
              personaId,
              personaName: String(data.persona_name ?? p?.name ?? personaId),
              personaRole: String(data.role ?? p?.role ?? ''),
              avatarColor: String(data.avatar_color ?? p?.avatar_color ?? 'var(--wp-gold)'),
              avatarIcon: String(data.avatar_icon ?? p?.avatar_icon ?? ''),
              content: String(data.content ?? ''),
              isFacilitator: false,
            };
            state.turns.push(turn);
            emitUpdate();
          } else if (type === 'meeting_summary') {
            state.summary = String(data.content ?? '');
            state.summaryPersonaName = String(data.persona_name ?? '');
            emitUpdate();
          } else if (type === 'warning') {
            showPersonasWarnings(data);
          } else if (type === 'done') {
            const doneId = String(data.meeting_id ?? '');
            if (doneId) state.meetingId = doneId;
            state.streaming = false;
            emitUpdate();
          } else if (type === 'error') {
            state.error = String(data.code ?? data.message ?? 'meeting_error');
            state.streaming = false;
            emitUpdate();
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (abortSignal?.aborted) {
        state.streaming = false;
        return state;
      }
      state.error = err instanceof Error ? err.message : 'meeting_error';
      state.streaming = false;
      onUpdate?.({ ...state });
    }

    state.streaming = false;
    if (!state.meetingId) {
      state.meetingId = createMeetingId();
    }
    return state;
  }

  async function discuss(
    pluginDataDir: string,
    personaIds: string[],
    message: string,
    discussionId: string | null,
    history: DiscussionMessage[],
    onUpdate?: (messages: DiscussionMessage[]) => void,
    workspaceDataDir?: string | null,
    includeMemory = false,
  ): Promise<{ discussionId: string | null; messages: DiscussionMessage[] }> {
    const providerSet = buildContextProviderSet();
    if (!ensureProviderSetChatReady(providerSet)) {
      throw new Error('api_key_missing');
    }

    const messages = [...history];
    const userMsg: DiscussionMessage = {
      id: createMessageId(),
      role: 'user',
      content: message,
    };
    messages.push(userMsg);
    onUpdate?.([...messages]);

    const providerSetPayload = providerSet ? providerSetToSidecar(providerSet) : null;
    const controller = new AbortController();
    let newDiscussionId = discussionId;
    let streamError: Error | null = null;

    const apiHistory = history
      .filter((m) => m.role === 'user' || m.role === 'persona')
      .map((m) => ({
        role: m.role,
        content: m.content,
        persona_id: m.personaId,
        persona_name: m.personaName,
      }));

    try {
      await discussWithPersonas(
        {
          pluginDataDir,
          personaIds,
          message,
          history: apiHistory,
          discussionId,
          workspaceDataDir,
          includeMemory,
          providerSet: providerSetPayload,
          locale: locale.value,
        },
        (type, data) => {
          if (type === 'discuss_message') {
            const personaId = String(data.persona_id ?? '');
            const p = findPersona(personaId);
            const personaMsg: DiscussionMessage = {
              id: createMessageId(),
              role: 'persona',
              personaId,
              personaName: String(data.persona_name ?? p?.name ?? personaId),
              personaRole: String(data.role_label ?? p?.role ?? ''),
              avatarColor: String(data.avatar_color ?? p?.avatar_color ?? 'var(--wp-gold)'),
              avatarIcon: String(data.avatar_icon ?? p?.avatar_icon ?? ''),
              content: String(data.content ?? ''),
              streaming: false,
            };
            messages.push(personaMsg);
            onUpdate?.([...messages]);
          } else if (type === 'warning') {
            showPersonasWarnings(data);
          } else if (type === 'done') {
            newDiscussionId = String(data.discussion_id ?? newDiscussionId ?? '');
            messages.forEach((m) => {
              if (m.streaming) m.streaming = false;
            });
            onUpdate?.([...messages]);
          } else if (type === 'error') {
            streamError = new Error(String(data.message ?? 'discuss_error'));
          }
        },
        controller.signal,
      );
    } catch (err) {
      onUpdate?.([...history]);
      throw err;
    }

    if (streamError) {
      onUpdate?.([...history]);
      throw streamError;
    }

    messages.forEach((m) => {
      if (m.streaming) m.streaming = false;
    });

    return { discussionId: newDiscussionId, messages };
  }

  async function estimateCost(
    pluginDataDir: string,
    personaIds: string[],
    mode: PersonasEstimateMode,
    rounds?: number,
  ): Promise<PersonasCostEstimate | null> {
    const providerSet = buildContextProviderSet();
    if (!ensureProviderSetChatReady(providerSet)) {
      return null;
    }
    const providerSetPayload = providerSet ? providerSetToSidecar(providerSet) : null;
    return estimatePersonasCost({
      pluginDataDir,
      personaIds,
      mode,
      rounds,
      providerSet: providerSetPayload,
      security: buildSidecarSecurityContext(
        settingsLocked.value,
        permissionsNetwork.value,
        locale.value,
      ),
    });
  }

  function listMeetings(): StoredMeeting[] {
    return readStorage<StoredMeeting>(MEETINGS_STORAGE_KEY).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }

  function getMeeting(meetingId: string): StoredMeeting | null {
    return listMeetings().find((m) => m.meeting_id === meetingId) ?? null;
  }

  function saveMeeting(meeting: StoredMeeting): void {
    const items = listMeetings().filter((m) => m.meeting_id !== meeting.meeting_id);
    items.unshift(meeting);
    writeStorage(MEETINGS_STORAGE_KEY, items.slice(0, MAX_STORED_MEETINGS));
    historyVersion.value += 1;
  }

  function listDiscussions(): StoredDiscussion[] {
    return readStorage<StoredDiscussion>(DISCUSSIONS_STORAGE_KEY).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }

  function getDiscussion(discussionId: string): StoredDiscussion | null {
    return listDiscussions().find((d) => d.discussion_id === discussionId) ?? null;
  }

  function saveDiscussion(discussion: StoredDiscussion): void {
    const items = listDiscussions().filter(
      (d) => d.discussion_id !== discussion.discussion_id,
    );
    items.unshift(discussion);
    writeStorage(DISCUSSIONS_STORAGE_KEY, items.slice(0, MAX_STORED_DISCUSSIONS));
    historyVersion.value += 1;
  }

  function listCustomSets(): PersonaSet[] {
    return readCustomSets();
  }

  async function saveCustomSet(pluginDataDir: string, set: PersonaSet): Promise<void> {
    try {
      const saved = await savePersonasSet(pluginDataDir, set);
      const without = sets.value.filter((s) => s.id !== saved.id);
      sets.value = [...without, saved];
      const items = readCustomSets().filter((s) => s.id !== saved.id);
      items.unshift(saved);
      writeStorage(CUSTOM_SETS_STORAGE_KEY, items);
    } catch {
      const items = readCustomSets().filter((s) => s.id !== set.id);
      items.unshift(set);
      writeStorage(CUSTOM_SETS_STORAGE_KEY, items);
      const customIds = new Set(items.map((s) => s.id));
      const apiSets = sets.value.filter((s) => !customIds.has(s.id));
      sets.value = [...apiSets, ...items];
    }
  }

  async function deleteCustomSet(pluginDataDir: string, setId: string): Promise<void> {
    try {
      await deletePersonasSet(pluginDataDir, setId);
    } catch {
      /* fallback local */
    }
    const items = readCustomSets().filter((s) => s.id !== setId);
    writeStorage(CUSTOM_SETS_STORAGE_KEY, items);
    const customIds = new Set(items.map((s) => s.id));
    const apiSets = sets.value.filter((s) => !customIds.has(s.id));
    sets.value = [...apiSets, ...items];
    if (activeSetId.value === setId) {
      const fallback = sets.value[0]?.id ?? null;
      activeSetId.value = fallback;
      if (fallback) persistActiveSetId(fallback);
    }
  }

  async function syncHistory(pluginDataDir: string): Promise<void> {
    await syncPersonasHistory(pluginDataDir);
  }

  return {
    sets,
    activeSet,
    personas,
    builtinPersonas,
    selectablePersonas,
    loading,
    loadError,
    historyVersion,
    refresh,
    setActiveSet,
    askOpinion,
    startMeeting,
    discuss,
    estimateCost,
    listMeetings,
    getMeeting,
    saveMeeting,
    listDiscussions,
    getDiscussion,
    saveDiscussion,
    syncHistory,
    listCustomSets,
    saveCustomSet,
    deleteCustomSet,
    findPersona,
  };
}

export { PERSONAS_PLUGIN_ID, syncPersonasHistory };
