export interface LocalDocumentEntry {
  name: string;
  relativePath: string;
  kind: string;
}

export interface LocalDirEntry {
  name: string;
  relativePath: string;
  isDir: boolean;
  kind: string;
}

export interface WorkspaceInfo {
  id: string;
  folderPath: string;
  dataDir: string;
  title: string;
  createdAt: string;
  lastOpenedAt: string;
}

export type LlmProviderName =
  | 'openai_compat'
  | 'openai'
  | 'mistral'
  | 'ollama'
  | 'vllm'
  | 'anthropic';

import type { ReasoningEffort } from '#types';

export interface LlmProviderEntry {
  id: string;
  label: string;
  provider: LlmProviderName;
  model: string;
  baseUrl?: string | null;
  apiKey?: string | null;
  temperature?: number | null;
  maxTokens?: number | null;
  extraHeaders?: Record<string, string>;
  embeddingModel?: string | null;
  embeddingBaseUrl?: string | null;
  reasoningEffort?: ReasoningEffort | null;
}

export type ToolCallViewMode = 'human' | 'tech';

export type SettingsMode = 'guided' | 'advanced';

export type DensityMode = 'compact' | 'comfortable' | 'spacious';

export interface AppSettings {
  version: number;
  providers: LlmProviderEntry[];
  activeChatProviderId?: string | null;
  activeEmbeddingProviderId?: string | null;
  toolCallView?: ToolCallViewMode;
  settingsMode?: SettingsMode;
  settingsLocked?: boolean;
  density?: DensityMode;
  onboardingDone?: boolean;
}
