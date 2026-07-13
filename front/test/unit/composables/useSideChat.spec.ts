import { describe, expect, it, vi, beforeEach } from 'vitest';
import { nextTick, ref } from 'vue';

const sideChatPluginPanels = ref<Array<{ pluginId: string }>>([
  { pluginId: 'workproba.personas' },
]);

vi.mock('@composables/usePluginSlots', () => ({
  usePluginSlots: () => ({
    sideChatPluginPanels,
  }),
}));

import {
  resetSideChatStateForTests,
  useSideChat,
} from '@composables/useSideChat';

describe('useSideChat', () => {
  beforeEach(() => {
    resetSideChatStateForTests();
    sideChatPluginPanels.value = [{ pluginId: 'workproba.personas' }];
  });

  it('openSideChat ouvre le panneau et enregistre le plugin actif', () => {
    const { sideChatOpen, activeSideChatPluginId, openSideChat } = useSideChat();

    openSideChat('workproba.personas', { mode: 'avis', personaIds: ['p1'] });

    expect(sideChatOpen.value).toBe(true);
    expect(activeSideChatPluginId.value).toBe('workproba.personas');
  });

  it('closeSideChat ferme le panneau', () => {
    const { sideChatOpen, openSideChat, closeSideChat } = useSideChat();

    openSideChat('workproba.personas');
    closeSideChat();

    expect(sideChatOpen.value).toBe(false);
  });

  it('consumeInitial retourne les valeurs initiales puis les réinitialise', () => {
    const { openSideChat, consumeInitial, launchToken } = useSideChat();

    openSideChat('workproba.personas', {
      mode: 'discussion',
      personaIds: ['p1', 'p2'],
    });

    expect(launchToken.value).toBe(1);
    expect(consumeInitial()).toEqual({
      personaIds: ['p1', 'p2'],
      mode: 'discussion',
      draft: '',
      discussionSeed: null,
      resume: null,
    });
    expect(consumeInitial()).toEqual({
      personaIds: [],
      mode: null,
      draft: '',
      discussionSeed: null,
      resume: null,
    });
  });

  it('incrémente launchToken à chaque ouverture avec payload', () => {
    const { openSideChat, launchToken } = useSideChat();

    openSideChat('workproba.personas', { mode: 'avis', personaIds: ['p1'] });
    expect(launchToken.value).toBe(1);

    openSideChat('workproba.personas', { mode: 'discussion', personaIds: ['p2'] });
    expect(launchToken.value).toBe(2);
  });

  it('hasSideChat reflète la présence de panneaux side_chat', () => {
    const { hasSideChat } = useSideChat();
    expect(hasSideChat.value).toBe(true);

    sideChatPluginPanels.value = [];
    expect(hasSideChat.value).toBe(false);
  });

  it('ferme le side chat quand aucun panneau n’est disponible', async () => {
    const { openSideChat, sideChatOpen } = useSideChat();
    openSideChat('workproba.personas');
    expect(sideChatOpen.value).toBe(true);

    sideChatPluginPanels.value = [];
    await nextTick();
    expect(sideChatOpen.value).toBe(false);
  });

  it('sideChatOpen setter contrôle l’état ouvert', () => {
    const { sideChatOpen } = useSideChat();
    sideChatOpen.value = true;
    expect(sideChatOpen.value).toBe(true);
    sideChatOpen.value = false;
    expect(sideChatOpen.value).toBe(false);
  });

  it('openSideChat sans mode conserve les valeurs initiales', () => {
    const { openSideChat, consumeInitial } = useSideChat();
    openSideChat('workproba.personas', { mode: 'discussion', personaIds: ['p1'] });
    openSideChat('workproba.personas');
    expect(consumeInitial()).toEqual({
      personaIds: ['p1'],
      mode: 'discussion',
      draft: '',
      discussionSeed: null,
      resume: null,
    });
  });

  it('réaffecte le plugin actif quand il n’est plus disponible', async () => {
    sideChatPluginPanels.value = [
      { pluginId: 'workproba.personas' },
      { pluginId: 'workproba.other' },
    ];
    const { openSideChat, activeSideChatPluginId } = useSideChat();
    openSideChat('workproba.other');
    expect(activeSideChatPluginId.value).toBe('workproba.other');

    sideChatPluginPanels.value = [{ pluginId: 'workproba.personas' }];
    await nextTick();
    expect(activeSideChatPluginId.value).toBe('workproba.personas');
  });
});
