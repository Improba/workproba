import { Notify } from 'quasar';
import type { ProviderSet } from '@composables/useDesktop.types';
import { t } from '@utils/i18nT';
import {
  type CloudProviderReadiness,
  type ProviderSetReadinessIssue,
  validateProviderSetChatReady,
  validateProviderSetEmbeddingsReady,
} from '@utils/providerSetValidation';

function readinessMessage(reason: ProviderSetReadinessIssue): string {
  switch (reason) {
    case 'missing_api_key':
      return t('errors.apiKeyMissing');
    case 'missing_base_url':
      return t('errors.baseUrlMissing');
    case 'cloud_not_enrolled':
      return t('errors.cloudNotEnrolled');
    case 'not_subscribed':
      return t('errors.cloudNotSubscribed');
    case 'quota_exceeded':
      return t('errors.cloudQuotaExceeded');
    case 'cloud_unreachable':
      return t('errors.cloudUnreachable');
    case 'no_set':
    default:
      return t('chat.page.noModelConfigured');
  }
}

function notifyIssue(reason: ProviderSetReadinessIssue): void {
  Notify.create({
    message: readinessMessage(reason),
    classes: 'bg-warning text-neutral-lowest',
    timeout: 6000,
  });
}

/** Retourne false et notifie l'utilisateur si le set n'est pas prêt pour le chat. */
export function ensureProviderSetChatReady(
  set: ProviderSet | null,
  cloud?: CloudProviderReadiness | null,
): set is ProviderSet {
  const check = validateProviderSetChatReady(set, cloud);
  if (check.ok) return true;
  notifyIssue(check.reason);
  return false;
}

/** Retourne false et notifie si les embeddings du set ne sont pas configurés. */
export function ensureProviderSetEmbeddingsReady(
  set: ProviderSet | null,
  cloud?: CloudProviderReadiness | null,
): boolean {
  const check = validateProviderSetEmbeddingsReady(set, cloud);
  if (check.ok) return true;
  notifyIssue(check.reason);
  return false;
}

export function chatErrorMessageForReadiness(reason: ProviderSetReadinessIssue): string {
  return readinessMessage(reason);
}

export function chatErrorCodeForReadiness(
  reason: ProviderSetReadinessIssue,
): 'api_key_missing' | 'cloud_not_enrolled' | 'not_subscribed' | 'quota_exceeded' | 'cloud_unreachable' | 'no_model' {
  switch (reason) {
    case 'missing_api_key':
      return 'api_key_missing';
    case 'cloud_not_enrolled':
      return 'cloud_not_enrolled';
    case 'not_subscribed':
      return 'not_subscribed';
    case 'quota_exceeded':
      return 'quota_exceeded';
    case 'cloud_unreachable':
      return 'cloud_unreachable';
    case 'no_set':
    default:
      return 'no_model';
  }
}
