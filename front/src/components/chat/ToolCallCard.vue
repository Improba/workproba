<template>
  <div class="tool-call-card" data-testid="tool-call-card">
    <div class="tool-call-card__human">
      <span
        class="tool-call-card__dot"
        :class="`tool-call-card__dot--${toolCall.status}`"
        aria-hidden="true"
      />
      <p class="tool-call-card__summary">{{ humanLabel }}</p>
      <button
        v-if="canOpenFile"
        type="button"
        class="tool-call-card__file-btn"
        @click="emit('open-file', toolCall.filePath!)"
      >
        <Lucide :name="fileIcon" size="xs" color="wp-accent" />
        {{ fileName }}
      </button>
      <button
        type="button"
        class="tool-call-card__tech-pill"
        :class="{
          'tool-call-card__tech-pill--active': isTechView,
          'tool-call-card__tech-pill--expanded': isTechView,
        }"
        :aria-pressed="isTechView"
        :aria-expanded="isTechView"
        @click="toggleTechView"
      >
        <Lucide
          name="chevron-down"
          size="xs"
          color="wp-text-muted"
          :class="isTechView ? 'tool-call-card__chevron tool-call-card__chevron--up' : 'tool-call-card__chevron'"
        />
        {{ t('common.showDetails') }}
      </button>
    </div>

    <div v-if="isTechView" class="tool-call-card__tech">
      <!-- Vue détaillée lisible : où, dans quoi, résultat, durée, statut -->
      <div class="tool-call-card__tech-header">
        <span class="tool-call-card__tool-name">{{ toolCall.name }}</span>
        <span
          class="tool-call-card__status-chip"
          :class="`tool-call-card__status-chip--${toolCall.status}`"
        >
          {{ statusLabel }}
        </span>
        <q-spinner
          v-if="toolCall.status === 'running' || toolCall.status === 'awaiting_confirmation' || toolCall.status === 'pending_confirmation'"
          size="14px"
          class="tool-call-card__spinner"
        />
      </div>

      <dl class="tool-call-card__detail-rows">
        <div
          v-for="row in details.rows"
          :key="row.label"
          class="tool-call-card__detail-row"
        >
          <dt class="tool-call-card__detail-label">{{ row.label }}</dt>
          <dd class="tool-call-card__detail-value">{{ row.value }}</dd>
        </div>
      </dl>

      <!-- Sous-bloc technique repliable : args + résultat bruts -->
      <button
        type="button"
        class="tool-call-card__raw-toggle"
        :aria-expanded="showRaw"
        @click="toggleRaw"
      >
        <Lucide
          name="chevron-down"
          size="xs"
          color="wp-text-muted"
          :class="showRaw ? 'tool-call-card__chevron tool-call-card__chevron--up' : 'tool-call-card__chevron'"
        />
        {{ isTechView ? t('common.hideTechnicalDetails') : t('common.showTechnicalDetails') }}
      </button>

      <div v-if="showRaw" class="tool-call-card__raw">
        <section v-if="toolCall.args && Object.keys(toolCall.args).length">
          <h4 class="tool-call-card__section-title">{{ t('common.arguments') }}</h4>
          <pre class="tool-call-card__json">{{ formattedArgs }}</pre>
        </section>

        <section v-if="toolCall.result !== undefined">
          <h4 class="tool-call-card__section-title">{{ t('common.result') }}</h4>
          <pre class="tool-call-card__json">{{ formattedResult }}</pre>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useToolCallExpansion } from '@composables/useToolCallExpansion';
import { fallbackHumanLabel } from '@utils/toolCallHumanLabel';
import { buildToolCallDetails, durationLabel, toolCallStatusLabel } from '@utils/toolCallDetails';
import type { ChatToolCall } from '#types';

const props = defineProps<{
  toolCall: ChatToolCall;
  projectPath?: string | null;
  sessionId?: string | null;
  /** Masque le résumé redondant quand la carte de confirmation est affichée en dessous. */
  confirmationActive?: boolean;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
}>();

// État déplié propre à chaque carte : par défaut replié, mais on peut en
// déplier plusieurs indépendamment. La préférence globale `toolCallView` ne
// sert qu'à semer la valeur initiale (un utilisateur ayant choisi "tech" par
// défaut conserve ce comportement, sans verrouiller toutes les cartes ensemble).
//
// L'état est porté par `useToolCallExpansion` (hors du composant) : il survit
// au recyclage du `DynamicScroller` qui héberge les messages, sinon la section
// dépliée se replierait immédiatement lors du re-mesurage du virtual scroller.
const { isTechView, showRaw, toggleTechView, toggleRaw } = useToolCallExpansion(
  () => props.toolCall.id,
);

const { t } = useI18n();

const humanLabel = computed(() => {
  if (props.confirmationActive) {
    return t('chat.awaitingConfirmation');
  }
  if (
    props.toolCall.status === 'pending_confirmation' ||
    props.toolCall.status === 'awaiting_confirmation'
  ) {
    const summary = props.toolCall.humanSummary?.trim();
    if (summary) return summary;
    return t('chat.awaitingConfirmation');
  }
  const summary = props.toolCall.humanSummary?.trim();
  const base = summary || fallbackHumanLabel(props.toolCall.name, props.toolCall.args);
  if (props.toolCall.autoApproved) {
    return `${base} · ${t('toolCalls.autoApproved')}`;
  }
  return base;
});

const details = computed(() => buildToolCallDetails(props.toolCall));

const statusLabel = computed(() => toolCallStatusLabel(props.toolCall));

const formattedArgs = computed(() =>
  JSON.stringify(props.toolCall.args ?? {}, null, 2),
);

const formattedResult = computed(() => {
  const { result } = props.toolCall;
  if (typeof result === 'string') return result;
  return JSON.stringify(result, null, 2);
});

const fileName = computed(() => {
  const path = props.toolCall.filePath ?? '';
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
});

/** N'ouvrir que si le fichier a bien été écrit (évite un clic pendant la confirmation). */
const canOpenFile = computed(
  () =>
    Boolean(props.toolCall.filePath) &&
    props.toolCall.status === 'success' &&
    !props.confirmationActive,
);

const fileIcon = computed(() => {
  const name = fileName.value.toLowerCase();
  if (name.endsWith('.pptx') || name.endsWith('.ppt')) return 'presentation';
  if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) {
    return 'file-spreadsheet';
  }
  if (name.endsWith('.pdf')) return 'file-text';
  return 'file-text';
});
</script>

<style scoped lang="scss">
.tool-call-card {
  width: 100%;
  margin: 0;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  overflow: hidden;
}

.tool-call-card__human {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.65rem 0.85rem;
  color: var(--wp-text);
}

.tool-call-card__dot {
  flex: 0 0 auto;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);

  &--running {
    background: var(--wp-accent);
    animation: wp-breathe 1.6s ease-in-out infinite;
  }

  &--success {
    background: var(--wp-success);
  }

  &--error {
    background: var(--wp-danger);
  }

  &--pending {
    background: var(--wp-gold);
  }

  &--awaiting_confirmation,
  &--pending_confirmation {
    background: var(--wp-gold);
    animation: wp-breathe 1.6s ease-in-out infinite;
  }
}

.tool-call-card__summary {
  flex: 1 1 auto;
  margin: 0;
  min-width: 0;
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);
}

.tool-call-card__file-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-sm);
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.tool-call-card__tech-pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    color var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    border-color: var(--wp-border-strong);
    color: var(--wp-text);
  }

  &--active {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
    color: var(--wp-accent-strong);
  }
}

.tool-call-card__chevron {
  flex: 0 0 auto;
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.tool-call-card__tech {
  padding: 0.75rem 0.85rem 0.85rem;
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface-2);
}

.tool-call-card__tech-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}

.tool-call-card__tool-name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-family: var(--wp-font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-call-card__status-chip {
  flex: 0 0 auto;
  padding: 0.1rem 0.5rem;
  border-radius: var(--wp-r-pill);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  background: var(--wp-surface-3);
  color: var(--wp-text-muted);

  &--running,
  &--awaiting_confirmation,
  &--pending_confirmation {
    background: var(--wp-accent-soft);
    color: var(--wp-accent-strong);
  }

  &--success {
    background: var(--wp-success-soft, var(--wp-accent-soft));
    color: var(--wp-success);
  }

  &--error {
    background: var(--wp-danger-soft);
    color: var(--wp-danger);
  }

  &--pending {
    background: var(--wp-gold-soft);
    color: var(--wp-gold);
  }
}

.tool-call-card__spinner {
  color: var(--wp-accent);
}

.tool-call-card__detail-rows {
  margin: 0 0 0.75rem;
  display: grid;
  grid-template-columns: minmax(5.5rem, auto) 1fr;
  gap: 0.35rem 0.75rem;
}

.tool-call-card__detail-row {
  display: contents;
}

.tool-call-card__detail-label {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--wp-text-muted);
  align-self: baseline;
}

.tool-call-card__detail-value {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text);
  min-width: 0;
  word-break: break-word;
}

.tool-call-card__raw-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin: 0 0 0.5rem;
  padding: 0.25rem 0.5rem;
  border: 1px dashed var(--wp-border-strong);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: color var(--wp-dur) var(--wp-ease),
    border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    color: var(--wp-text);
    border-color: var(--wp-text-muted);
  }
}

.tool-call-card__raw {
  margin-top: 0.25rem;
}

.tool-call-card__section-title {
  margin: 0 0 0.35rem;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--wp-text-muted);
}

.tool-call-card__json {
  margin: 0 0 0.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-3);
  color: var(--wp-text);
  font-family: var(--wp-font-mono);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
