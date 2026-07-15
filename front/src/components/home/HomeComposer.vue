<template>
  <div class="home-composer">
    <form class="home-composer__form" @submit.prevent="submit">
      <label class="home-composer__label" for="home-composer-input">
        {{ t('home.composerLabel') }}
      </label>
      <div class="home-composer__row">
        <textarea
          id="home-composer-input"
          ref="inputRef"
          v-model="draft"
          class="home-composer__input"
          rows="3"
          :placeholder="t('home.composerPlaceholder')"
          :disabled="disabled"
          @keydown.enter.ctrl.prevent="submit"
          @keydown.enter.meta.prevent="submit"
        />
        <button
          type="submit"
          class="home-composer__send"
          :disabled="disabled || !draft.trim()"
          :aria-label="t('chat.send')"
        >
          <Lucide name="arrow-up" size="18" color="wp-canard" />
        </button>
      </div>
    </form>
    <StartPrompts class="home-composer__prompts" variant="chips" @select="onChipSelect" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import StartPrompts from '@components/chat/StartPrompts.vue';

defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits<{
  submit: [text: string];
}>();

const { t } = useI18n();
const draft = ref('');
const inputRef = ref<HTMLTextAreaElement | null>(null);

function submit(): void {
  const text = draft.value.trim();
  if (!text) return;
  emit('submit', text);
  draft.value = '';
}

function onChipSelect(prompt: string): void {
  emit('submit', prompt);
}

defineExpose({
  focus: () => inputRef.value?.focus(),
});
</script>

<style scoped lang="scss">
.home-composer {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
  max-width: 42rem;
  margin: 0 auto;
}

.home-composer__label {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.home-composer__form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.home-composer__row {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding: 0.65rem 0.65rem 0.65rem 0.85rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  box-shadow: var(--wp-shadow-1);
  transition: border-color var(--wp-dur) var(--wp-ease), box-shadow var(--wp-dur) var(--wp-ease);

  &:focus-within {
    border-color: var(--wp-accent);
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }
}

.home-composer__input {
  flex: 1;
  min-width: 0;
  min-height: 4.5rem;
  max-height: 12rem;
  resize: vertical;
  border: none;
  background: transparent;
  color: var(--wp-text);
  font-family: var(--wp-font-chat);
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-normal);

  &:focus {
    outline: none;
  }

  &::placeholder {
    color: var(--wp-text-faint);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.home-composer__send {
  flex: none;
  width: 2.25rem;
  height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent);
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.home-composer__prompts {
  align-self: center;
}
</style>
