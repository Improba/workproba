<template>
  <div class="personas-meeting" role="main" :aria-label="t('personas.meeting.title')">
    <header class="personas-meeting__header">
      <button type="button" class="personas-meeting__back" @click="emit('close')">
        <Lucide name="arrow-left" size="16" color="text" />
        {{ t('personas.meeting.back') }}
      </button>
      <h1 class="personas-meeting__title">{{ t('personas.meeting.title') }}</h1>
      <PersonasConfidentialityHint class="personas-meeting__privacy" />
    </header>

    <!-- Configuration -->
    <section v-if="phase === 'config'" class="personas-meeting__config">
      <PersonasHistoryPanel
        ref="historyRef"
        mode="meeting"
        :plugin-data-dir="pluginDataDir"
        @relaunch-meeting="onRelaunchFromHistory"
      />
      <PersonasPicker
        :key="pickerKey"
        :open="true"
        :personas="personas"
        :loading="loading"
        :title="t('personas.meeting.configTitle')"
        :subtitle="t('personas.meeting.configSubtitle')"
        :confirm-label="t('personas.meeting.start')"
        :show-rounds="true"
        :topic-label="t('personas.meeting.topicLabel')"
        :topic-placeholder="t('personas.meeting.topicPlaceholder')"
        :busy="starting || Boolean(meetingState?.streaming)"
        :estimate-mode="'meeting'"
        :plugin-data-dir="pluginDataDir"
        :initial-persona-ids="relaunchConfig?.personaIds"
        :initial-topic="relaunchConfig?.topic"
        :initial-rounds="relaunchConfig?.rounds"
        @update:open="(v) => { if (!v) emit('close'); }"
        @confirm="onStart"
      />
    </section>

    <!-- Tour de table -->
    <section v-else class="personas-meeting__room">
      <div
        v-if="meetingState?.error"
        class="personas-meeting__error"
        role="alert"
      >
        {{ meetingErrorMessage }}
      </div>

      <div class="personas-meeting__round-table">
        <div
          v-for="pid in meetingPersonaIds"
          :key="pid"
          class="personas-meeting__seat"
        >
          <PersonaAvatar
            :name="personaName(pid)"
            :color="personaColor(pid)"
            :icon="personaIcon(pid)"
          />
          <span class="personas-meeting__seat-name">{{ personaName(pid) }}</span>
        </div>
      </div>

      <p class="personas-meeting__topic">
        <span class="personas-meeting__topic-label">{{ t('personas.meeting.topicLabel') }}</span>
        {{ meetingState?.topic }}
      </p>

      <div class="personas-meeting__scroll">
        <div class="personas-meeting__turns" role="log" aria-live="polite">
        <div
          v-for="(turn, index) in meetingState?.turns ?? []"
          :key="`${turn.round}-${turn.personaId}-${index}`"
          class="personas-meeting__turn"
          :class="{
            'personas-meeting__turn--facilitator': turn.isFacilitator,
          }"
        >
          <header class="personas-meeting__turn-head">
            <PersonaAvatar
              v-if="!turn.isFacilitator"
              :name="turn.personaName"
              :color="turn.avatarColor"
              :icon="turn.avatarIcon"
            />
            <Lucide v-else name="sparkles" size="16" color="accent" />
            <div class="personas-meeting__turn-meta">
              <span class="personas-meeting__turn-name">
                {{ turn.isFacilitator ? t('personas.meeting.facilitator') : `${turn.personaName} :` }}
              </span>
              <span class="personas-meeting__turn-round">
                {{ t('personas.meeting.round', { n: turn.round }) }}
              </span>
            </div>
          </header>
          <p class="personas-meeting__turn-content">{{ turn.content }}</p>
        </div>

        <p v-if="meetingState?.streaming" class="personas-meeting__streaming">
          {{ t('personas.meeting.inProgress') }}
        </p>
        </div>

        <section
          v-if="meetingState?.summary"
          class="personas-meeting__summary"
          role="region"
          :aria-label="t('personas.meeting.summaryTitle')"
        >
          <h2 class="personas-meeting__summary-title">
            <Lucide name="list-checks" size="16" color="wp-gold" />
            {{ summaryTitle }}
          </h2>
          <p class="personas-meeting__summary-body">{{ meetingState.summary }}</p>
        </section>
      </div>

      <footer v-if="!meetingState?.streaming && !meetingState?.error" class="personas-meeting__actions">
        <button
          v-if="projetPluginActive"
          type="button"
          class="personas-meeting__action"
          @click="publishOpen = true"
        >
          {{ t('personas.publishToProject') }}
        </button>
        <button type="button" class="personas-meeting__action" @click="emit('toDiscussion')">
          {{ t('personas.meeting.toDiscussion') }}
        </button>
        <button type="button" class="personas-meeting__action personas-meeting__action--primary" @click="emit('close')">
          {{ t('personas.meeting.done') }}
        </button>
      </footer>

      <PublishToProjectDialog
        v-model:open="publishOpen"
        :content="publishMarkdown"
        :default-name="publishDefaultName"
        :workspace-data-dir="workspaceDataDir"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import PersonasPicker from '@components/personas/PersonasPicker.vue';
import PersonasHistoryPanel from '@components/personas/PersonasHistoryPanel.vue';
import PersonasConfidentialityHint from '@components/personas/PersonasConfidentialityHint.vue';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { formatMeetingMarkdown, usePersonas, type MeetingState } from '@composables/usePersonas';
import type { PersonaInfo } from '@services/aiSidecar';

const props = defineProps<{
  personas: PersonaInfo[];
  loading?: boolean;
  meetingState: MeetingState | null;
  initialPersonaIds?: string[];
  relaunchConfig?: { personaIds: string[]; topic: string; rounds: number } | null;
  pluginDataDir?: string | null;
  workspaceDataDir?: string | null;
  projetPluginActive?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  start: [payload: { personaIds: string[]; topic: string; rounds: number; includeMemory: boolean }];
  toDiscussion: [];
  relaunch: [config: { personaIds: string[]; topic: string; rounds: number }];
}>();

const { t, locale } = useI18n();
const { findPersona } = usePersonas();

const phase = ref<'config' | 'running'>(props.meetingState ? 'running' : 'config');
const starting = ref(false);
const publishOpen = ref(false);
const historyRef = ref<InstanceType<typeof PersonasHistoryPanel> | null>(null);
const relaunchConfig = ref(props.relaunchConfig ?? null);
const pickerKey = computed(
  () => `picker-${relaunchConfig.value?.topic ?? ''}-${(relaunchConfig.value?.personaIds ?? []).join(',')}`,
);
const meetingPersonaIds = computed(
  () => props.meetingState?.personaIds ?? props.initialPersonaIds ?? [],
);

watch(
  () => props.meetingState,
  (state) => {
    phase.value = state ? 'running' : 'config';
    if (!state?.streaming) starting.value = false;
  },
);

watch(
  () => props.relaunchConfig,
  (config) => {
    if (config) {
      relaunchConfig.value = config;
      phase.value = 'config';
    }
  },
);

const summaryTitle = computed(() => {
  const name = props.meetingState?.summaryPersonaName;
  if (name) return t('personas.meeting.summaryByPersona', { name });
  return t('personas.meeting.summaryTitle');
});

const meetingErrorMessage = computed(() => {
  const code = props.meetingState?.error;
  if (!code) return '';
  if (code === 'api_key_missing') return t('errors.apiKeyMissing');
  if (code === 'unavailable') return t('personas.errors.unavailable');
  return t('personas.errors.meetingFailed');
});

function personaName(id: string): string {
  return findPersona(id)?.name ?? id;
}

function personaColor(id: string): string {
  return findPersona(id)?.avatar_color ?? 'var(--wp-gold)';
}

function personaIcon(id: string): string | undefined {
  return findPersona(id)?.avatar_icon;
}

function onStart(payload: {
  personaIds: string[];
  topic: string;
  rounds: number;
  includeMemory: boolean;
}): void {
  if (starting.value || props.meetingState?.streaming) return;
  starting.value = true;
  relaunchConfig.value = null;
  emit('start', payload);
}

const publishMarkdown = computed(() =>
  props.meetingState ? formatMeetingMarkdown(props.meetingState) : '',
);

const publishDefaultName = computed(() => {
  const topic = props.meetingState?.topic ?? t('personas.meeting.title');
  const date = new Date().toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  return t('personas.publishToProjectNameMeeting', { topic, date });
});

function onRelaunchFromHistory(config: {
  personaIds: string[];
  topic: string;
  rounds: number;
}): void {
  relaunchConfig.value = config;
  phase.value = 'config';
  emit('relaunch', config);
}
</script>

<style scoped lang="scss">
.personas-meeting {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--wp-bg);
  overflow: hidden;
}

.personas-meeting__header {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--wp-space-3);
  padding: var(--wp-space-3) var(--wp-space-4);
  border-bottom: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.personas-meeting__back {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.personas-meeting__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
}

.personas-meeting__privacy {
  margin-left: auto;
  max-width: 28ch;
}

.personas-meeting__config {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: var(--wp-space-4);
  overflow-y: auto;
  gap: var(--wp-space-3);
}

.personas-meeting__room {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: var(--wp-space-4);
}

.personas-meeting__error {
  margin: var(--wp-space-3) var(--wp-space-4) 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-sm);
  background: var(--wp-danger-soft);
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.personas-meeting__round-table {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--wp-space-4);
  padding: var(--wp-space-4);
  margin-bottom: var(--wp-space-4);
  border: 1px dashed color-mix(in srgb, var(--wp-gold) 40%, var(--wp-border));
  border-radius: var(--wp-r-lg, var(--wp-r-md));
  background: var(--wp-gold-soft);
}

.personas-meeting__seat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--wp-space-1);
  min-width: 64px;
}

.personas-meeting__seat-name {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
  text-align: center;
}

.personas-meeting__topic {
  margin: 0 0 var(--wp-space-4);
  font-size: var(--wp-fs-base);
  color: var(--wp-text);
}

.personas-meeting__topic-label {
  display: block;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--wp-space-1);
}

.personas-meeting__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.personas-meeting__turns {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.personas-meeting__turn {
  padding: var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-left: 3px solid var(--wp-gold);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);

  &--facilitator {
    border-left-color: var(--wp-accent);
    background: var(--wp-accent-soft);
  }
}

.personas-meeting__turn-head {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
}

.personas-meeting__turn-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.personas-meeting__turn-name {
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-meeting__turn-round {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.personas-meeting__turn-content {
  margin: 0;
  font-family: var(--wp-font-chat, var(--wp-font-ui));
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  white-space: pre-wrap;
}

.personas-meeting__streaming {
  text-align: center;
  color: var(--wp-gold);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
}

.personas-meeting__summary {
  margin-top: var(--wp-space-4);
  padding: var(--wp-space-4);
  border: 1px solid color-mix(in srgb, var(--wp-gold) 40%, var(--wp-border));
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.personas-meeting__summary-title {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin: 0 0 var(--wp-space-2);
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  font-weight: 700;
}

.personas-meeting__summary-body {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  white-space: pre-wrap;
}

.personas-meeting__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-4);
  padding-top: var(--wp-space-4);
  border-top: 1px solid var(--wp-border);
}

.personas-meeting__action {
  padding: var(--wp-space-2) var(--wp-space-4);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);

  &:hover {
    background: var(--wp-surface-2);
  }

  &--primary {
    background: var(--wp-gold);
    border-color: var(--wp-gold);
    color: var(--wp-canard);
    font-weight: 600;
  }
}
</style>
