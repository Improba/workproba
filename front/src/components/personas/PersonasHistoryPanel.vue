<template>
  <aside class="personas-history" :aria-label="t('personas.history.title')">
    <header class="personas-history__head">
      <h2 class="personas-history__title">{{ t('personas.history.title') }}</h2>
      <button
        type="button"
        class="personas-history__toggle"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <Lucide :name="expanded ? 'chevron-up' : 'chevron-down'" size="14" color="text-muted" />
      </button>
    </header>

    <div v-show="expanded" class="personas-history__body">
      <section v-if="mode === 'meeting' || mode === 'all'" class="personas-history__section">
        <h3 class="personas-history__section-title">{{ t('personas.history.meetings') }}</h3>
        <p v-if="meetings.length === 0" class="personas-history__empty">
          {{ t('personas.history.noMeetings') }}
        </p>
        <ul v-else class="personas-history__list" role="list">
          <li v-for="meeting in meetings" :key="meeting.meeting_id" class="personas-history__row">
            <button
              type="button"
              class="personas-history__item"
              :class="{ 'personas-history__item--active': selectedMeetingId === meeting.meeting_id }"
              @click="onSelectMeeting(meeting)"
            >
              <span class="personas-history__item-title">{{ meeting.topic }}</span>
              <span class="personas-history__item-meta">
                {{ formatDate(meeting.created_at) }}
              </span>
            </button>
            <button
              v-if="mode === 'meeting' || mode === 'all'"
              type="button"
              class="personas-history__relaunch"
              :title="t('personas.history.relaunch')"
              @click.stop="onRelaunchMeeting(meeting)"
            >
              {{ t('personas.history.relaunch') }}
            </button>
          </li>
        </ul>
      </section>

      <section v-if="mode === 'discuss' || mode === 'all'" class="personas-history__section">
        <h3 class="personas-history__section-title">{{ t('personas.history.discussions') }}</h3>
        <p v-if="discussions.length === 0" class="personas-history__empty">
          {{ t('personas.history.noDiscussions') }}
        </p>
        <ul v-else class="personas-history__list" role="list">
          <li v-for="discussion in discussions" :key="discussion.discussion_id">
            <button
              type="button"
              class="personas-history__item"
              :class="{ 'personas-history__item--active': selectedDiscussionId === discussion.discussion_id }"
              @click="onSelectDiscussion(discussion)"
            >
              <span class="personas-history__item-title">
                {{ discussionTitle(discussion) }}
              </span>
              <span class="personas-history__item-meta">
                {{ formatDate(discussion.updated_at) }}
              </span>
            </button>
          </li>
        </ul>
      </section>

      <article
        v-if="viewingTranscript"
        class="personas-history__transcript"
        role="region"
        :aria-label="t('personas.history.transcript')"
      >
        <header class="personas-history__transcript-head">
          <h4>{{ viewingTranscript.title }}</h4>
          <button type="button" class="personas-history__close" @click="viewingTranscript = null">
            <Lucide name="x" size="14" color="text-muted" />
          </button>
        </header>
        <pre class="personas-history__transcript-body">{{ viewingTranscript.body }}</pre>
      </article>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import {
  usePersonas,
  type StoredDiscussion,
  type StoredMeeting,
} from '@composables/usePersonas';
import type { DiscussionMessage } from '@composables/usePersonas';

const props = withDefaults(
  defineProps<{
    mode?: 'meeting' | 'discuss' | 'all';
    selectedMeetingId?: string | null;
    selectedDiscussionId?: string | null;
    pluginDataDir?: string | null;
  }>(),
  {
    mode: 'all',
    selectedMeetingId: null,
    selectedDiscussionId: null,
    pluginDataDir: null,
  },
);

const emit = defineEmits<{
  'view-meeting': [meeting: StoredMeeting];
  'relaunch-meeting': [config: { personaIds: string[]; topic: string; rounds: number }];
  'resume-discussion': [payload: { discussionId: string; personaIds: string[]; messages: DiscussionMessage[] }];
}>();

const { t, locale } = useI18n();
const { listMeetings, listDiscussions, syncHistory } = usePersonas();

const expanded = ref(true);
const meetings = ref(listMeetings());
const discussions = ref(listDiscussions());
const viewingTranscript = ref<{ title: string; body: string } | null>(null);

function refreshLists(): void {
  meetings.value = listMeetings();
  discussions.value = listDiscussions();
}

async function refreshFromBack(): Promise<void> {
  if (props.pluginDataDir) {
    await syncHistory(props.pluginDataDir);
  }
  refreshLists();
}

function onRelaunchMeeting(meeting: StoredMeeting): void {
  emit('relaunch-meeting', {
    personaIds: meeting.persona_ids,
    topic: meeting.topic,
    rounds: meeting.rounds ?? 3,
  });
  emit('view-meeting', meeting);
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function discussionTitle(d: StoredDiscussion): string {
  const firstUser = d.messages.find((m) => m.role === 'user');
  if (firstUser?.content) {
    const preview = firstUser.content.slice(0, 48);
    return preview.length < firstUser.content.length ? `${preview}…` : preview;
  }
  return t('personas.history.discussionFallback', { count: d.persona_ids.length });
}

function onSelectMeeting(meeting: StoredMeeting): void {
  viewingTranscript.value = {
    title: meeting.topic,
    body: meeting.transcript,
  };
  emit('view-meeting', meeting);
}

function onSelectDiscussion(discussion: StoredDiscussion): void {
  const messages: DiscussionMessage[] = discussion.messages.map((m, i) => ({
    id: `hist_${discussion.discussion_id}_${i}`,
    role: m.role,
    content: m.content,
    personaId: m.persona_id,
    personaName: m.persona_name,
    personaRole: m.role_label,
    avatarColor: m.avatar_color ?? 'var(--wp-gold)',
    avatarIcon: m.avatar_icon,
  }));
  emit('resume-discussion', {
    discussionId: discussion.discussion_id,
    personaIds: discussion.persona_ids,
    messages,
  });
}

defineExpose({ refresh: refreshLists, refreshFromBack });

onMounted(() => {
  void refreshFromBack();
});
</script>

<style scoped lang="scss">
.personas-history {
  flex: none;
  border-bottom: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.personas-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--wp-space-2) var(--wp-space-3);
}

.personas-history__title {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.personas-history__toggle {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px;
}

.personas-history__body {
  padding: 0 var(--wp-space-3) var(--wp-space-3);
  max-height: 200px;
  overflow-y: auto;
}

.personas-history__section {
  margin-bottom: var(--wp-space-2);
}

.personas-history__section-title {
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-faint);
}

.personas-history__empty {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.personas-history__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.personas-history__row {
  display: flex;
  align-items: stretch;
  gap: 2px;
}

.personas-history__relaunch {
  flex: none;
  padding: var(--wp-space-1);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: 10px;
  font-weight: 600;
  color: var(--wp-accent);
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: var(--wp-accent-soft);
  }
}

.personas-history__item {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid transparent;
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;
  text-align: left;

  &:hover {
    background: var(--wp-surface-2);
  }

  &--active {
    border-color: var(--wp-gold);
    background: var(--wp-gold-soft);
  }
}

.personas-history__item-title {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.personas-history__item-meta {
  font-size: 10px;
  color: var(--wp-text-faint);
}

.personas-history__transcript {
  margin-top: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
}

.personas-history__transcript-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--wp-space-1) var(--wp-space-2);
  border-bottom: 1px solid var(--wp-border);

  h4 {
    margin: 0;
    font-size: var(--wp-fs-xs);
    font-weight: 600;
  }
}

.personas-history__close {
  border: none;
  background: transparent;
  cursor: pointer;
}

.personas-history__transcript-body {
  margin: 0;
  padding: var(--wp-space-2);
  max-height: 120px;
  overflow: auto;
  font-size: 10px;
  font-family: var(--wp-font-ui);
  white-space: pre-wrap;
}
</style>
