import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { deleteSession } from '@services/workspaceSession';
import { bumpSessions } from '@composables/useSessionSync';
import { HOME_ROUTE } from '@router/meta';

export function useDeleteConversation() {
  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();
  const deletingIds = ref<Set<string>>(new Set());

  function isDeleting(sessionId: string): boolean {
    return deletingIds.value.has(sessionId);
  }

  async function removeConversation(
    workspaceId: string,
    sessionId: string,
    onRemoved?: () => void,
  ): Promise<boolean> {
    if (deletingIds.value.has(sessionId)) return false;

    const next = new Set(deletingIds.value);
    next.add(sessionId);
    deletingIds.value = next;

    try {
      await deleteSession(workspaceId, sessionId);
      onRemoved?.();
      bumpSessions();

      if (
        route.name === 'chat_session' &&
        String(route.params.id ?? '') === sessionId
      ) {
        await router.push({ name: HOME_ROUTE });
      }
      return true;
    } catch (err) {
      Notify.create({
        message: err instanceof Error ? err.message : t('shell.deleteConversationFailed'),
        classes: 'bg-danger text-white',
      });
      return false;
    } finally {
      const cleared = new Set(deletingIds.value);
      cleared.delete(sessionId);
      deletingIds.value = cleared;
    }
  }

  return { removeConversation, isDeleting };
}
