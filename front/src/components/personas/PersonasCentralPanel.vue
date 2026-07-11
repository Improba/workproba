<template>
  <div class="personas-central">
    <header class="personas-central__head">
      <span class="personas-central__brand">{{ t('personas.panel.title') }}</span>
    </header>

    <div v-if="!pluginActive" class="personas-central__empty">
      {{ t('personas.picker.empty') }}
    </div>

    <template v-else>
      <PersonasConfidentialityHint class="personas-central__privacy" />

      <section class="personas-central__section">
        <h3 class="personas-central__section-title">{{ t('personas.panel.setsTitle') }}</h3>
        <p v-if="loading" class="personas-central__hint">{{ t('common.loading') }}</p>
        <p v-else-if="sets.length === 0" class="personas-central__hint">
          {{ t('personas.picker.empty') }}
        </p>
        <ul v-else class="personas-central__sets" role="list">
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
      </section>

      <section v-if="personas.length" class="personas-central__section">
        <h3 class="personas-central__section-title">{{ t('personas.panel.personasTitle') }}</h3>
        <ul class="personas-central__personas" role="list">
          <li v-for="persona in personas" :key="persona.id">
            <button
              type="button"
              class="personas-central__persona-card"
              @click="openPersonaDetail(persona)"
            >
              <span
                class="personas-central__persona-dot"
                :style="{ backgroundColor: persona.avatar_color }"
              />
              <span class="personas-central__persona-name">{{ persona.name }}</span>
              <span class="personas-central__persona-role">{{ persona.role }}</span>
            </button>
          </li>
        </ul>
      </section>

      <section v-if="personas.length" class="personas-central__section">
        <h3 class="personas-central__section-title">{{ t('personas.panel.actionsTitle') }}</h3>
        <div class="personas-central__actions">
          <button type="button" class="personas-central__action" @click="emit('ask-opinion')">
            {{ t('personas.actions.askOpinion') }}
          </button>
          <button type="button" class="personas-central__action" @click="emit('meeting')">
            {{ t('personas.actions.simulateMeeting') }}
          </button>
          <button type="button" class="personas-central__action" @click="emit('discuss')">
            {{ t('personas.actions.discuss') }}
          </button>
        </div>
      </section>

      <section class="personas-central__section personas-central__section--cost">
        <h3 class="personas-central__section-title">{{ t('personas.panel.sessionCostTitle') }}</h3>
        <p class="personas-central__cost">
          {{ t('personas.panel.sessionCostSummary', { calls: sessionCalls }) }}
        </p>
      </section>

      <PersonasHistoryPanel
        ref="historyRef"
        mode="all"
        class="personas-central__history"
        :plugin-data-dir="pluginDataDir"
        @view-meeting="onViewMeeting"
        @relaunch-meeting="onRelaunchMeeting"
        @resume-discussion="onResumeDiscussion"
      />
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
import PersonasConfidentialityHint from '@components/personas/PersonasConfidentialityHint.vue';
import PersonasHistoryPanel from '@components/personas/PersonasHistoryPanel.vue';
import {
  estimateSessionCalls,
  usePersonas,
  type DiscussionMessage,
  type StoredMeeting,
} from '@composables/usePersonas';
import type { PersonaInfo, PersonaSet } from '@services/aiSidecar';

const props = defineProps<{
  pluginActive: boolean;
  pluginDataDir?: string | null;
}>();

const emit = defineEmits<{
  'ask-opinion': [];
  meeting: [];
  discuss: [];
  'view-meeting': [meeting: StoredMeeting];
  'resume-discussion': [payload: {
    discussionId: string;
    personaIds: string[];
    messages: DiscussionMessage[];
  }];
  'relaunch-meeting': [config: { personaIds: string[]; topic: string; rounds: number }];
}>();

const { t } = useI18n();
const {
  sets,
  activeSet,
  personas,
  loading,
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

const customSetIds = computed(() => new Set(listCustomSets().map((s) => s.id)));

const builtinPersonas = computed(() => {
  const builtin = sets.value.find((s) => !customSetIds.value.has(s.id));
  return builtin?.personas ?? personas.value;
});

const sessionCalls = computed(() =>
  estimateSessionCalls(listMeetings(), listDiscussions()),
);

function onSelectSet(setId: string): void {
  setActiveSet(setId);
}

function onViewMeeting(meeting: StoredMeeting): void {
  emit('view-meeting', meeting);
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
  if (!setEditorName.value.trim() || selected.length === 0 || !props.pluginDataDir) return;
  const id = editingSet.value?.id ?? `custom_${Date.now()}`;
  await saveCustomSet(props.pluginDataDir, {
    id,
    name: setEditorName.value.trim(),
    personas: selected,
  });
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
  overflow-y: auto;
  padding: 0 var(--wp-space-2) var(--wp-space-2);
}

.personas-central__head {
  padding: var(--wp-space-3) var(--wp-space-2) var(--wp-space-2);
}

.personas-central__brand {
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--wp-gold);
}

.personas-central__empty,
.personas-central__hint {
  padding: var(--wp-space-3) var(--wp-space-2);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-faint);
}

.personas-central__privacy {
  padding: 0 var(--wp-space-2) var(--wp-space-2);
}

.personas-central__section {
  padding: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);

  &--cost {
    border-color: color-mix(in srgb, var(--wp-gold) 35%, var(--wp-border));
    background: var(--wp-gold-soft);
  }
}

.personas-central__section-title {
  margin: 0 0 var(--wp-space-2);
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
  gap: 4px;

  li {
    display: flex;
    align-items: stretch;
    gap: 4px;
  }
}

.personas-central__set-create {
  margin-top: var(--wp-space-2);
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
  margin: var(--wp-space-1) 0 0;
  font-size: 10px;
  color: var(--wp-text-faint);
}

.personas-central__set-edit {
  flex: none;
  padding: var(--wp-space-1);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-size: 10px;
  cursor: pointer;
}

.personas-central__personas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--wp-space-1);
}

.personas-central__persona-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  cursor: pointer;
  text-align: left;
  width: 100%;

  &:hover {
    border-color: var(--wp-gold);
    background: var(--wp-gold-soft);
  }
}

.personas-central__persona-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--wp-r-pill);
}

.personas-central__persona-name {
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
}

.personas-central__persona-role {
  font-size: 10px;
  color: var(--wp-text-faint);
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

.personas-central__actions {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
}

.personas-central__action {
  width: 100%;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-gold) 40%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
  cursor: pointer;
  text-align: left;

  &:hover {
    background: var(--wp-gold-soft);
  }
}

.personas-central__cost {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-central__history {
  flex: none;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  overflow: hidden;
}
</style>
