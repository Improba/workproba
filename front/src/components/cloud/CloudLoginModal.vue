<template>
  <q-dialog :model-value="modelValue" @update:model-value="onOpenChange">
    <div class="cloud-login-modal">
      <header class="cloud-login-modal__head">
        <div>
          <h2 class="cloud-login-modal__title">{{ t('cloud.loginTitle') }}</h2>
          <p class="cloud-login-modal__hint">{{ t('cloud.loginHint') }}</p>
        </div>
        <button
          type="button"
          class="cloud-login-modal__close"
          :aria-label="t('common.cancel')"
          :disabled="submitting"
          @click="onCancel"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p v-if="displayError" class="cloud-login-modal__error" role="alert">
        {{ displayError }}
      </p>

      <form class="cloud-login-form" @submit.prevent="onSubmit">
        <div class="cloud-login-form__field">
          <label for="cloud-login-username">{{ t('cloud.loginUsername') }}</label>
          <input
            id="cloud-login-username"
            v-model="usernameDraft"
            type="text"
            class="cloud-login-form__input"
            :placeholder="t('cloud.loginUsernamePlaceholder')"
            :disabled="cloudLoading || submitting"
            autocomplete="username"
          />
        </div>
        <div class="cloud-login-form__field">
          <label for="cloud-login-password">{{ t('cloud.loginPassword') }}</label>
          <input
            id="cloud-login-password"
            v-model="passwordDraft"
            type="password"
            class="cloud-login-form__input"
            :disabled="cloudLoading || submitting"
            autocomplete="current-password"
          />
        </div>
        <div v-if="showCloudUrlField" class="cloud-login-form__field">
          <label for="cloud-login-url">{{ t('cloud.joinUrlLabel') }}</label>
          <input
            id="cloud-login-url"
            v-model="baseUrlDraft"
            type="url"
            class="cloud-login-form__input"
            :placeholder="t('cloud.baseUrlPlaceholder')"
            :disabled="cloudLoading || submitting"
          />
        </div>
        <button
          type="submit"
          class="cloud-login-form__submit"
          :disabled="cloudLoading || submitting || !canSubmit"
        >
          {{ submitting ? t('cloud.loggingIn') : t('cloud.loginSubmit') }}
        </button>
      </form>

      <button
        type="button"
        class="cloud-login-modal__invitation"
        :disabled="submitting"
        @click="onOpenInvitation"
      >
        {{ t('cloud.haveInvitationCode') }}
      </button>

      <footer class="cloud-login-modal__foot">
        <button
          type="button"
          class="cloud-login-modal__cancel"
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
import { useUserProfile } from '@composables/useUserProfile';
import {
  CloudDesktopAuthError,
  displayNameFromUsername,
  loginDesktopCloud,
} from '@services/cloudDesktopAuth';

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [open: boolean];
  enrolled: [];
  success: [];
  cancel: [];
  'open-invitation': [];
}>();

const { t, te } = useI18n();
const { settings } = useAppSettings();
const { profile, save: saveProfile } = useUserProfile();
const {
  status,
  loading: cloudLoading,
  loadError,
  enroll,
  refreshStatus,
  refreshQuota,
} = useCloud();

const usernameDraft = ref('');
const passwordDraft = ref('');
const baseUrlDraft = ref('');
const submitting = ref(false);
const authError = ref<string | null>(null);

const presetCloudUrl = computed(() => settings.value.cloudEndpoint?.trim() ?? '');
const showCloudUrlField = computed(
  () => !status.value?.base_url && !presetCloudUrl.value,
);

const canSubmit = computed(
  () => Boolean(usernameDraft.value.trim() && passwordDraft.value),
);

const displayError = computed(() => {
  const raw = authError.value?.trim() || loadError.value?.trim();
  if (!raw) return '';
  return te(raw) ? t(raw) : raw;
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

function onOpenInvitation(): void {
  if (submitting.value) return;
  emit('update:modelValue', false);
  emit('open-invitation');
}

function maybeSaveProfileFromLogin(username: string): void {
  if (profile.value.name.trim()) return;
  const name = displayNameFromUsername(username);
  if (!name) return;
  const orgLabel = status.value?.org_label?.trim();
  saveProfile({
    name,
    ...(orgLabel ? { organisation: orgLabel } : {}),
  });
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

  const username = usernameDraft.value.trim();
  if (!username || !passwordDraft.value) {
    Notify.create({
      message: t('cloud.loginCredentialsRequired'),
      color: 'negative',
    });
    return;
  }

  submitting.value = true;
  authError.value = null;
  try {
    const { token } = await loginDesktopCloud({
      baseUrl,
      username,
      password: passwordDraft.value,
    });

    const ok = await enroll({ baseUrl, bearerToken: token });
    if (!ok) {
      Notify.create({
        message: displayError.value || t('cloud.loginFailed'),
        color: 'negative',
      });
      return;
    }

    passwordDraft.value = '';
    await refreshStatus();
    await refreshQuota();
    maybeSaveProfileFromLogin(username);

    Notify.create({
      message: t('cloud.loginSuccess'),
      color: 'positive',
      timeout: 2000,
    });

    emit('enrolled');
    emit('success');
    emit('update:modelValue', false);
  } catch (err) {
    if (err instanceof CloudDesktopAuthError) {
      authError.value = err.message;
      Notify.create({
        message: t(err.message),
        color: 'negative',
      });
      return;
    }
    authError.value = 'cloud.loginFailed';
    Notify.create({
      message: t('cloud.loginFailed'),
      color: 'negative',
    });
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
    usernameDraft.value = '';
    passwordDraft.value = '';
    authError.value = null;
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
.cloud-login-modal {
  width: min(480px, 92vw);
  padding: var(--wp-space-4);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.cloud-login-modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--wp-space-2);
}

.cloud-login-modal__title {
  margin: 0;
  font-size: var(--wp-fs-base);
  font-weight: 700;
  color: var(--wp-text);
}

.cloud-login-modal__hint {
  margin: 4px 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.cloud-login-modal__close {
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  padding: 4px;
}

.cloud-login-modal__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.cloud-login-form {
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.cloud-login-form__field {
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

.cloud-login-form__input {
  width: 100%;
  box-sizing: border-box;
  min-height: 38px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
}

.cloud-login-form__submit {
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

.cloud-login-modal__invitation {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  text-decoration: underline;
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.cloud-login-modal__foot {
  display: flex;
  justify-content: flex-end;
}

.cloud-login-modal__cancel {
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
