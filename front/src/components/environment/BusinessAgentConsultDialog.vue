<template>
  <q-dialog :model-value="open" @update:model-value="onDialogModelValue">
    <div v-if="selectedAgent" class="business-agent-consult">
      <header class="business-agent-consult__head">
        <div class="business-agent-consult__identity">
          <PersonaAvatar
            :name="selectedAgent.name"
            :color="selectedAgent.avatar_color"
            :icon="selectedAgent.avatar_icon"
          />
          <div>
            <span class="business-agent-consult__eyebrow">{{ t('environment.consultEyebrow') }}</span>
            <h2>{{ selectedAgent.name }}</h2>
            <p>{{ selectedAgent.role }}</p>
          </div>
        </div>
        <button
          type="button"
          class="business-agent-consult__close"
          :aria-label="t('common.close')"
          @click="closeConsultation()"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p class="business-agent-consult__lead">{{ t('environment.consultLead') }}</p>

      <label class="business-agent-consult__field">
        <span>{{ t('environment.consultQuestionLabel') }}</span>
        <textarea
          v-model="question"
          rows="5"
          :placeholder="t('environment.consultQuestionPlaceholder', { name: selectedAgent.name })"
          @keydown.meta.enter.prevent="submit"
          @keydown.ctrl.enter.prevent="submit"
        />
      </label>

      <SpecialistToolsPanel :persona="selectedAgent" :connectors="connectors" />

      <footer class="business-agent-consult__foot">
        <button type="button" class="business-agent-consult__cancel" @click="closeConsultation()">
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="business-agent-consult__submit"
          :disabled="!question.trim() || busy"
          @click="submit"
        >
          {{ busy ? t('common.inProgress') : t('environment.startWithWorkproba') }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import SpecialistToolsPanel from '@components/personas/SpecialistToolsPanel.vue';
import { useBusinessAgentConsultation } from '@composables/useBusinessAgentConsultation';
import { useOrganizationEnvironment } from '@composables/useOrganizationEnvironment';
import { setPendingChatLaunch } from '@composables/usePendingChatLaunch';
import { useSpace } from '@composables/useSpace';
import { bumpSessions } from '@composables/useSessionSync';
import { createSession } from '@services/workspaceSession';

const { t } = useI18n();
const router = useRouter();
const { open, selectedAgent, closeConsultation } = useBusinessAgentConsultation();
const { connectors } = useOrganizationEnvironment();
const { activePath, activeSpaceId } = useSpace();
const question = ref('');
const busy = ref(false);

watch(selectedAgent, () => {
  question.value = '';
});

watch(open, (isOpen) => {
  if (!isOpen) return;
  if (activePath.value && activeSpaceId.value) return;
  Notify.create({ message: t('errors.noSpaceOpen'), color: 'negative' });
  closeConsultation();
}, { immediate: true });

function onDialogModelValue(value: boolean): void {
  if (!value) closeConsultation();
}

async function submit(): Promise<void> {
  const agent = selectedAgent.value;
  const task = question.value.trim();
  if (!agent || !task || busy.value) return;
  if (!activePath.value || !activeSpaceId.value) {
    Notify.create({ message: t('errors.noSpaceOpen'), color: 'negative' });
    return;
  }

  busy.value = true;
  try {
    const session = await createSession(activeSpaceId.value, activePath.value);
    setPendingChatLaunch({
      text: t('environment.consultPrompt', {
        name: agent.name,
        id: agent.id,
        question: task,
      }),
      attachments: [],
      sessionId: session.id,
    });
    bumpSessions();
    closeConsultation();
    await router.push({ name: 'chat_session', params: { id: session.id } });
  } catch (error) {
    Notify.create({
      message: error instanceof Error ? error.message : t('shell.conversationCreateFailed'),
      color: 'negative',
    });
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped lang="scss">
.business-agent-consult {
  width: min(560px, calc(100vw - 2rem));
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-4);
  padding: var(--wp-space-5);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-2);
  font-family: var(--wp-font-ui);
}

.business-agent-consult__head,
.business-agent-consult__identity,
.business-agent-consult__foot {
  display: flex;
  align-items: center;
}

.business-agent-consult__head,
.business-agent-consult__foot {
  justify-content: space-between;
  gap: var(--wp-space-3);
}

.business-agent-consult__identity {
  gap: var(--wp-space-3);
}

.business-agent-consult__eyebrow {
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.business-agent-consult h2,
.business-agent-consult p {
  margin: 0;
}

.business-agent-consult h2 {
  color: var(--wp-text);
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
}

.business-agent-consult__identity p,
.business-agent-consult__lead {
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
}

.business-agent-consult__close {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  cursor: pointer;

  &:hover { background: var(--wp-surface-2); }
}

.business-agent-consult__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
}

.business-agent-consult__field textarea {
  width: 100%;
  resize: vertical;
  box-sizing: border-box;
  padding: var(--wp-space-3);
  border: 1px solid var(--wp-border-strong);
  border-radius: var(--wp-r-md);
  outline: none;
  background: var(--wp-bg);
  color: var(--wp-text);
  font: 400 var(--wp-fs-base)/var(--wp-lh-normal) var(--wp-font-chat);

  &:focus { border-color: var(--wp-accent); }
}

.business-agent-consult__cancel,
.business-agent-consult__submit {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-radius: var(--wp-r-sm);
  font-family: inherit;
  font-size: var(--wp-fs-sm);
  cursor: pointer;
}

.business-agent-consult__cancel {
  background: transparent;
  color: var(--wp-text-muted);
}

.business-agent-consult__submit {
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-weight: 700;

  &:disabled { cursor: default; opacity: 0.45; }
}
</style>
