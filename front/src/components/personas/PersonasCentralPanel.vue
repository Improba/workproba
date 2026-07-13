<template>
  <div class="personas-central">
    <div v-if="!pluginActive" class="personas-central__empty">
      {{ t('personas.picker.empty') }}
    </div>

    <template v-else>
      <p v-if="loading" class="personas-central__hint">{{ t('common.loading') }}</p>
      <p v-else-if="loadError" class="personas-central__hint personas-central__hint--error">
        {{ t('personas.errors.loadFailed') }}
        <button type="button" class="personas-central__retry" @click="loadSets">
          {{ t('common.retry') }}
        </button>
      </p>
      <p v-else-if="selectablePersonas.length === 0" class="personas-central__hint">
        {{ t('personas.picker.empty') }}
      </p>

      <template v-else>
        <header class="personas-central__intro">
          <h2 class="personas-central__title">{{ t('personas.panel.chooseTitle') }}</h2>
          <p class="personas-central__lead">{{ t('personas.panel.chooseLead') }}</p>
        </header>

        <ul class="personas-central__list" role="list">
          <li v-for="persona in selectablePersonas" :key="persona.id">
            <article class="personas-central__card">
              <button
                type="button"
                class="personas-central__card-main"
                :title="personaCardTitle(persona)"
                @click="emit('discuss', [persona.id])"
              >
                <PersonaAvatar
                  :name="persona.name"
                  :color="persona.avatar_color"
                  :icon="persona.avatar_icon"
                />
                <span class="personas-central__card-text">
                  <span class="personas-central__card-name">{{ persona.name }}</span>
                  <span class="personas-central__card-role">{{ persona.role }}</span>
                </span>
                <Lucide
                  class="personas-central__card-cue"
                  name="message-circle"
                  size="16"
                  color="wp-gold"
                />
              </button>
              <button
                type="button"
                class="personas-central__card-secondary"
                @click="emit('ask-opinion', [persona.id])"
              >
                {{ t('personas.panel.askTheirOpinion') }}
              </button>
              <button
                v-if="showAdvanced"
                type="button"
                class="personas-central__card-secondary personas-central__card-secondary--ghost"
                @click="openPersonaDetail(persona)"
              >
                {{ t('personas.panel.viewProfile') }}
              </button>
            </article>
          </li>
        </ul>

        <div class="personas-central__footer">
          <button type="button" class="personas-central__meeting" @click="emit('meeting')">
            <Lucide name="users" size="15" color="wp-gold" />
            <span>{{ t('personas.actions.simulateMeeting') }}</span>
          </button>
          <p class="personas-central__meeting-hint">{{ t('personas.actions.simulateMeetingHint') }}</p>
        </div>
      </template>

      <PersonasHistoryPanel
        v-if="!loading"
        ref="historyRef"
        mode="all"
        class="personas-central__history"
        :default-expanded="false"
        :plugin-data-dir="pluginDataDir"
        @relaunch-meeting="onRelaunchMeeting"
        @resume-discussion="onResumeDiscussion"
      />

      <PersonasConfidentialityHint class="personas-central__privacy" />

      <section v-if="showAdvanced && selectablePersonas.length" class="personas-central__advanced">
        <button
          type="button"
          class="personas-central__advanced-toggle"
          :aria-expanded="advancedOpen"
          @click="advancedOpen = !advancedOpen"
        >
          {{ t('personas.panel.customizeTitle') }}
          <Lucide :name="advancedOpen ? 'chevron-up' : 'chevron-down'" size="14" color="text-muted" />
        </button>

        <div v-show="advancedOpen" class="personas-central__advanced-body">
          <h3 class="personas-central__advanced-label">{{ t('personas.panel.setsTitle') }}</h3>
          <ul v-if="sets.length" class="personas-central__sets" role="list">
            <li v-for="set in sets" :key="set.id">
              <button
                type="button"
                class="personas-central__set"
                :class="{ 'personas-central__set--active': set.id === activeSet?.id }"
                @click="onSelectSet(set.id)"
              >
                <span class="personas-central__set-name">{{ set.name }}</span>
                <span class="personas-central__set-count">
                  {{ t('personas.panel.personaCount', { count: set.personas.length }) }}
                </span>
              </button>
              <button
                v-if="isCustomSet(set.id)"
                type="button"
                class="personas-central__set-edit"
                :title="t('personas.sets.edit.title')"
                @click.stop="openSetEditor(set)"
              >
                {{ t('personas.sets.edit.edit') }}
              </button>
            </li>
          </ul>
          <button type="button" class="personas-central__set-create" @click="openSetEditor()">
            {{ t('personas.sets.edit.create') }}
          </button>
          <p class="personas-central__set-note">{{ t('personas.sets.edit.localOnlyNote') }}</p>
          <p class="personas-central__cost">
            {{ t('personas.panel.sessionCostSummary', { calls: sessionCalls }) }}
          </p>
        </div>
      </section>
    </template>

    <q-dialog v-model="personaDetailOpen">
      <div v-if="selectedPersona" class="personas-central__detail">
        <h3>{{ selectedPersona.name }}</h3>
        <p class="personas-central__detail-role">{{ selectedPersona.role }}</p>
        <p v-if="selectedPersona.description" class="personas-central__detail-desc">
          {{ selectedPersona.description }}
        </p>
        <pre v-if="selectedPersona.system_prompt" class="personas-central__detail-prompt">{{
          truncatePrompt(selectedPersona.system_prompt)
        }}</pre>
        <button type="button" class="personas-central__detail-close" @click="personaDetailOpen = false">
          {{ t('common.close') }}
        </button>
      </div>
    </q-dialog>

    <q-dialog v-model="setEditorOpen">
      <form class="personas-central__editor" @submit.prevent="saveSetEditor">
        <h3>{{ editingSet ? t('personas.sets.edit.title') : t('personas.sets.edit.create') }}</h3>
        <label class="personas-central__editor-field">
          <span>{{ t('personas.sets.edit.nameLabel') }}</span>
          <input v-model="setEditorName" type="text" required />
        </label>
        <fieldset class="personas-central__editor-field">
          <legend>{{ t('personas.sets.edit.selectPersonas') }}</legend>
          <label
            v-for="persona in builtinPersonas"
            :key="persona.id"
            class="personas-central__editor-check"
          >
            <input v-model="setEditorPersonaIds" type="checkbox" :value="persona.id" />
            {{ persona.name }}
          </label>
        </fieldset>
        <footer class="personas-central__editor-foot">
          <button type="button" @click="setEditorOpen = false">{{ t('common.cancel') }}</button>
          <button type="submit" class="personas-central__editor-save">{{ t('common.save') }}</button>
        </footer>
      </form>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import PersonasConfidentialityHint from '@components/personas/PersonasConfidentialityHint.vue';
import PersonasHistoryPanel from '@components/personas/PersonasHistoryPanel.vue';
import { useAppSettings } from '@composables/useAppSettings';
import {
  estimateSessionCalls,
  usePersonas,
  type DiscussionMessage,
} from '@composables/usePersonas';
import type { PersonaInfo, PersonaSet } from '@services/aiSidecar';

const props = defineProps<{
  pluginActive: boolean;
  pluginDataDir?: string | null;
}>();

const emit = defineEmits<{
  'ask-opinion': [personaIds: string[]];
  meeting: [];
  discuss: [personaIds: string[]];
  'resume-discussion': [payload: {
    discussionId: string;
    personaIds: string[];
    messages: DiscussionMessage[];
  }];
  'relaunch-meeting': [config: { personaIds: string[]; topic: string; rounds: number }];
}>();

const { t } = useI18n();
const { settingsMode } = useAppSettings();
const {
  sets,
  activeSet,
  builtinPersonas,
  selectablePersonas,
  loading,
  loadError,
  refresh,
  setActiveSet,
  listMeetings,
  listDiscussions,
  listCustomSets,
  saveCustomSet,
} = usePersonas();

const historyRef = ref<InstanceType<typeof PersonasHistoryPanel> | null>(null);
const personaDetailOpen = ref(false);
const selectedPersona = ref<PersonaInfo | null>(null);
const setEditorOpen = ref(false);
const editingSet = ref<PersonaSet | null>(null);
const setEditorName = ref('');
const setEditorPersonaIds = ref<string[]>([]);
const advancedOpen = ref(false);

const showAdvanced = computed(() => settingsMode.value === 'advanced');

const customSetIds = computed(() => new Set(listCustomSets().map((s) => s.id)));

const sessionCalls = computed(() =>
  estimateSessionCalls(listMeetings(), listDiscussions()),
);

function personaCardTitle(persona: PersonaInfo): string {
  if (persona.description?.trim()) return persona.description.trim();
  return t('personas.panel.talkToPersona', { name: persona.name });
}

function onSelectSet(setId: string): void {
  setActiveSet(setId);
}

function onRelaunchMeeting(config: {
  personaIds: string[];
  topic: string;
  rounds: number;
}): void {
  emit('relaunch-meeting', config);
}

function isCustomSet(setId: string): boolean {
  return customSetIds.value.has(setId);
}

function openPersonaDetail(persona: PersonaInfo): void {
  selectedPersona.value = persona;
  personaDetailOpen.value = true;
}

function truncatePrompt(prompt: string, max = 280): string {
  if (prompt.length <= max) return prompt;
  return `${prompt.slice(0, max)}…`;
}

function openSetEditor(set?: PersonaSet): void {
  editingSet.value = set ?? null;
  setEditorName.value = set?.name ?? '';
  setEditorPersonaIds.value = set?.personas.map((p) => p.id) ?? [];
  setEditorOpen.value = true;
}

async function saveSetEditor(): Promise<void> {
  const selected = builtinPersonas.value.filter((p) =>
    setEditorPersonaIds.value.includes(p.id),
  );
  if (!setEditorName.value.trim() || selected.length === 0) return;
  if (!props.pluginDataDir) {
    Notify.create({ message: t('personas.errors.unavailable'), color: 'negative' });
    return;
  }
  const id = editingSet.value?.id ?? `custom_${Date.now()}`;
  await saveCustomSet(props.pluginDataDir, {
    id,
    name: setEditorName.value.trim(),
    personas: selected,
  });
  setActiveSet(id);
  setEditorOpen.value = false;
}

function onResumeDiscussion(payload: {
  discussionId: string;
  personaIds: string[];
  messages: DiscussionMessage[];
}): void {
  emit('resume-discussion', payload);
}

async function loadSets(): Promise<void> {
  if (!props.pluginActive || !props.pluginDataDir) return;
  await refresh(props.pluginDataDir);
}

watch(
  () => props.pluginDataDir,
  () => {
    void loadSets();
  },
);

onMounted(() => {
  void loadSets();
});

defineExpose({
  refreshHistory: () => historyRef.value?.refresh?.(),
});
</script>

<style scoped lang="scss">
.personas-central {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  overflow-y: auto;
  padding: var(--wp-space-3) var(--wp-space-2) var(--wp-space-2);
}

.personas-central__empty,
.personas-central__hint {
  margin: 0;
  padding: var(--wp-space-2);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-faint);
  text-align: center;
}

.personas-central__intro {
  padding: 0 var(--wp-space-1);
}

.personas-central__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-sm);
  font-weight: 700;
  color: var(--wp-text);
  line-height: var(--wp-lh-tight);
}

.personas-central__lead {
  margin: var(--wp-space-1) 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  line-height: var(--wp-lh-normal);
}

.personas-central__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.personas-central__card {
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  overflow: hidden;
  transition: border-color var(--wp-dur) var(--wp-ease), box-shadow var(--wp-dur) var(--wp-ease);

  &:hover {
    border-color: color-mix(in srgb, var(--wp-gold) 35%, var(--wp-border));
    box-shadow: var(--wp-shadow-1);
  }
}

.personas-central__card-main {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;

  &:hover {
    background: var(--wp-gold-soft);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-accent);
    outline-offset: -2px;
  }
}

.personas-central__card-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.personas-central__card-name {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.personas-central__card-role {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.personas-central__card-cue {
  flex: none;
  opacity: 0.7;
}

.personas-central__card-secondary {
  display: block;
  width: 100%;
  padding: var(--wp-space-1) var(--wp-space-3) var(--wp-space-2);
  border: none;
  border-top: 1px solid var(--wp-border);
  background: transparent;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  text-align: left;
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
    background: var(--wp-surface-2);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-accent);
    outline-offset: -2px;
  }

  &--ghost {
    font-weight: 500;
    color: var(--wp-text-faint);
  }
}

.personas-central__footer {
  padding: var(--wp-space-2) var(--wp-space-1) 0;
  border-top: 1px solid var(--wp-border);
}

.personas-central__meeting {
  width: 100%;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-1);
  border: none;
  background: transparent;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
  cursor: pointer;
  text-align: left;

  &:hover {
    color: color-mix(in srgb, var(--wp-gold) 70%, var(--wp-text));
  }

  &:focus-visible {
    outline: 2px solid var(--wp-accent);
    outline-offset: 2px;
    border-radius: var(--wp-r-sm);
  }
}

.personas-central__meeting-hint {
  margin: 0;
  padding: 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  line-height: var(--wp-lh-normal);
}

.personas-central__history {
  flex: none;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  overflow: hidden;
}

.personas-central__privacy {
  margin-top: auto;
  padding: 0 var(--wp-space-1);
}

.personas-central__advanced {
  padding: var(--wp-space-2) var(--wp-space-1) 0;
  border-top: 1px dashed var(--wp-border);
}

.personas-central__advanced-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  padding: var(--wp-space-1) 0;
  border: none;
  background: transparent;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid var(--wp-accent);
    outline-offset: 2px;
    border-radius: var(--wp-r-sm);
  }
}

.personas-central__advanced-body {
  margin-top: var(--wp-space-2);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
}

.personas-central__advanced-label {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.personas-central__sets {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);

  li {
    display: flex;
    align-items: stretch;
    gap: var(--wp-space-1);
  }
}

.personas-central__set-create {
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px dashed var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.personas-central__set-note {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.personas-central__set-edit {
  flex: none;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: var(--wp-fs-xs);
  cursor: pointer;
}

.personas-central__set {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--wp-space-2);
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

.personas-central__set-name {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.personas-central__set-count {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.personas-central__cost {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-central__detail,
.personas-central__editor {
  padding: var(--wp-space-4);
  background: var(--wp-surface);
  border-radius: var(--wp-r-md);
  min-width: 320px;
  max-width: 480px;
}

.personas-central__detail-role {
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.personas-central__detail-desc {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-central__detail-prompt {
  font-size: var(--wp-fs-xs);
  white-space: pre-wrap;
  max-height: 160px;
  overflow: auto;
  background: var(--wp-surface-2);
  padding: var(--wp-space-2);
  border-radius: var(--wp-r-sm);
}

.personas-central__detail-close {
  margin-top: var(--wp-space-2);
}

.personas-central__editor-field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  margin-bottom: var(--wp-space-2);
  font-size: var(--wp-fs-sm);
}

.personas-central__editor-check {
  display: flex;
  align-items: center;
  gap: var(--wp-space-1);
}

.personas-central__editor-foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.personas-central__editor-save {
  font-weight: 600;
}
</style>
