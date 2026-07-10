import { normalizeOllamaBaseUrl } from '@utils/guidedModelSetup';

export interface OllamaModelInfo {
  name: string;
}

export async function fetchOllamaModels(baseUrl: string): Promise<string[]> {
  const root = normalizeOllamaBaseUrl(baseUrl);
  const response = await fetch(`${root}/api/tags`);
  if (!response.ok) {
    throw new Error(`Ollama injoignable (HTTP ${response.status})`);
  }

  const data = (await response.json()) as { models?: OllamaModelInfo[] };
  const names = (data.models ?? [])
    .map((model) => model.name)
    .filter((name): name is string => Boolean(name));

  return names.sort((a, b) => a.localeCompare(b));
}
