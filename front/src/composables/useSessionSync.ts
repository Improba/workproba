import { ref } from 'vue';

/**
 * Compteur partagé de révision de la liste des sessions.
 *
 * Permet à un composant qui modifie une session (titre auto, résumé persisté)
 * de signaler à la sidebar qu'elle doit rafraîchir sa liste, sans couplage
 * direct entre les deux. La sidebar watch `sessionVersion` et recharge.
 */
const sessionVersion = ref(0);

export function bumpSessions(): void {
  sessionVersion.value += 1;
}

export function useSessionSync(): { sessionVersion: typeof sessionVersion } {
  return { sessionVersion };
}
