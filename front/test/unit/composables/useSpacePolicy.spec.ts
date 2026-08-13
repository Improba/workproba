import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

const activeDataDir = ref<string | null>('/tmp/ws');

const fetchWorkspacePolicy = vi.fn();
const updateWorkspacePolicy = vi.fn();

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({ activeDataDir }),
}));

vi.mock('@services/aiSidecar', () => ({
  fetchWorkspacePolicy: (...args: unknown[]) => fetchWorkspacePolicy(...args),
  updateWorkspacePolicy: (...args: unknown[]) => updateWorkspacePolicy(...args),
}));

import { useSpacePolicy } from '@composables/useSpacePolicy';

describe('useSpacePolicy', () => {
  beforeEach(() => {
    fetchWorkspacePolicy.mockReset();
    updateWorkspacePolicy.mockReset();
    fetchWorkspacePolicy.mockResolvedValue({
      ok: true,
      data: { approvalMode: 'security' },
    });
    updateWorkspacePolicy.mockResolvedValue({
      ok: true,
      data: { approvalMode: 'trust' },
    });
  });

  it('charge le mode au montage', async () => {
    const dataDir = ref('/tmp/custom-ws');
    const { approvalMode, loading } = useSpacePolicy({ workspaceDataDir: dataDir });
    await vi.waitFor(() => expect(loading.value).toBe(false));
    expect(fetchWorkspacePolicy).toHaveBeenCalledWith({
      workspaceDataDir: '/tmp/custom-ws',
    });
    expect(approvalMode.value).toBe('security');
  });

  it('persiste trust au toggle', async () => {
    const dataDir = ref('/tmp/custom-ws');
    const { approvalMode, setApprovalMode } = useSpacePolicy({ workspaceDataDir: dataDir });
    await vi.waitFor(() => expect(approvalMode.value).toBe('security'));

    const result = await setApprovalMode('trust');
    expect(result.ok).toBe(true);
    expect(updateWorkspacePolicy).toHaveBeenCalledWith({
      workspaceDataDir: '/tmp/custom-ws',
      approvalMode: 'trust',
    });
    expect(approvalMode.value).toBe('trust');
  });

  it('restaure le mode précédent si la mise à jour échoue', async () => {
    updateWorkspacePolicy.mockResolvedValueOnce({ ok: false, error: 'network' });
    const dataDir = ref('/tmp/custom-ws');
    const { approvalMode, setApprovalMode } = useSpacePolicy({ workspaceDataDir: dataDir });
    await vi.waitFor(() => expect(approvalMode.value).toBe('security'));

    const result = await setApprovalMode('trust');
    expect(result.ok).toBe(false);
    expect(approvalMode.value).toBe('security');
  });
});
