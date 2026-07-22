import { computed, reactive, ref } from 'vue';
import { useAppSettings } from '@composables/useAppSettings';

/**
 * État d'expansion des cartes d'appels d'outil, partagé entre les instances de
 * `ToolCallCard`.
 *
 * Pourquoi hors du composant : les cartes vivent dans un `DynamicScroller`
 * (vue-virtual-scroller) qui recycle (démonte) les items sortis de la fenêtre
 * active. Un `ref` local serait perdu à chaque recyclage -> la section
 * dépliée se replierait immédiatement (notamment pendant le streaming, où
 * `item.content` change toutes les ~50 ms et re-mesure le scroller). On stocke
 * donc l'état par id de tool call, côté données réactives.
 *
 * `expansionEpoch` est incrémenté à chaque bascule ; il est consommé par les
 * `size-dependencies` du `DynamicScrollerItem` pour forcer un re-mesurage quand
 * une carte se déplie/replie (sinon la hauteur réservée par le virtual scroller
 * devient stale et la carte dépliée chevauche la suivante).
 */

const techViewOverrides = reactive(new Map<string, boolean>());
const rawViewOverrides = reactive(new Map<string, boolean>());
const thinkingExpandedOverrides = reactive(new Map<string, boolean>());

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
 * les tool calls : la carte vit dans le `DynamicScroller` et un `ref` local
 * serait perdu au recyclage. Clé = id du segment `thinking` (stable pendant
 * toute la vie du message).
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

/** Replie un bloc raisonnement (ex. quand un tool_call suit). */
export function collapseThinking(thinkingPartId: string): void {
  if (thinkingExpandedOverrides.get(thinkingPartId) !== true) return;
  thinkingExpandedOverrides.set(thinkingPartId, false);
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
  bumpEpoch();
}

export { expansionEpoch };
