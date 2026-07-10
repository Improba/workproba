<template>
  <div class="message-list">
    <q-scroll-area ref="scrollAreaRef" class="message-list__scroller">
      <DynamicScroller
        v-if="messages.length"
        class="message-list__virtual"
        :items="messages"
        :min-item-size="72"
        key-field="id"
      >
        <template #default="{ item, active, index }">
          <DynamicScrollerItem
            :item="item"
            :active="active"
            :data-index="index"
            :size-dependencies="[
              item.content,
              item.toolCalls?.length,
              item.parts?.length,
              item.streaming,
              item.error?.code,
              item.pendingConfirmation?.confirmationId,
            ]"
          >
            <Message
              :message="item"
              :project-path="projectPath"
              :session-id="sessionId"
              :confirming="confirming"
              class="message-list__item"
              @open-file="(path) => emit('open-file', path)"
              @restored="(path) => emit('restored', path)"
              @confirm-approve="emit('confirm-approve')"
              @confirm-deny="emit('confirm-deny')"
            />
          </DynamicScrollerItem>
        </template>
      </DynamicScroller>

      <div v-else class="message-list__empty">
        <Lucide name="messages-square" size="lg" color="neutral-medium" />
        <p>Commencez la conversation. L'agent peut manipuler vos documents et exécuter des tâches pour vous.</p>
      </div>
    </q-scroll-area>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import {
  DynamicScroller,
  DynamicScrollerItem,
} from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import Message from '@components/chat/Message.vue';
import type { ChatMessage } from '#types';
import type { QScrollArea } from 'quasar';

defineProps<{
  messages: ChatMessage[];
  projectPath?: string | null;
  sessionId?: string | null;
  confirming?: boolean;
}>();

const emit = defineEmits<{
  'open-file': [path: string];
  restored: [path: string];
  'confirm-approve': [];
  'confirm-deny': [];
}>();

const scrollAreaRef = ref<QScrollArea | null>(null);

function getScrollTarget(): HTMLElement | null {
  return (
    scrollAreaRef.value?.$el?.querySelector('.q-scrollarea__container') ?? null
  );
}

defineExpose({
  scrollToBottom: () => {
    const target = getScrollTarget();
    if (!target) return;
    target.scrollTop = target.scrollHeight;
  },
  getScrollTarget,
});
</script>

<style scoped lang="scss">
.message-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.message-list__scroller {
  flex: 1;
  min-height: 0;
}

.message-list__virtual {
  max-width: 46rem;
  margin: 0 auto;
  padding: 1rem 1.25rem 1.5rem;
}

.message-list__item {
  // vue-virtual-scroller positionne les items en absolu et mesure la
  // border-box (margins ignorées) : on utilise padding-bottom pour créer
  // un gap réellement visible entre les messages.
  padding-bottom: 1rem;
}

.message-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.85rem;
  min-height: 240px;
  padding: 2rem 1.5rem;
  text-align: center;
  color: var(--wp-text-muted);

  p {
    margin: 0;
    max-width: 34rem;
    font-size: 1rem;
    line-height: 1.55;
  }
}
</style>
