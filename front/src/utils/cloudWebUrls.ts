const DEFAULT_CLOUD_WEB_ORIGIN = 'http://localhost:8482';

// TODO(deep-link): workproba://enroll?token=… — nécessite tauri-plugin-deep-link
// et un scheme dans tauri.conf.json. En attendant : ouverture URL cloud + collage du code.

function normalizeOrigin(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

/** Origine du front web Improba Cloud (login / inscription). */
export function resolveCloudWebOrigin(): string {
  const env = import.meta.env.VITE_CLOUD_WEB_URL;
  if (typeof env === 'string' && env.trim()) {
    return normalizeOrigin(env);
  }
  return DEFAULT_CLOUD_WEB_ORIGIN;
}

export function cloudAuthLoginUrl(origin = resolveCloudWebOrigin()): string {
  return `${normalizeOrigin(origin)}/auth/login`;
}

export function cloudAuthRegisterUrl(origin = resolveCloudWebOrigin()): string {
  return `${normalizeOrigin(origin)}/auth/register`;
}
