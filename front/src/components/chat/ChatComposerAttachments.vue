<template>
  <div v-if="attachments.length" class="chat-attachments">
    <TransitionGroup name="chat-attachments">
      <div
        v-for="att in attachments"
        :key="att.id"
        class="chat-attachments__chip"
        :class="{
          'chat-attachments__chip--error': att.status === 'error',
          'chat-attachments__chip--reading': att.status === 'reading',
        }"
        :title="att.error || att.fileName"
      >
        <div class="chat-attachments__thumb">
          <img
            v-if="att.kind === 'image' && att.previewUrl"
            :src="att.previewUrl"
            :alt="att.fileName"
            class="chat-attachments__img"
          />
          <Lucide v-else :name="iconFor(att)" size="16" color="wp-text-muted" />
        </div>
        <div class="chat-attachments__meta">
          <span class="chat-attachments__name">{{ att.fileName }}</span>
          <span class="chat-attachments__sub">
            <template v-if="att.status === 'reading'">{{ t('chat.composerReading') }}</template>
            <template v-else-if="att.status === 'error'">{{
              att.error
            }}</template>
            <template v-else>{{ formatSize(att.sizeBytes) }}</template>
          </span>
        </div>
        <button
          type="button"
          class="chat-attachments__remove"
          :aria-label="t('chat.attachment.removeAria', { name: att.fileName })"
          @click="emit('remove', att.id)"
        >
          <Lucide name="x" size="14" color="wp-text-muted" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import type { ChatAttachment } from '#types';

const { t } = useI18n();

defineProps<{
  attachments: ChatAttachment[];
}>();

const emit = defineEmits<{
  remove: [id: string];
}>();

function iconFor(att: ChatAttachment): string {
  if (att.kind === 'image') return 'image';
  const ext = att.fileName.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return 'file-text';
  if (ext === 'docx' || ext === 'doc') return 'file-text';
  if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') return 'table';
  if (ext === 'pptx') return 'presentation';
  return 'file';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}
</script>

<style scoped lang="scss">
.chat-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.2rem 0;
}

.chat-attachments__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  max-width: 14rem;
  padding: 0.25rem 0.35rem 0.25rem 0.3rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  transition:
    border-color var(--wp-dur) var(--wp-ease),
    background var(--wp-dur) var(--wp-ease);

  &--error {
    border-color: var(--wp-danger);
    background: var(--wp-danger-soft);
  }

  &--reading {
    opacity: 0.85;
  }
}

.chat-attachments__thumb {
  flex: 0 0 auto;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.chat-attachments__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-attachments__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.chat-attachments__name {
  font-size: 0.75rem;
  color: var(--wp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-attachments__sub {
  font-size: 0.65rem;
  color: var(--wp-text-faint);

  .chat-attachments__chip--error & {
    color: var(--wp-danger);
  }
}

.chat-attachments__remove {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.1rem;
  border-radius: var(--wp-r-sm);
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.chat-attachments-enter-active,
.chat-attachments-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}

.chat-attachments-enter-from,
.chat-attachments-leave-to {
  opacity: 0;
  transform: scale(0.9);
}
</style>
