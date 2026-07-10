import { getAiSidecarUrl, getDesktopSecret } from '@services/aiSidecar';

export interface VersionSnapshot {
  original_path: string;
  snapshot_path: string;
  timestamp: string;
  session_id: string;
}

function sidecarHeaders(): Record<string, string> {
  return { 'X-Internal-Secret': getDesktopSecret() };
}

export async function listVersions(
  projectPath: string,
  sessionId: string,
  filePath: string,
): Promise<VersionSnapshot[]> {
  const params = new URLSearchParams({
    project_path: projectPath,
    session_id: sessionId,
    file_path: filePath,
  });
  const response = await fetch(`${getAiSidecarUrl()}/versions?${params}`, {
    headers: sidecarHeaders(),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = (await response.json()) as { snapshots?: VersionSnapshot[] };
  return data.snapshots ?? [];
}

export async function restoreVersion(
  projectPath: string,
  sessionId: string,
  snapshotPath: string,
): Promise<{ restored_path: string; snapshot_path: string }> {
  const response = await fetch(`${getAiSidecarUrl()}/versions/restore`, {
    method: 'POST',
    headers: {
      ...sidecarHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      project_path: projectPath,
      session_id: sessionId,
      snapshot_path: snapshotPath,
    }),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as { restored_path: string; snapshot_path: string };
}
