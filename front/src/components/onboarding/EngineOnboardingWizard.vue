<template>
  <div class="engine-onboarding-wizard">
    <header class="engine-onboarding-wizard__head">
      <button
        v-if="screen !== 'choices'"
        type="button"
        class="engine-onboarding-wizard__back"
        @click="onBack"
      >
        <Lucide name="arrow-left" size="16" color="text-muted" />
        {{ t('home.engineOnboarding.back') }}
      </button>
      <h2 class="engine-onboarding-wizard__title">{{ screenTitle }}</h2>
      <p v-if="screenLead" class="engine-onboarding-wizard__lead">{{ screenLead }}</p>
    </header>

    <section v-if="screen === 'choices'" class="engine-onboarding-wizard__choices">
      <button
        type="button"
        class="engine-onboarding-wizard__choice"
        data-testid="engine-onboarding-login"
        @click="onLoginCloud"
      >
        <span class="engine-onboarding-wizard__choice-icon" aria-hidden="true">
          <Lucide name="log-in" size="22" color="wp-accent" />
        </span>
        <span class="engine-onboarding-wizard__choice-body">
          <span class="engine-onboarding-wizard__choice-title">
            {{ t('home.engineOnboarding.loginCloud') }}
          </span>
          <span class="engine-onboarding-wizard__choice-hint">
            {{ t('home.engineOnboarding.loginCloudHint') }}
          </span>
        </span>
        <Lucide name="chevron-right" size="18" color="text-faint" />
      </button>

      <button
        type="button"
        class="engine-onboarding-wizard__choice"
        data-testid="engine-onboarding-register"
        @click="onRegisterCloud"
      >
        <span class="engine-onboarding-wizard__choice-icon" aria-hidden="true">
          <Lucide name="user-plus" size="22" color="wp-accent" />
        </span>
        <span class="engine-onboarding-wizard__choice-body">
          <span class="engine-onboarding-wizard__choice-title">
            {{ t('home.engineOnboarding.registerCloud') }}
          </span>
          <span class="engine-onboarding-wizard__choice-hint">
            {{ t('home.engineOnboarding.registerCloudHint') }}
          </span>
        </span>
        <Lucide name="chevron-right" size="18" color="text-faint" />
      </button>

      <button
        type="button"
        class="engine-onboarding-wizard__choice"
        data-testid="engine-onboarding-api-key"
        @click="screen = 'api-key'"
      >
        <span class="engine-onboarding-wizard__choice-icon" aria-hidden="true">
          <Lucide name="key-round" size="22" color="wp-accent" />
        </span>
        <span class="engine-onboarding-wizard__choice-body">
          <span class="engine-onboarding-wizard__choice-title">
            {{ t('home.engineOnboarding.useAccessKey') }}
          </span>
          <span class="engine-onboarding-wizard__choice-hint">
            {{ t('home.engineOnboarding.useAccessKeyHint') }}
          </span>
        </span>
        <Lucide name="chevron-right" size="18" color="text-faint" />
      </button>
    </section>

    <section v-else-if="screen === 'api-key'" class="engine-onboarding-wizard__choices">
      <button
        type="button"
        class="engine-onboarding-wizard__choice"
        data-testid="engine-onboarding-mistral"
        @click="screen = 'mistral'"
      >
        <span class="engine-onboarding-wizard__choice-icon" aria-hidden="true">
          <Lucide name="sparkles" size="22" color="wp-accent" />
        </span>
        <span class="engine-onboarding-wizard__choice-body">
          <span class="engine-onboarding-wizard__choice-title">
            {{ t('settings.engine.mistralName') }}
          </span>
          <span class="engine-onboarding-wizard__choice-hint">
            {{ t('home.engineOnboarding.mistralLead') }}
          </span>
        </span>
        <Lucide name="chevron-right" size="18" color="text-faint" />
      </button>

      <button
        type="button"
        class="engine-onboarding-wizard__choice"
        data-testid="engine-onboarding-manual"
        @click="screen = 'manual'"
      >
        <span class="engine-onboarding-wizard__choice-icon" aria-hidden="true">
          <Lucide name="settings-2" size="22" color="wp-accent" />
        </span>
        <span class="engine-onboarding-wizard__choice-body">
          <span class="engine-onboarding-wizard__choice-title">
            {{ t('settings.engine.manualName') }}
          </span>
          <span class="engine-onboarding-wizard__choice-hint">
            {{ t('home.engineOnboarding.manualLead') }}
          </span>
        </span>
        <Lucide name="chevron-right" size="18" color="text-faint" />
      </button>
    </section>

    <section v-else-if="screen === 'mistral'" class="engine-onboarding-wizard__form">
      <q-input
        ref="accessKeyInputRef"
        v-model="mistralKey"
        :label="t('settings.engine.accessKey')"
        outlined
        dense
        :type="showKey ? 'text' : 'password'"
        class="engine-onboarding-wizard__field"
      >
        <template #append>
          <button type="button" class="reveal-btn" @click="showKey = !showKey">
            <Lucide :name="showKey ? 'eye-off' : 'eye'" size="16" color="text-faint" />
          </button>
        </template>
      </q-input>
      <p class="engine-onboarding-wizard__hint">{{ t('settings.engine.accessKeyHint') }}</p>
      <button
        type="button"
        class="engine-onboarding-wizard__submit"
        data-testid="engine-onboarding-mistral-submit"
        :disabled="activating || !mistralKey.trim()"
        @click="onActivateMistral"
      >
        {{ activating ? t('common.inProgress') : t('common.continue') }}
      </button>
    </section>

    <section v-else-if="screen === 'manual'" class="engine-onboarding-wizard__form">
      <ManualOpenAiCompatForm @activated="onManualActivated" />
    </section>

    <section v-else-if="screen === 'cloud-followup'" class="engine-onboarding-wizard__cloud">
      <p class="engine-onboarding-wizard__cloud-lead">
        {{ cloudFollowupLead }}
      </p>
      <div class="engine-onboarding-wizard__cloud-actions">
        <button
          type="button"
          class="engine-onboarding-wizard__secondary"
          @click="reopenCloudPage"
        >
          <Lucide name="external-link" size="14" color="text" />
          {{ cloudReopenLabel }}
        </button>
        <button
          type="button"
          class="engine-onboarding-wizard__submit"
          data-testid="engine-onboarding-paste-invitation"
          @click="enrollModalOpen = true"
        >
          {{ t('home.engineOnboarding.pasteInvitation') }}
        </button>
      </div>
    </section>

    <CloudLoginModal
      v-model="loginModalOpen"
      @enrolled="onCloudEnrolled"
      @open-invitation="onOpenInvitationFromLogin"
    />

    <EnrollCloudModal
      v-model="enrollModalOpen"
      @enrolled="onCloudEnrolled"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import type { QInput } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import ManualOpenAiCompatForm from '@components/settings/ManualOpenAiCompatForm.vue';
import { useAppSettings } from '@composables/useAppSettings';
import { useUserProfile } from '@composables/useUserProfile';
import { useCloud } from '@composables/useCloud';
import { openExternalUrl } from '@composables/useDesktop';
import { ProviderSetNotReadyError } from '@utils/providerSetErrors';
import { chatErrorMessageForReadiness } from '@utils/providerSetNotify';
import {
  applyAccessKeyToSet,
  WORKPROBA_CLOUD_BUILTIN_SET,
} from '@utils/providerSets';
import {
  cloudAuthLoginUrl,
  cloudAuthRegisterUrl,
} from '@utils/cloudWebUrls';

type WizardScreen = 'choices' | 'api-key' | 'mistral' | 'manual' | 'cloud-followup';
type CloudFlow = 'login' | 'register';

const emit = defineEmits<{
  complete: [];
}>();

const { t } = useI18n();
const {
  sets,
  load,
  setActiveSet,
  updateSet,
  setOnboardingDone,
} = useAppSettings();
const {
  status,
  providerReadiness,
  init: initCloud,
  refreshQuota,
} = useCloud();
const { profile, save: saveProfile } = useUserProfile();

const screen = ref<WizardScreen>('choices');
const cloudFlow = ref<CloudFlow>('login');
const mistralKey = ref('');
const showKey = ref(false);
const activating = ref(false);
const loginModalOpen = ref(false);
const enrollModalOpen = ref(false);
const accessKeyInputRef = ref<InstanceType<typeof QInput> | null>(null);

const screenTitle = computed(() => {
  switch (screen.value) {
    case 'choices':
      return t('home.engineOnboarding.title');
    case 'api-key':
      return t('home.engineOnboarding.apiKeyTitle');
    case 'mistral':
      return t('settings.engine.mistralName');
    case 'manual':
      return t('settings.engine.manualTitle');
    case 'cloud-followup':
      return t('home.engineOnboarding.cloudFollowupTitle');
    default:
      return '';
  }
});

const screenLead = computed(() => {
  switch (screen.value) {
    case 'choices':
      return t('home.engineOnboarding.lead');
    case 'api-key':
      return t('home.engineOnboarding.apiKeyLead');
    default:
      return '';
  }
});

const cloudFollowupLead = computed(() =>
  cloudFlow.value === 'login'
    ? t('home.engineOnboarding.cloudFollowupLoginLead')
    : t('home.engineOnboarding.cloudFollowupRegisterLead'),
);

const cloudReopenLabel = computed(() =>
  cloudFlow.value === 'login'
    ? t('home.engineOnboarding.reopenLogin')
    : t('home.engineOnboarding.reopenRegister'),
);

function onBack(): void {
  switch (screen.value) {
    case 'api-key':
    case 'cloud-followup':
      screen.value = 'choices';
      break;
    case 'mistral':
    case 'manual':
      screen.value = 'api-key';
      break;
    default:
      screen.value = 'choices';
  }
}

async function openCloudAuth(flow: CloudFlow): Promise<void> {
  cloudFlow.value = flow;
  const url = flow === 'login' ? cloudAuthLoginUrl() : cloudAuthRegisterUrl();
  await openExternalUrl(url);
  screen.value = 'cloud-followup';
}

function onLoginCloud(): void {
  loginModalOpen.value = true;
}

function onOpenInvitationFromLogin(): void {
  enrollModalOpen.value = true;
}

function onRegisterCloud(): void {
  void openCloudAuth('register');
}

function reopenCloudPage(): void {
  const url = cloudFlow.value === 'login'
    ? cloudAuthLoginUrl()
    : cloudAuthRegisterUrl();
  void openExternalUrl(url);
}

async function finishOnboarding(): Promise<void> {
  await setOnboardingDone(true);
  emit('complete');
}

async function activateSetId(id: string): Promise<boolean> {
  activating.value = true;
  try {
    await setActiveSet(id, { cloud: providerReadiness.value });
    await finishOnboarding();
    return true;
  } catch (err) {
    if (err instanceof ProviderSetNotReadyError) {
      Notify.create({
        message: chatErrorMessageForReadiness(err.reason),
        color: 'warning',
      });
      if (err.reason === 'missing_api_key' && id === 'mistral-default') {
        await nextTick();
        accessKeyInputRef.value?.focus();
      }
      return false;
    }
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.saveFailed'),
      color: 'negative',
    });
    return false;
  } finally {
    activating.value = false;
  }
}

async function onActivateMistral(): Promise<void> {
  const key = mistralKey.value.trim();
  if (!key) {
    Notify.create({
      message: t('errors.apiKeyMissing'),
      color: 'warning',
    });
    await nextTick();
    accessKeyInputRef.value?.focus();
    return;
  }

  const mistralSet = sets.value.find((set) => set.id === 'mistral-default') ?? null;
  if (mistralSet && key !== (mistralSet.chat.apiKey ?? '')) {
    try {
      await updateSet(applyAccessKeyToSet(mistralSet, key));
    } catch (err) {
      Notify.create({
        message: err instanceof Error ? err.message : t('settings.saveFailed'),
        color: 'negative',
      });
      return;
    }
  }

  await activateSetId('mistral-default');
}

async function onManualActivated(): Promise<void> {
  await finishOnboarding();
}

async function onCloudEnrolled(): Promise<void> {
  await refreshQuota();
  const orgLabel = status.value?.org_label?.trim();
  if (orgLabel && !profile.value.organisation.trim()) {
    saveProfile({ organisation: orgLabel });
  }
  await activateSetId(WORKPROBA_CLOUD_BUILTIN_SET.id);
}

onMounted(async () => {
  await load();
  await initCloud();
});
</script>

<style scoped lang="scss">
.engine-onboarding-wizard {
  width: min(32rem, 92vw);
  padding: 1.75rem;
  border-radius: var(--wp-r-lg);
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.engine-onboarding-wizard__head {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.engine-onboarding-wizard__back {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:hover {
    color: var(--wp-text);
  }
}

.engine-onboarding-wizard__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-lg);
  font-weight: 700;
  color: var(--wp-text);
  text-align: center;
}

.engine-onboarding-wizard__lead {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  text-align: center;
}

.engine-onboarding-wizard__choices {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.engine-onboarding-wizard__choice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.85rem;
  width: 100%;
  padding: 0.9rem 1rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition:
    border-color var(--wp-dur) var(--wp-ease),
    background var(--wp-dur) var(--wp-ease);

  &:hover,
  &:focus-visible {
    border-color: var(--wp-accent);
    background: var(--wp-accent-soft);
    outline: none;
  }
}

.engine-onboarding-wizard__choice-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
}

.engine-onboarding-wizard__choice-body {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.engine-onboarding-wizard__choice-title {
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.engine-onboarding-wizard__choice-hint {
  font-size: var(--wp-fs-xs);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
}

.engine-onboarding-wizard__form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.engine-onboarding-wizard__field {
  width: 100%;
}

.engine-onboarding-wizard__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.engine-onboarding-wizard__cloud {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.engine-onboarding-wizard__cloud-lead {
  margin: 0;
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-normal);
  color: var(--wp-text-muted);
  text-align: center;
}

.engine-onboarding-wizard__cloud-actions {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.engine-onboarding-wizard__submit {
  min-height: 2.5rem;
  padding: 0 1.1rem;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-accent);
  color: var(--wp-canard);
  font-family: var(--wp-font-ui);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--wp-accent-strong);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.engine-onboarding-wizard__secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  min-height: 2.25rem;
  padding: 0 0.85rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.reveal-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  padding: 2px;
}
</style>
