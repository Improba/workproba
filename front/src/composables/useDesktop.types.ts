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
import type { UiThemeId } from '@utils/uiTheme';

export type { UiThemeId };

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
  utilityModel?: string | null;
  reasoningEffort?: ReasoningEffort | null;
}

export type ToolCallViewMode = 'human' | 'tech';

export type SettingsMode = 'guided' | 'advanced';

export type DensityMode = 'compact' | 'comfortable' | 'spacious';

export type AppLocale = 'fr' | 'en-US';

export type ProviderSetChatReasoning = 'auto' | 'none' | 'low' | 'medium' | 'high';
export type ProviderSetOcrProvider = 'mistral' | 'docling';
export type ProviderSetOcrMode = 'auto' | 'none';
export type ProviderSetVisionMode = 'chat' | 'none';
export type ProviderSetCapabilitiesReasoning = 'low' | 'medium' | 'high';

export interface ProviderSetChatModel {
  model: string;
  label: string;
  hint?: string;
  contextWindow?: number;
  reasoningEfforts?: ReasoningEffort[];
}

export interface ProviderSetChat {
  provider: LlmProviderName;
  model: string;
  apiKeyRef?: string | null;
  apiKey?: string | null;
  baseUrl?: string | null;
  reasoning?: ProviderSetChatReasoning;
  models?: ProviderSetChatModel[];
}

export interface ProviderSetEmbeddings {
  provider: LlmProviderName;
  model: string;
  apiKeyRef?: string | null;
  apiKey?: string | null;
  baseUrl?: string | null;
}

export interface ProviderSetOcr {
  provider: ProviderSetOcrProvider;
  mode: ProviderSetOcrMode;
}

export interface ProviderSetVision {
  mode: ProviderSetVisionMode;
}

export interface ProviderSetCapabilities {
  reasoning: ProviderSetCapabilitiesReasoning;
  vision: boolean;
  tools: boolean;
  webSearch: boolean;
}

export interface ProviderSet {
  id: string;
  name: string;
  description: string;
  badges: string[];
  chat: ProviderSetChat;
  embeddings: ProviderSetEmbeddings | null;
  ocr: ProviderSetOcr | null;
  vision: ProviderSetVision;
  capabilities: ProviderSetCapabilities;
  isDefault: boolean;
  isBuiltin: boolean;
}

export type PluginSource = 'builtin' | 'local';

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  permissions: string[];
  defaultEnabled: boolean;
  uiSlots: string[];
  hooks: string[];
  isBuiltin: boolean;
}

export interface PluginInfo {
  manifest: PluginManifest;
  enabled: boolean;
  enabledScoped: boolean;
  source: PluginSource;
}

/** Configuration enterprise imposée (preset verrouillé, camelCase Tauri). */
export interface EnterprisePreset {
  settingsLocked: boolean;
  localeLocked: boolean;
  locale?: string | null;
  pluginsAllowed?: string[] | null;
  localPluginsAllowed?: boolean | null;
  permissionsNetwork?: boolean | null;
  permissionsProjectSync?: boolean | null;
  permissionsNetworkImprobaCloud?: boolean | null;
  cloudEndpoint?: string | null;
  cloudOrgId?: string | null;
  codeExecute?: boolean | null;
  auditRetentionDays?: number | null;
  auditEnabled?: boolean | null;
  providerSetsLocked?: boolean | null;
  allowedProviderSetIds?: string[] | null;
}

export interface AppSettings {
  version: number;
  providers: LlmProviderEntry[];
  activeChatProviderId?: string | null;
  activeEmbeddingProviderId?: string | null;
  toolCallView?: ToolCallViewMode;
  /** Demander confirmation avant écriture fichier (mode avancé). Défaut true. */
  confirmBeforeWrite?: boolean | null;
  settingsMode?: SettingsMode;
  settingsLocked?: boolean;
  density?: DensityMode;
  /** Thème graphique (papier, charbon, …). */
  uiTheme?: UiThemeId | null;
  onboardingDone?: boolean;
  locale?: AppLocale | null;
  /** Langue imposée par preset : le toggle est masqué. */
  localeLocked?: boolean | null;
  /** Nom affiché dans l'interface (onboarding profil). */
  userName?: string | null;
  /** Organisation affichée dans l'interface (onboarding profil). */
  userOrg?: string | null;
  /** Profil nom/org renseigné au premier lancement. */
  profileOnboardingDone?: boolean;
  /** Provider sets (Vague 6). Persistés côté Rust (agent G). */
  sets?: ProviderSet[];
  /** ID du set actif. */
  activeSetId?: string | null;
  /** Autorise les permissions réseau (preset verrouillé). Absent = autorisé. */
  permissionsNetwork?: boolean | null;
  /** Autorise la synchronisation projet (preset verrouillé). Absent = autorisé. */
  permissionsProjectSync?: boolean | null;
  /** Autorise le réseau Improba Cloud (preset verrouillé). Absent = autorisé. */
  permissionsNetworkImprobaCloud?: boolean | null;
  /** Endpoint du plan de contrôle cloud (preset). */
  cloudEndpoint?: string | null;
  /** Identifiant d'organisation cloud (preset). */
  cloudOrgId?: string | null;
  /** Plugins locaux autorisés (preset verrouillé). */
  localPluginsAllowed?: boolean | null;
  /** Liste blanche de plugins (preset verrouillé). */
  pluginsAllowed?: string[] | null;
  /** Exécution de code autorisée (preset verrouillé). */
  codeExecute?: boolean | null;
  /** Rétention du journal d'audit (jours, preset). */
  auditRetentionDays?: number | null;
  /** Journal d'audit activé (preset). */
  auditEnabled?: boolean | null;
  /** Sets provider verrouillés (preset). */
  providerSetsLocked?: boolean | null;
  /** Identifiants de sets autorisés (preset). */
  allowedProviderSetIds?: string[] | null;
}
