import { computed, ref, watch, type Ref } from 'vue';
import {
  fetchWorkspacePolicy,
  updateWorkspacePolicy,
  type ApprovalMode,
  type WorkspacePolicy,
} from '@services/aiSidecar';
import { useSpace } from './useSpace';

export interface UseSpacePolicyReturn {
  loading: Ref<boolean>;
  error: Ref<string | null>;
  approvalMode: Ref<ApprovalMode>;
  saving: Ref<boolean>;
  refresh: () => Promise<void>;
  setApprovalMode: (mode: ApprovalMode) => Promise<{ ok: boolean; error?: string }>;
}

export interface UseSpacePolicyOptions {
  workspaceDataDir?: Ref<string | null | undefined>;
}

export function useSpacePolicy(opts?: UseSpacePolicyOptions): UseSpacePolicyReturn {
  const { activeDataDir } = useSpace();
  const dataDirRef = opts?.workspaceDataDir ?? activeDataDir;

  const loading = ref(false);
  const saving = ref(false);
  const error = ref<string | null>(null);
  const approvalMode = ref<ApprovalMode>('security');
  let requestSeq = 0;

  async function refresh(): Promise<void> {
    const dataDir = dataDirRef.value;
    if (!dataDir?.trim()) {
      approvalMode.value = 'security';
      error.value = null;
      return;
    }

    const seq = ++requestSeq;
    loading.value = true;
    error.value = null;
    try {
      const result = await fetchWorkspacePolicy({ workspaceDataDir: dataDir });
      if (seq !== requestSeq) return;
      if (!result.ok || !result.data) {
        error.value = result.error ?? 'workspace_policy_failed';
        return;
      }
      approvalMode.value = result.data.approvalMode;
    } finally {
      if (seq === requestSeq) {
        loading.value = false;
      }
    }
  }

  async function setApprovalMode(mode: ApprovalMode): Promise<{ ok: boolean; error?: string }> {
    const dataDir = dataDirRef.value;
    if (!dataDir?.trim()) {
      return { ok: false, error: 'no_workspace' };
    }
    if (approvalMode.value === mode) {
      return { ok: true };
    }

    const previous = approvalMode.value;
    approvalMode.value = mode;
    saving.value = true;
    error.value = null;
    try {
      const result = await updateWorkspacePolicy({
        workspaceDataDir: dataDir,
        approvalMode: mode,
      });
      if (!result.ok || !result.data) {
        approvalMode.value = previous;
        const err = result.error ?? 'workspace_policy_update_failed';
        error.value = err;
        return { ok: false, error: err };
      }
      approvalMode.value = result.data.approvalMode;
      return { ok: true };
    } finally {
      saving.value = false;
    }
  }

  watch(
    dataDirRef,
    () => {
      void refresh();
    },
    { immediate: true },
  );

  return {
    loading,
    error,
    approvalMode,
    saving,
    refresh,
    setApprovalMode,
  };
}

export type { ApprovalMode, WorkspacePolicy };
