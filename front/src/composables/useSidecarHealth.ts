import { onMounted, onUnmounted } from 'vue';
import { useChatActivity } from '@composables/useChatActivity';
import { healthCheck } from '@services/aiSidecar';

const POLL_INTERVAL_MS = 8000;

export function useSidecarHealth(): void {
  const { streaming, setSidecarState } = useChatActivity();
  let intervalId: ReturnType<typeof setInterval> | null = null;
  let lastKnownHealthy: boolean | null = null;

  async function poll(): Promise<void> {
    if (streaming.value) return;

    const healthy = await healthCheck();
    if (lastKnownHealthy === healthy) return;

    lastKnownHealthy = healthy;
    setSidecarState(healthy ? 'connected' : 'error');
  }

  function start(): void {
    if (intervalId !== null) return;
    void poll();
    intervalId = setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
  }

  function stop(): void {
    if (intervalId === null) return;
    clearInterval(intervalId);
    intervalId = null;
  }

  onMounted(start);
  onUnmounted(stop);
}
