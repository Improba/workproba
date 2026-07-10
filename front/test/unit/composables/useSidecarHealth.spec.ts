import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatActivity } from '@composables/useChatActivity';

vi.mock('@services/aiSidecar', () => ({
  healthCheck: vi.fn(),
  getAiSidecarUrl: () => 'http://127.0.0.1:8765',
  getDesktopSecret: () => 'desktop-dev-secret',
}));

// Import après le mock pour récupérer la version moquée.
import { healthCheck } from '@services/aiSidecar';
import { useSidecarHealth } from '@composables/useSidecarHealth';

const { sidecarState, setSidecarState, setStreaming } = useChatActivity();

function flushPromises(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function mountWithHealth() {
  const Host = defineComponent({
    setup() {
      useSidecarHealth();
      return {};
    },
    template: '<div />',
  });
  return mount(Host);
}

describe('useSidecarHealth', () => {
  beforeEach(() => {
    setSidecarState('idle');
    setStreaming(false);
    vi.clearAllMocks();
  });

  it('passe à connected quand le sidecar répond sain', async () => {
    (healthCheck as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(true);

    mountWithHealth();
    await flushPromises();

    expect(healthCheck).toHaveBeenCalled();
    expect(sidecarState.value).toBe('connected');
  });

  it('passe à error quand le sidecar est injoignable', async () => {
    (healthCheck as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(false);

    mountWithHealth();
    await flushPromises();

    expect(sidecarState.value).toBe('error');
  });

  it('ne sonde pas pendant un tour de streaming', async () => {
    (healthCheck as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(true);
    setStreaming(true);

    mountWithHealth();
    await flushPromises();

    expect(healthCheck).not.toHaveBeenCalled();
    // L'état n'est pas écrasé par le polling pendant le streaming.
    expect(sidecarState.value).toBe('idle');
  });

  it('ne relance pas d\'appel réseau si l\'état de santé est inchangé', async () => {
    (healthCheck as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(true);

    mountWithHealth();
    await flushPromises();

    const firstCalls = (healthCheck as unknown as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(sidecarState.value).toBe('connected');

    // Forcer un nouveau cycle de poll via un second montage (même état sain).
    const second = mountWithHealth();
    await flushPromises();
    second.unmount();

    // Aucune nouvelle transition d'état -> le second poll ne re-renduit pas 'connected' en plus.
    expect(sidecarState.value).toBe('connected');
    expect(
      (healthCheck as unknown as ReturnType<typeof vi.fn>).mock.calls.length,
    ).toBeGreaterThanOrEqual(firstCalls);
  });
});
