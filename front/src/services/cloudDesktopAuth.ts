export class CloudDesktopAuthError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'CloudDesktopAuthError';
    this.status = status;
  }
}

export function normalizeCloudBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

export async function loginDesktopCloud(opts: {
  baseUrl: string;
  username: string;
  password: string;
}): Promise<{ token: string }> {
  const root = normalizeCloudBaseUrl(opts.baseUrl);
  if (!root) {
    throw new CloudDesktopAuthError('cloud.loginBaseUrlRequired');
  }

  const username = opts.username.trim();
  const password = opts.password;
  if (!username || !password) {
    throw new CloudDesktopAuthError('cloud.loginCredentialsRequired');
  }

  let response: Response;
  try {
    response = await fetch(`${root}/devices/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new CloudDesktopAuthError('cloud.loginUnreachable');
  }

  if (response.status === 401 || response.status === 400) {
    throw new CloudDesktopAuthError('cloud.loginInvalidCredentials', response.status);
  }

  if (!response.ok) {
    throw new CloudDesktopAuthError('cloud.loginFailed', response.status);
  }

  let data: { token?: unknown };
  try {
    data = (await response.json()) as { token?: unknown };
  } catch {
    throw new CloudDesktopAuthError('cloud.loginFailed', response.status);
  }

  const token = typeof data.token === 'string' ? data.token.trim() : '';
  if (!token) {
    throw new CloudDesktopAuthError('cloud.loginFailed', response.status);
  }

  return { token };
}

export function displayNameFromUsername(username: string): string {
  const trimmed = username.trim();
  const atIndex = trimmed.indexOf('@');
  if (atIndex > 0) {
    return trimmed.slice(0, atIndex);
  }
  return trimmed;
}
