import { computed, reactive, ref } from 'vue';
import { useAppSettings } from '@composables/useAppSettings';

/**
 * État d'expansion des cartes d'appels d'outil, partagé entre les instances de
 * `ToolCallCard`.
 *
 * Pourquoi hors du composant : l'état doit survivre au démontage/remontage des
 * messages dans la liste (scroll, changement de session). Un `ref` local dans
 * la carte serait perdu et la section dépliée se replierait immédiatement.
 * On stocke donc l'état par id de tool call, côté données réactives.
 *
 * `expansionEpoch` est incrémenté à chaque bascule (tests / coordination) ;
 * la liste plate mesure les hauteurs via le DOM (`offsetHeight`).
 */

const techViewOverrides = reactive(new Map<string, boolean>());
const rawViewOverrides = reactive(new Map<string, boolean>());
const thinkingExpandedOverrides = reactive(new Map<string, boolean>());
const memoryCitationsExpandedOverrides = reactive(new Map<string, boolean>());
const activityGroupExpandedOverrides = reactive(new Map<string, boolean>());

const expansionEpoch = ref(0);

function bumpEpoch(): void {
  expansionEpoch.value += 1;
}

export function useToolCallExpansion(toolCallId: () => string) {
  const { toolCallView } = useAppSettings();

  const isTechView = computed<boolean>({
    get() {
      const id = toolCallId();
      if (techViewOverrides.has(id)) {
        return techViewOverrides.get(id) === true;
      }
      // Préférence globale "tech" : cartes ouvertes par défaut, sans verrouiller
      // chaque carte (l'utilisateur peut refermer indépendamment).
      return toolCallView.value === 'tech';
    },
    set(value: boolean) {
      techViewOverrides.set(toolCallId(), value);
      bumpEpoch();
    },
  });

  const showRaw = computed<boolean>({
    get() {
      return rawViewOverrides.get(toolCallId()) === true;
    },
    set(value: boolean) {
      rawViewOverrides.set(toolCallId(), value);
      bumpEpoch();
    },
  });

  function toggleTechView(): void {
    isTechView.value = !isTechView.value;
  }

  function toggleRaw(): void {
    showRaw.value = !showRaw.value;
  }

  return {
    isTechView,
    showRaw,
    toggleTechView,
    toggleRaw,
  };
}

/**
 * État déplié du bloc "Raisonnement" (`ThinkingCard`). Même raison que pour
 * les tool calls : l'état doit survivre au démontage des messages dans la liste.
 */
export function useThinkingExpansion(thinkingId: () => string) {
  const expanded = computed<boolean>({
    get() {
      return thinkingExpandedOverrides.get(thinkingId()) === true;
    },
    set(value: boolean) {
      thinkingExpandedOverrides.set(thinkingId(), value);
      bumpEpoch();
    },
  });

  function toggle(): void {
    expanded.value = !expanded.value;
  }

  return { expanded, toggle };
}

/**
 * État déplié de `MemoryCitationsBar`. Même raison que thinking / tool calls :
 * état partagé hors composant. Clé stable fournie par le parent (`message.id`,
 * `card.id-personaId`, etc.).
 */
export function useMemoryCitationsExpansion(
  key: () => string,
  defaultExpanded?: () => boolean,
) {
  const expanded = computed<boolean>({
    get() {
      const id = key();
      if (memoryCitationsExpandedOverrides.has(id)) {
        return memoryCitationsExpandedOverrides.get(id) === true;
      }
      return defaultExpanded?.() ?? false;
    },
    set(value: boolean) {
      memoryCitationsExpandedOverrides.set(key(), value);
      bumpEpoch();
    },
  });

  function toggle(): void {
    expanded.value = !expanded.value;
  }

  return { expanded, toggle };
}

/**
 * État déplié de `ActivityGroup`. Même raison que thinking / tool calls :
 * état partagé hors composant. Clé = id de la première part du run.
 */
export function useActivityGroupExpansion(
  key: () => string,
  defaultExpanded?: () => boolean,
) {
  const expanded = computed<boolean>({
    get() {
      const id = key();
      if (activityGroupExpandedOverrides.has(id)) {
        return activityGroupExpandedOverrides.get(id) === true;
      }
      return defaultExpanded?.() ?? false;
    },
    set(value: boolean) {
      activityGroupExpandedOverrides.set(key(), value);
      bumpEpoch();
    },
  });

  function toggle(): void {
    expanded.value = !expanded.value;
  }

  return { expanded, toggle };
}

/** Replie un bloc raisonnement (ex. quand un tool_call suit). */
export function collapseThinking(thinkingPartId: string): void {
  if (thinkingExpandedOverrides.get(thinkingPartId) !== true) return;
  thinkingExpandedOverrides.set(thinkingPartId, false);
  bumpEpoch();
}

/** Replie un groupe d'activité (ex. quand un tool_call suit un thinking). */
export function collapseActivityGroup(groupId: string): void {
  if (activityGroupExpandedOverrides.get(groupId) !== true) return;
  activityGroupExpandedOverrides.set(groupId, false);
  bumpEpoch();
}

/** True si ce segment thinking est déplié (défaut = replié). */
export function isThinkingPartExpanded(thinkingPartId: string): boolean {
  return thinkingExpandedOverrides.get(thinkingPartId) === true;
}

/** Vide les maps d'expansion au changement de session pour éviter une fuite mémoire. */
export function clearExpansionState(): void {
  techViewOverrides.clear();
  rawViewOverrides.clear();
  thinkingExpandedOverrides.clear();
  memoryCitationsExpandedOverrides.clear();
  activityGroupExpandedOverrides.clear();
  bumpEpoch();
}

export { expansionEpoch };
