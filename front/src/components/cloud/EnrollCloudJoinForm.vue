<template>
  <form class="enroll-cloud-form" @submit.prevent="emit('submit')">
    <div class="enroll-cloud-form__field">
      <label :for="joinTokenInputId">{{ t('cloud.invitationCode') }}</label>
      <input
        :id="joinTokenInputId"
        :value="joinToken"
        type="text"
        class="enroll-cloud-form__input"
        :disabled="disabled || submitting"
        autocomplete="off"
        @input="onJoinTokenInput"
      />
    </div>
    <div v-if="showUrlField" class="enroll-cloud-form__field">
      <label :for="baseUrlInputId">{{ t('cloud.joinUrlLabel') }}</label>
      <input
        :id="baseUrlInputId"
        :value="baseUrl"
        type="url"
        class="enroll-cloud-form__input"
        :placeholder="t('cloud.baseUrlPlaceholder')"
        :disabled="disabled || submitting"
        @input="onBaseUrlInput"
      />
    </div>
    <div v-if="showBearer" class="enroll-cloud-form__field">
      <label :for="bearerInputId">{{ t('cloud.bearerToken') }}</label>
      <input
        :id="bearerInputId"
        :value="bearerToken"
        type="password"
        class="enroll-cloud-form__input"
        :placeholder="t('cloud.bearerToken')"
        :disabled="disabled || submitting"
        @input="onBearerInput"
      />
    </div>
    <button
      type="submit"
      class="enroll-cloud-form__submit"
      :disabled="disabled || submitting || !canSubmit"
    >
      {{ submitting ? t('cloud.joining') : submitLabel }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const props = withDefaults(
  defineProps<{
    joinToken: string;
    baseUrl?: string;
    bearerToken?: string;
    showUrlField?: boolean;
    showBearer?: boolean;
    disabled?: boolean;
    submitting?: boolean;
    submitLabel?: string;
    joinTokenInputId?: string;
    baseUrlInputId?: string;
    bearerInputId?: string;
  }>(),
  {
    baseUrl: '',
    bearerToken: '',
    showUrlField: false,
    showBearer: false,
    disabled: false,
    submitting: false,
    submitLabel: '',
    joinTokenInputId: 'cloud-join-token',
    baseUrlInputId: 'cloud-join-url',
    bearerInputId: 'cloud-bearer-token',
  },
);

const emit = defineEmits<{
  'update:joinToken': [value: string];
  'update:baseUrl': [value: string];
  'update:bearerToken': [value: string];
  submit: [];
}>();

const { t } = useI18n();

const submitLabel = computed(
  () => props.submitLabel || t('cloud.join'),
);

const canSubmit = computed(() => {
  if (props.showBearer) {
    return Boolean(props.baseUrl.trim() && props.bearerToken.trim());
  }
  if (props.showUrlField && !props.baseUrl.trim()) return false;
  return Boolean(props.joinToken.trim());
});

function onJoinTokenInput(event: Event): void {
  emit('update:joinToken', (event.target as HTMLInputElement).value);
}

function onBaseUrlInput(event: Event): void {
  emit('update:baseUrl', (event.target as HTMLInputElement).value);
}

function onBearerInput(event: Event): void {
  emit('update:bearerToken', (event.target as HTMLInputElement).value);
}
</script>

<style scoped lang="scss">
.enroll-cloud-form {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.enroll-cloud-form__field {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-1);
  width: 100%;

  label {
    font-size: var(--wp-fs-xs);
    color: var(--wp-text-muted);
    font-weight: 500;
  }
}

.enroll-cloud-form__input {
  width: 100%;
  box-sizing: border-box;
  min-height: 38px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
}

.enroll-cloud-form__submit {
  align-self: stretch;
  min-height: 38px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-accent);
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
  color: var(--wp-accent);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}
</style>
