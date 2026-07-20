<template>
  <q-dialog :model-value="modelValue" @update:model-value="onOpenChange">
    <div class="enroll-cloud-modal">
      <header class="enroll-cloud-modal__head">
        <div>
          <h2 class="enroll-cloud-modal__title">{{ t('cloud.joinTitle') }}</h2>
          <p class="enroll-cloud-modal__hint">{{ t('cloud.joinHint') }}</p>
        </div>
        <button
          type="button"
          class="enroll-cloud-modal__close"
          :aria-label="t('common.cancel')"
          :disabled="submitting"
          @click="onCancel"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p v-if="displayError" class="enroll-cloud-modal__error" role="alert">
        {{ displayError }}
      </p>

      <EnrollCloudJoinForm
        v-model:join-token="joinTokenDraft"
        v-model:base-url="baseUrlDraft"
        v-model:bearer-token="bearerTokenDraft"
        :show-url-field="showCloudUrlField"
        :show-bearer="showBearerField"
        :disabled="cloudLoading"
        :submitting="submitting"
        :submit-label="t('settings.engine.linkDevice')"
        @submit="onSubmit"
      />

      <footer class="enroll-cloud-modal__foot">
        <button
          type="button"
          class="enroll-cloud-modal__cancel"
          :disabled="submitting"
          @click="onCancel"
        >
          {{ t('common.cancel') }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useCloud } from '@composables/useCloud';
import EnrollCloudJoinForm from '@components/cloud/EnrollCloudJoinForm.vue';

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    /** Affiche le champ bearer (usage technique / avancé). */
    technical?: boolean;
  }>(),
  {
    technical: false,
  },
);

const emit = defineEmits<{
  'update:modelValue': [open: boolean];
  enrolled: [];
  success: [];
  cancel: [];
}>();

const { t } = useI18n();
const { settings } = useAppSettings();
const {
  status,
  loading: cloudLoading,
  loadError,
  enroll,
  refreshStatus,
  refreshQuota,
} = useCloud();

const joinTokenDraft = ref('');
const baseUrlDraft = ref('');
const bearerTokenDraft = ref('');
const submitting = ref(false);

const presetCloudUrl = computed(() => settings.value.cloudEndpoint?.trim() ?? '');
const showCloudUrlField = computed(
  () => !status.value?.base_url && !presetCloudUrl.value,
);
const showBearerField = computed(() => props.technical);

const displayError = computed(() => {
  const raw = loadError.value?.trim();
  if (!raw) return '';
  if (/^[a-z][a-z0-9_]*$/.test(raw)) return t('cloud.joinFailed');
  return raw;
});

function resolveBaseUrl(): string {
  return (
    baseUrlDraft.value.trim()
    || status.value?.base_url?.trim()
    || presetCloudUrl.value
    || ''
  );
}

function onOpenChange(open: boolean): void {
  emit('update:modelValue', open);
  if (!open) {
    emit('cancel');
  }
}

function onCancel(): void {
  if (submitting.value) return;
  emit('update:modelValue', false);
  emit('cancel');
}

async function onSubmit(): Promise<void> {
  const baseUrl = resolveBaseUrl();
  if (!baseUrl) {
    Notify.create({
      message: t('cloud.baseUrlRequired'),
      color: 'negative',
    });
    return;
  }

  submitting.value = true;
  try {
    const ok = await enroll({
      baseUrl,
      joinToken: joinTokenDraft.value,
      bearerToken: showBearerField.value ? bearerTokenDraft.value : undefined,
    });
    if (!ok) {
      Notify.create({
        message: displayError.value || t('cloud.joinFailed'),
        color: 'negative',
      });
      return;
    }

    joinTokenDraft.value = '';
    bearerTokenDraft.value = '';
    await refreshStatus();
    await refreshQuota();

    Notify.create({
      message: t('cloud.joinSuccess'),
      color: 'positive',
      timeout: 2000,
    });

    emit('enrolled');
    emit('success');
    emit('update:modelValue', false);
  } finally {
    submitting.value = false;
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    baseUrlDraft.value =
      status.value?.base_url?.trim()
      || presetCloudUrl.value
      || 'http://localhost:3336';
    joinTokenDraft.value = '';
    bearerTokenDraft.value = '';
  },
);

watch(status, (next) => {
  if (next?.base_url) {
    baseUrlDraft.value = next.base_url;
  } else if (presetCloudUrl.value) {
    baseUrlDraft.value = presetCloudUrl.value;
  }
});
</script>

<style scoped lang="scss">
.enroll-cloud-modal {
  width: min(480px, 92vw);
  padding: var(--wp-space-4);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.enroll-cloud-modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--wp-space-2);
}

.enroll-cloud-modal__title {
  margin: 0;
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.enroll-cloud-modal__hint {
  margin: 4px 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.enroll-cloud-modal__close {
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  padding: 4px;
}

.enroll-cloud-modal__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.enroll-cloud-modal__foot {
  display: flex;
  justify-content: flex-end;
}

.enroll-cloud-modal__cancel {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  text-decoration: underline;
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}
</style>
