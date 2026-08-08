<template>
  <aside
    v-if="environmentOpen"
    class="environment-drawer"
    role="complementary"
    :aria-label="t('environment.drawerTitle', { organization: displayOrganizationName })"
  >
    <header class="environment-drawer__head">
      <div class="environment-drawer__identity">
        <span class="environment-drawer__monogram" aria-hidden="true">
          {{ organizationInitial }}
        </span>
        <div>
          <span class="environment-drawer__eyebrow">{{ t('environment.eyebrow') }}</span>
          <h2 class="environment-drawer__title">{{ displayOrganizationName }}</h2>
        </div>
      </div>
      <button
        type="button"
        class="environment-drawer__close"
        :aria-label="t('common.close')"
        @click="closeEnvironment()"
      >
        <Lucide name="x" size="16" color="text-muted" />
      </button>
    </header>

    <div class="environment-drawer__status">
      <span class="environment-drawer__status-dot" :data-connected="cloudConnected" />
      <span>
        {{ cloudConnected ? t('environment.cloudConnected') : t('environment.localEnvironment') }}
      </span>
      <span v-if="userEmail" class="environment-drawer__email">{{ userEmail }}</span>
    </div>

    <div v-if="loadError" class="environment-drawer__alert" role="alert">
      <p>{{ t('environment.loadFailed', { error: loadError }) }}</p>
      <button type="button" class="environment-drawer__alert-retry" @click="onRetryLoad">
        {{ t('environment.retryLoad') }}
      </button>
    </div>

    <template v-if="selectedAgent">
      <button
        type="button"
        class="environment-drawer__back"
        @click="clearBusinessAgentSelection()"
      >
        <Lucide name="arrow-left" size="14" color="text-muted" />
        {{ t('environment.backToEnvironment') }}
      </button>

      <section class="environment-drawer__agent-detail">
        <div class="environment-drawer__agent-identity">
          <PersonaAvatar
            :name="selectedAgent.name"
            :color="selectedAgent.avatar_color"
            :icon="selectedAgent.avatar_icon"
          />
          <div>
            <h3>{{ selectedAgent.name }}</h3>
            <p>{{ selectedAgent.role }}</p>
          </div>
        </div>
        <p class="environment-drawer__agent-description">{{ selectedAgent.description }}</p>
        <SpecialistToolsPanel :persona="selectedAgent" :connectors="connectors" />
        <button
          type="button"
          class="environment-drawer__primary"
          @click="onConsult(selectedAgent)"
        >
          <Lucide name="message-circle-more" size="15" color="wp-canard" />
          {{ t('environment.askWorkprobaToConsult', { name: selectedAgent.name }) }}
        </button>
        <p class="environment-drawer__assistant-note">
          {{ t('environment.assistantRemains') }}
        </p>
      </section>
    </template>

    <template v-else>
      <section class="environment-drawer__assistant">
        <span class="environment-drawer__assistant-icon" aria-hidden="true">
          <Lucide name="sparkles" size="17" color="wp-canard" />
        </span>
        <div>
          <h3>{{ t('environment.workprobaAssistant') }}</h3>
          <p>{{ t('environment.workprobaAssistantLead') }}</p>
        </div>
      </section>

      <section class="environment-drawer__section">
        <header class="environment-drawer__section-head">
          <div>
            <h3>{{ t('environment.businessAgentsTitle') }}</h3>
            <p>{{ t('environment.businessAgentsLead') }}</p>
          </div>
          <span v-if="businessAgents.length" class="environment-drawer__count">
            {{ businessAgents.length }}
          </span>
        </header>

        <p v-if="loading" class="environment-drawer__empty">{{ t('common.loading') }}</p>
        <p v-else-if="!loadError && !businessAgents.length" class="environment-drawer__empty">
          {{ t('environment.noBusinessAgents') }}
        </p>
        <ul v-else class="environment-drawer__agents" role="list">
          <li v-for="agent in businessAgents" :key="agent.id">
            <button
              type="button"
              class="environment-drawer__agent"
              @click="selectBusinessAgent(agent.id)"
            >
              <PersonaAvatar
                :name="agent.name"
                :color="agent.avatar_color"
                :icon="agent.avatar_icon"
              />
              <span class="environment-drawer__agent-copy">
                <span class="environment-drawer__agent-name">{{ agent.name }}</span>
                <span class="environment-drawer__agent-role">{{ agent.role }}</span>
                <span v-if="connectorLabelsFor(agent.id).length" class="environment-drawer__agent-tools">
                  {{ connectorLabelsFor(agent.id).join(' · ') }}
                </span>
              </span>
              <Lucide name="chevron-right" size="14" color="text-faint" />
            </button>
          </li>
        </ul>
      </section>

      <section class="environment-drawer__section environment-drawer__section--technical">
        <h3>{{ t('environment.configurationTitle') }}</h3>
        <p>{{ t('environment.configurationLead') }}</p>

        <div class="environment-drawer__engine" :data-state="engineChipState">
          <div class="environment-drawer__engine-copy">
            <span class="environment-drawer__engine-label">{{ t('environment.engineTitle') }}</span>
            <span class="environment-drawer__engine-value">{{ engineLabel }}</span>
          </div>
          <button type="button" class="environment-drawer__secondary" @click="onOpenEngineSettings">
            <Lucide name="settings-2" size="15" color="text-muted" />
            {{ t('environment.openEngineSettings') }}
          </button>
        </div>

        <button type="button" class="environment-drawer__secondary" @click="onOpenCapabilities">
          <Lucide name="layers" size="15" color="text-muted" />
          {{ t('environment.configureCapabilities') }}
        </button>
      </section>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import SpecialistToolsPanel from '@components/personas/SpecialistToolsPanel.vue';
import type { PersonaInfo } from '@services/aiSidecar';
import { useAppSettings } from '@composables/useAppSettings';
import { useBusinessAgentConsultation } from '@composables/useBusinessAgentConsultation';
import { useChatActivity } from '@composables/useChatActivity';
import { useOrganizationEnvironment } from '@composables/useOrganizationEnvironment';
import { useShellSurfaces } from '@composables/useShellSurfaces';
import { guidedPresetLabel, localizedSetName } from '@utils/providerSets';
import { resolveEnvironmentChipState } from '@utils/environmentStatus';
import { specialistAllowedTools } from '@utils/specialistTools';

const { t } = useI18n();
const router = useRouter();
const { effectiveActiveSet, activeSet, settingsLocked } = useAppSettings();
const { sidecarState } = useChatActivity();
const {
  organizationName,
  userEmail,
  cloudConnected,
  businessAgents,
  connectors,
  loading,
  loadError,
  refresh,
} = useOrganizationEnvironment();
const {
  environmentOpen,
  selectedBusinessAgentId,
  closeEnvironment,
  openCapabilities,
  selectBusinessAgent,
  clearBusinessAgentSelection,
} = useShellSurfaces();
const { requestConsultation } = useBusinessAgentConsultation();

const displayOrganizationName = computed(
  () => organizationName.value || t('environment.defaultOrganization'),
);
const organizationInitial = computed(
  () => displayOrganizationName.value.trim().charAt(0).toUpperCase() || 'W',
);
const selectedAgent = computed(
  () => businessAgents.value.find((agent) => agent.id === selectedBusinessAgentId.value) ?? null,
);
const hasEffectiveEngine = computed(() => Boolean(effectiveActiveSet.value));
const engineChipState = computed(() => resolveEnvironmentChipState({
  sidecarState: sidecarState.value,
  hasEffectiveEngine: hasEffectiveEngine.value,
  cloudConnected: cloudConnected.value,
}));
const engineLabel = computed(() => {
  if (!hasEffectiveEngine.value) return t('environment.engineMissing');
  const set = effectiveActiveSet.value ?? activeSet.value;
  if (!set) return t('environment.engineMissing');
  if (settingsLocked.value) return guidedPresetLabel(set, t);
  return localizedSetName(set, t);
});

const agentConnectorLabelsById = computed(() => {
  const labelsById = new Map<string, string[]>();
  for (const agent of businessAgents.value) {
    const labels = new Set<string>();
    for (const ref of specialistAllowedTools(agent)) {
      const connector = connectors.value.find((item) => item.id === ref.connector_id);
      labels.add(connector?.name?.trim() || ref.connector_id);
    }
    labelsById.set(agent.id, [...labels]);
  }
  return labelsById;
});

function connectorLabelsFor(agentId: string): string[] {
  return agentConnectorLabelsById.value.get(agentId) ?? [];
}

function onConsult(agent: PersonaInfo): void {
  requestConsultation(agent);
  closeEnvironment();
}

function onOpenCapabilities(): void {
  openCapabilities();
}

function onOpenEngineSettings(): void {
  closeEnvironment();
  void router.push({ name: 'settings_models' });
}

function onRetryLoad(): void {
  void refresh(true);
}

watch(environmentOpen, (open) => {
  if (open) void refresh(true);
});
</script>

<style scoped lang="scss">
.environment-drawer {
  position: absolute;
  inset: 0 0 0 auto;
  z-index: 21;
  width: clamp(380px, 36vw, 440px);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-4);
  padding: var(--wp-space-4);
  overflow-y: auto;
  border-left: 1px solid var(--wp-border);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-2);
  animation: environment-drawer-in var(--wp-dur) var(--wp-ease);
}

@keyframes environment-drawer-in {
  from { opacity: 0; transform: translateX(12px); }
  to { opacity: 1; transform: translateX(0); }
}

.environment-drawer__head,
.environment-drawer__identity,
.environment-drawer__status,
.environment-drawer__assistant,
.environment-drawer__section-head,
.environment-drawer__agent,
.environment-drawer__agent-identity,
.environment-drawer__primary,
.environment-drawer__secondary,
.environment-drawer__back {
  display: flex;
  align-items: center;
}

.environment-drawer__head,
.environment-drawer__section-head {
  justify-content: space-between;
  gap: var(--wp-space-3);
}

.environment-drawer__identity,
.environment-drawer__assistant,
.environment-drawer__agent,
.environment-drawer__agent-identity {
  gap: var(--wp-space-3);
}

.environment-drawer__monogram,
.environment-drawer__assistant-icon {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--wp-r-md);
  background: var(--wp-primary-soft);
  color: var(--wp-primary);
  font-family: var(--wp-font-head);
  font-weight: 700;
}

.environment-drawer__monogram {
  width: 40px;
  height: 40px;
  font-size: var(--wp-fs-md);
}

.environment-drawer__assistant-icon {
  width: 34px;
  height: 34px;
}

.environment-drawer__eyebrow {
  display: block;
  margin-bottom: 2px;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.environment-drawer__title,
.environment-drawer h3,
.environment-drawer p {
  margin: 0;
}

.environment-drawer__title {
  color: var(--wp-text);
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
}

.environment-drawer__close {
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

.environment-drawer__status {
  flex-wrap: wrap;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
}

.environment-drawer__status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-warning);

  &[data-connected='true'] { background: var(--wp-success); }
}

.environment-drawer__email {
  margin-left: auto;
  color: var(--wp-text-faint);
}

.environment-drawer__alert {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-md);
  background: var(--wp-danger-soft);
  color: var(--wp-danger);
  font-size: var(--wp-fs-xs);
}

.environment-drawer__alert p {
  margin: 0;
  line-height: var(--wp-lh-normal);
}

.environment-drawer__alert-retry {
  align-self: flex-start;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-danger);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-danger);
  font-family: inherit;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
}

.environment-drawer__engine {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);

  &[data-state='error'] {
    border-color: var(--wp-danger);
    background: var(--wp-danger-soft);
  }
}

.environment-drawer__engine-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.environment-drawer__engine-label {
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.environment-drawer__engine-value {
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
}

.environment-drawer__assistant {
  padding: var(--wp-space-3);
  border-radius: var(--wp-r-md);
  background: var(--wp-primary-soft);
}

.environment-drawer__assistant h3,
.environment-drawer__section h3,
.environment-drawer__agent-identity h3 {
  color: var(--wp-text);
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-sm);
  font-weight: 700;
}

.environment-drawer__assistant p,
.environment-drawer__section p,
.environment-drawer__agent-identity p,
.environment-drawer__agent-description,
.environment-drawer__assistant-note {
  margin-top: var(--wp-space-1);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
}

.environment-drawer__section {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.environment-drawer__section--technical {
  margin-top: auto;
  padding-top: var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
}

.environment-drawer__count {
  min-width: 24px;
  padding: 2px var(--wp-space-2);
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-align: center;
}

.environment-drawer__agents {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.environment-drawer__agent {
  width: 100%;
  padding: var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;

  &:hover { background: var(--wp-surface-2); }
}

.environment-drawer__agent-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.environment-drawer__agent-name {
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-weight: 700;
}

.environment-drawer__agent-role,
.environment-drawer__agent-tools {
  overflow: hidden;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.environment-drawer__agent-tools {
  margin-top: 2px;
  color: var(--wp-text-faint);
}

.environment-drawer__back,
.environment-drawer__primary,
.environment-drawer__secondary {
  align-self: flex-start;
  gap: var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  font-family: inherit;
  font-size: var(--wp-fs-sm);
  cursor: pointer;
}

.environment-drawer__back {
  padding: 0;
  background: transparent;
  color: var(--wp-text-muted);
}

.environment-drawer__agent-detail {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.environment-drawer__primary {
  padding: var(--wp-space-2) var(--wp-space-3);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-weight: 700;
}

.environment-drawer__secondary {
  padding: var(--wp-space-2) 0;
  background: transparent;
  color: var(--wp-text-muted);

  &:hover { color: var(--wp-text); }
}

.environment-drawer__empty {
  padding: var(--wp-space-3);
  border: 1px dashed var(--wp-border-strong);
  border-radius: var(--wp-r-md);
  text-align: center;
}

@media (max-width: 620px) {
  .environment-drawer { width: 100%; }
}
</style>
