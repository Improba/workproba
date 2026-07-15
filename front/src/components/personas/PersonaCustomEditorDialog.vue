<template>
  <q-dialog :model-value="open" @update:model-value="emit('update:open', $event)">
    <form class="persona-editor" @submit.prevent="onSubmit">
      <h3 class="persona-editor__title">
        {{ editing ? t('personas.personaEditor.editTitle') : t('personas.personaEditor.createTitle') }}
      </h3>

      <label class="persona-editor__field">
        <span>{{ t('personas.personaEditor.nameLabel') }}</span>
        <input v-model="name" type="text" required maxlength="80" />
      </label>

      <label class="persona-editor__field">
        <span>{{ t('personas.personaEditor.roleLabel') }}</span>
        <input v-model="role" type="text" required maxlength="120" />
      </label>

      <label class="persona-editor__field">
        <span>{{ t('personas.personaEditor.promptLabel') }}</span>
        <textarea v-model="systemPrompt" rows="6" required maxlength="4000" />
      </label>

      <footer class="persona-editor__foot">
        <button type="button" @click="emit('update:open', false)">
          {{ t('common.cancel') }}
        </button>
        <button type="submit" class="persona-editor__save" :disabled="!canSave">
          {{ t('common.save') }}
        </button>
      </footer>
    </form>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import type { PersonaInfo } from '@services/aiSidecar';

const props = defineProps<{
  open: boolean;
  persona?: PersonaInfo | null;
}>();

const emit = defineEmits<{
  'update:open': [value: boolean];
  save: [payload: { name: string; role: string; systemPrompt: string; id?: string }];
}>();

const { t } = useI18n();

const name = ref('');
const role = ref('');
const systemPrompt = ref('');

const editing = computed(() => Boolean(props.persona?.id));

const canSave = computed(
  () =>
    name.value.trim().length > 0 &&
    role.value.trim().length > 0 &&
    systemPrompt.value.trim().length > 0,
);

watch(
  () => [props.open, props.persona] as const,
  ([isOpen, persona]) => {
    if (!isOpen) return;
    name.value = persona?.name ?? '';
    role.value = persona?.role ?? '';
    systemPrompt.value = persona?.system_prompt ?? '';
  },
  { immediate: true },
);

function onSubmit(): void {
  if (!canSave.value) return;
  emit('save', {
    id: props.persona?.id,
    name: name.value.trim(),
    role: role.value.trim(),
    systemPrompt: systemPrompt.value.trim(),
  });
}
</script>

<style scoped lang="scss">
.persona-editor {
  width: min(28rem, 92vw);
  padding: var(--wp-space-4);
  background: var(--wp-surface);
  border-radius: var(--wp-r-md);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.persona-editor__title {
  margin: 0;
  font-size: var(--wp-fs-base);
  font-weight: 600;
}

.persona-editor__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  font-size: var(--wp-fs-sm);

  input,
  textarea {
    padding: var(--wp-space-2);
    border: 1px solid var(--wp-border);
    border-radius: var(--wp-r-sm);
    background: var(--wp-surface-2);
    color: var(--wp-text);
    font: inherit;
  }
}

.persona-editor__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--wp-space-2);
}

.persona-editor__save {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-gold);
  color: var(--wp-text);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
