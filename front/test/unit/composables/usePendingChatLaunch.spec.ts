import { describe, expect, it } from 'vitest';
import {
  consumePendingChatLaunchForSession,
  resetPendingChatLaunchForTests,
  setPendingChatLaunch,
} from '@composables/usePendingChatLaunch';

describe('usePendingChatLaunch', () => {
  it('ne consomme pas un lancement destiné à une autre session', () => {
    resetPendingChatLaunchForTests();
    setPendingChatLaunch({
      text: 'bonjour',
      sessionId: 'session-a',
      personasAction: 'avis',
    });

    expect(consumePendingChatLaunchForSession('session-b')).toBeNull();
    expect(consumePendingChatLaunchForSession('session-a')).toEqual({
      text: 'bonjour',
      sessionId: 'session-a',
      personasAction: 'avis',
    });
    expect(consumePendingChatLaunchForSession('session-a')).toBeNull();
  });

  it('consomme un lancement sans sessionId sur la première session chargée', () => {
    resetPendingChatLaunchForTests();
    setPendingChatLaunch({ text: 'legacy' });

    expect(consumePendingChatLaunchForSession('session-x')).toEqual({
      text: 'legacy',
    });
  });
});
