export type LlmMessageRole = 'system' | 'user' | 'assistant' | 'tool';

export interface LlmChatMessage {
  role: LlmMessageRole;
  content: string;
  name?: string;
}

export interface LlmChatOptions {
  model?: string;
  messages: LlmChatMessage[];
  temperature?: number;
}

export interface LlmChatResult {
  content: string;
  model?: string;
  raw?: unknown;
}

export interface LlmEmbeddingOptions {
  model?: string;
  input: string[];
}

export interface LlmStreamChunk {
  type: 'token' | 'tool-call' | 'done';
  content?: string;
  raw?: unknown;
}

export interface LlmProvider {
  chat(options: LlmChatOptions): Promise<LlmChatResult>;
  embeddings(options: LlmEmbeddingOptions): Promise<number[][]>;
  streamChat(options: LlmChatOptions): AsyncIterable<LlmStreamChunk>;
}

export interface LlmProviderRuntimeConfig {
  baseUrl?: string | null;
  apiKey?: string | null;
  defaultModel?: string | null;
  embeddingModel?: string | null;
}
