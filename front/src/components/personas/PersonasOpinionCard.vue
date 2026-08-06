<template>
  <article
    class="personas-opinion-card"
    role="region"
    :aria-label="t('personas.opinion.cardLabel', { topic: card.question })"
  >
    <span
      class="wp-sr-only"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {{ liveStatusMessage }}
    </span>

    <header class="personas-opinion-card__header">
      <button
        type="button"
        class="personas-opinion-card__toggle"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <Lucide name="users" size="16" color="wp-gold" />
        <span class="personas-opinion-card__title">
          {{ t('personas.opinion.header', { topic: card.question }) }}
        </span>
        <Lucide
          name="chevron-down"
          size="14"
          color="text-muted"
          :class="expanded ? 'personas-opinion-card__chevron personas-opinion-card__chevron--up' : 'personas-opinion-card__chevron'"
        />
      </button>
      <span
        v-if="card.streaming && !card.error"
        class="personas-opinion-card__status"
        aria-hidden="true"
      >
        {{ t('common.inProgress') }}
      </span>
    </header>

    <div v-if="expanded" class="personas-opinion-card__body">
      <p
        v-if="card.error"
        class="personas-opinion-card__error"
        role="alert"
      >
        {{ t('personas.opinion.error') }}
      </p>

      <div
        v-else-if="card.streaming && !card.opinions.length"
        class="personas-opinion-card__preview"
        aria-hidden="true"
      >
        <span class="personas-opinion-card__preview-spinner" aria-hidden="true" />
        <span>{{ t('personas.opinion.analysing') }}</span>
      </div>

      <template v-else-if="!card.error">
        <section
          v-for="opinion in card.opinions"
          :key="opinion.personaId"
          class="personas-opinion-card__block"
        >
          <header class="personas-opinion-card__block-head">
            <PersonaAvatar :name="opinion.personaName" :color="opinion.avatarColor" :icon="opinion.avatarIcon" />
            <div class="personas-opinion-card__block-meta">
              <span class="personas-opinion-card__persona-name">{{ opinion.personaName }} :</span>
              <span v-if="opinion.personaRole" class="personas-opinion-card__role">
                {{ opinion.personaRole }}
              </span>
            </div>
          </header>
          <MessageTextPart
            v-if="opinion.content || opinion.streaming"
            class="personas-opinion-card__content"
            :content="opinion.content || (opinion.streaming ? t('personas.opinion.waiting') : '')"
            :streaming="!!opinion.streaming"
          />
          <p
            v-if="opinion.memoryCited && !opinion.memoryCitations?.length"
            class="personas-opinion-card__memory"
          >
            <Lucide name="brain" size="12" color="wp-violet" />
            <span>{{ t('personas.opinion.memoryCited') }}</span>
          </p>
          <MemoryCitationsBar
            v-else-if="opinion.memoryCitations?.length"
            class="personas-opinion-card__citations"
            :citations="opinion.memoryCitations"
            :expansion-key="`${card.id}-${opinion.personaId}`"
          />
        </section>

        <footer v-if="!card.streaming" class="personas-opinion-card__actions">
          <button type="button" class="personas-opinion-card__action" @click="emit('another')">
            {{ t('personas.opinion.another') }}
          </button>
          <button type="button" class="personas-opinion-card__action" @click="emit('toDiscussion')">
            {{ t('personas.opinion.toDiscussion') }}
          </button>
          <button
            v-if="showPublish"
            type="button"
            class="personas-opinion-card__action personas-opinion-card__action--publish"
            @click="emit('publish')"
          >
            {{ t('personas.publishToProject') }}
          </button>
        </footer>
      </template>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import PersonaAvatar from '@components/personas/PersonaAvatar.vue';
import MessageTextPart from '@components/chat/MessageTextPart.vue';
import MemoryCitationsBar from '@components/chat/MemoryCitationsBar.vue';
import type { PersonasOpinionCard } from '#types';

const props = defineProps<{
  card: PersonasOpinionCard;
  showPublish?: boolean;
}>();

const emit = defineEmits<{
  another: [];
  toDiscussion: [];
  publish: [];
}>();

const { t } = useI18n();
const expanded = ref(true);

const liveStatusMessage = computed(() => {
  if (props.card.error) {
    return t('personas.opinion.error');
  }
  if (props.card.streaming) {
    return t('personas.opinion.analysing');
  }
  return t('personas.opinion.header', { topic: props.card.question });
});
</script>

<style scoped lang="scss">
.personas-opinion-card {
  width: 100%;
  margin: var(--wp-space-2) 0;
  border: 1px solid color-mix(in srgb, var(--wp-gold) 40%, var(--wp-border));
  border-left: 3px solid var(--wp-gold);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  animation: personas-opinion-slide-in 240ms var(--wp-ease) both;
}

@keyframes personas-opinion-slide-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .personas-opinion-card {
    animation: none;
  }

  .personas-opinion-card__preview-spinner {
    animation: none;
  }

  .personas-opinion-card__chevron {
    transition: none;
  }
}

.personas-opinion-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3) var(--wp-space-3) 0;
}

.personas-opinion-card__toggle {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.personas-opinion-card__title {
  flex: 1;
  font-family: var(--wp-font-head);
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-opinion-card__chevron {
  transition: transform var(--wp-dur) var(--wp-ease);

  &--up {
    transform: rotate(180deg);
  }
}

.personas-opinion-card__status {
  font-size: var(--wp-fs-xs);
  color: var(--wp-gold);
  font-weight: 600;
}

.personas-opinion-card__body {
  padding: var(--wp-space-3);
}

.personas-opinion-card__error {
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-danger);
  background: color-mix(in srgb, var(--wp-danger) 8%, var(--wp-surface));
  border: 1px solid color-mix(in srgb, var(--wp-danger) 25%, transparent);
}

.personas-opinion-card__preview {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  font-style: italic;
}

.personas-opinion-card__preview-spinner {
  flex: 0 0 auto;
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 999px;
  border: 2px solid color-mix(in srgb, var(--wp-gold) 35%, transparent);
  border-top-color: var(--wp-gold);
  animation: personas-opinion-spin 0.7s linear infinite;
}

@keyframes personas-opinion-spin {
  to {
    transform: rotate(360deg);
  }
}

.personas-opinion-card__block {
  padding: var(--wp-space-3) 0;
  border-top: 1px solid var(--wp-border);

  &:first-child {
    border-top: none;
    padding-top: 0;
  }
}

.personas-opinion-card__block-head {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-2);
}

.personas-opinion-card__block-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.personas-opinion-card__persona-name {
  font-weight: 700;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.personas-opinion-card__role {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.personas-opinion-card__content {
  font-family: var(--wp-font-chat, var(--wp-font-ui));
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
  color: var(--wp-text);

  :deep(.chat-message__markdown) {
    font-family: inherit;
    font-size: inherit;
    line-height: inherit;
    color: inherit;
  }

  :deep(p) {
    margin: 0 0 0.5rem;
  }

  :deep(p:last-child) {
    margin-bottom: 0;
  }

  :deep(ul),
  :deep(ol) {
    margin: 0.25rem 0 0.5rem 1.1rem;
  }

  :deep(strong) {
    font-weight: 700;
  }
}

.personas-opinion-card__memory {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  margin: 0 0 var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-violet);
}

.personas-opinion-card__citations {
  margin: var(--wp-space-2) 0 0;
}

.personas-opinion-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--wp-space-2);
  margin-top: var(--wp-space-3);
  padding-top: var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
}

.personas-opinion-card__action {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid color-mix(in srgb, var(--wp-gold) 50%, var(--wp-border));
  border-radius: var(--wp-r-sm);
  background: var(--wp-gold-soft);
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:hover {
    filter: brightness(0.97);
  }
}
</style>
