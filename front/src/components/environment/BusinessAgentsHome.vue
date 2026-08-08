<template>
  <section v-if="agents.length" class="business-agents-home">
    <header class="business-agents-home__head">
      <div>
        <h2 class="business-agents-home__title">{{ t('environment.homeAgentsTitle') }}</h2>
        <p class="business-agents-home__lead">{{ t('environment.homeAgentsLead') }}</p>
      </div>
      <button
        type="button"
        class="business-agents-home__all"
        @click="emit('view-all')"
      >
        {{ t('environment.viewAllAgents') }}
        <Lucide name="arrow-right" size="14" color="text-muted" />
      </button>
    </header>

    <ul class="business-agents-home__list" role="list">
      <li v-for="{ agent, toolLabels } in visibleAgentCards" :key="agent.id" class="business-agents-home__item">
        <div class="business-agents-home__card">
          <button
            type="button"
            class="business-agents-home__profile"
            :aria-label="t('environment.openAgentProfile', { name: agent.name })"
            @click="emit('view-agent', agent)"
          >
            <PersonaAvatar
              :name="agent.name"
              :color="agent.avatar_color"
              :icon="agent.avatar_icon"
            />
            <span class="business-agents-home__identity">
              <span class="business-agents-home__name">{{ agent.name }}</span>
              <span class="business-agents-home__role">{{ agent.role }}</span>
            </span>
            <Lucide name="chevron-right" size="14" color="text-faint" />
          </button>

          <p v-if="agent.description" class="business-agents-home__description">
            {{ agent.description }}
          </p>

          <div v-if="toolLabels.length" class="business-agents-home__tools">
            <span
              v-for="label in toolLabels.slice(0, 2)"
              :key="label"
              class="business-agents-home__tool"
            >
              {{ label }}
            </span>
            <span
              v-if="toolLabels.length > 2"
              class="business-agents-home__tool business-agents-home__tool--more"
            >
              +{{ toolLabels.length - 2 }}
            </span>
          </div>

          <button
            type="button"
            class="business-agents-home__consult"
            @click="emit('consult', agent)"
          >
            <Lucide name="message-circle-more" size="14" color="wp-accent" />
            {{ t('environment.askWorkproba') }}
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import type { ManagedConnector, PersonaInfo } from '@services/aiSidecar';
import { specialistAllowedTools } from '@utils/specialistTools';

const props = defineProps<{
  agents: PersonaInfo[];
  connectors?: ManagedConnector[];
}>();

const emit = defineEmits<{
  consult: [agent: PersonaInfo];
  'view-agent': [agent: PersonaInfo];
  'view-all': [];
}>();

const { t } = useI18n();

const agentToolLabelsById = computed(() => {
  const labelsById = new Map<string, string[]>();
  for (const agent of props.agents) {
    const labels = new Set<string>();
    for (const ref of specialistAllowedTools(agent)) {
      const connector = props.connectors?.find((item) => item.id === ref.connector_id);
      labels.add(connector?.name?.trim() || ref.connector_id);
    }
    labelsById.set(agent.id, [...labels]);
  }
  return labelsById;
});

const visibleAgentCards = computed(() => props.agents.slice(0, 3).map((agent) => ({
  agent,
  toolLabels: agentToolLabelsById.value.get(agent.id) ?? [],
})));
</script>

<style scoped lang="scss">
.business-agents-home {
  width: 100%;
}

.business-agents-home__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--wp-space-3);
  margin-bottom: var(--wp-space-3);
}

.business-agents-home__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-sm);
  font-weight: 700;
  color: var(--wp-text);
}

.business-agents-home__lead {
  margin: var(--wp-space-1) 0 0;
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.business-agents-home__all,
.business-agents-home__consult,
.business-agents-home__profile {
  border: none;
  font-family: inherit;
  cursor: pointer;
}

.business-agents-home__all {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);

  &:hover {
    color: var(--wp-text);
  }
}

.business-agents-home__list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--wp-space-2);
  list-style: none;
  margin: 0;
  padding: 0;
}

.business-agents-home__card {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
}

.business-agents-home__profile {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: 0;
  background: transparent;
  text-align: left;
}

.business-agents-home__identity {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.business-agents-home__name,
.business-agents-home__role {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.business-agents-home__name {
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-weight: 700;
}

.business-agents-home__role,
.business-agents-home__description {
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
}

.business-agents-home__description {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  line-height: var(--wp-lh-normal);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.business-agents-home__tools {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-1);
}

.business-agents-home__tool {
  max-width: 100%;
  overflow: hidden;
  padding: 2px var(--wp-space-2);
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.business-agents-home__tool--more {
  flex: none;
}

.business-agents-home__consult {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  align-self: flex-start;
  margin-top: auto;
  padding: var(--wp-space-1) 0 0;
  background: transparent;
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

@media (max-width: 760px) {
  .business-agents-home__list {
    grid-template-columns: 1fr;
  }
}
</style>
