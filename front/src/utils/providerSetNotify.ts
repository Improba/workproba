import { Notify } from 'quasar';
import type { ProviderSet } from '@composables/useDesktop.types';
import { t } from '@utils/i18nT';
import {
  validateProviderSetChatReady,
  validateProviderSetEmbeddingsReady,
} from '@utils/providerSetValidation';

function notifyIssue(reason: 'no_set' | 'missing_api_key'): void {
  const message =
    reason === 'missing_api_key'
      ? t('errors.apiKeyMissing')
      : t('chat.page.noModelConfigured');
  Notify.create({
    message,
    classes: 'bg-warning text-neutral-lowest',
    timeout: 6000,
  });
}

/** Retourne false et notifie l'utilisateur si le set n'est pas prêt pour le chat. */
export function ensureProviderSetChatReady(set: ProviderSet | null): set is ProviderSet {
  const check = validateProviderSetChatReady(set);
  if (check.ok) return true;
  notifyIssue(check.reason);
  return false;
}

/** Retourne false et notifie si les embeddings du set ne sont pas configurés. */
export function ensureProviderSetEmbeddingsReady(set: ProviderSet | null): boolean {
  const check = validateProviderSetEmbeddingsReady(set);
  if (check.ok) return true;
  notifyIssue(check.reason);
  return false;
}
