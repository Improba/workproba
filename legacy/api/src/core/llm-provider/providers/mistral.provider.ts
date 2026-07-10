import { Mistral } from '@mistralai/mistralai';
import {
  LlmChatOptions,
  LlmChatResult,
  LlmEmbeddingOptions,
  LlmProvider,
  LlmProviderRuntimeConfig,
  LlmStreamChunk,
} from '@core/llm-provider/interfaces/llm-provider.interface';

export class MistralProvider implements LlmProvider {
  private readonly client: Mistral;

  constructor(private readonly config: LlmProviderRuntimeConfig) {
    this.client = new Mistral({
      apiKey: config.apiKey ?? 'not-configured',
    });
  }

  async chat(options: LlmChatOptions): Promise<LlmChatResult> {
    // TODO: map Workproba chat options to the Mistral SDK once provider specifics are selected.
    throw new Error(`Mistral chat provider is not wired yet (${options.messages.length} messages)`);
  }

  async embeddings(options: LlmEmbeddingOptions): Promise<number[][]> {
    // TODO: choose the Mistral embedding endpoint and normalize vectors.
    throw new Error(`Mistral embeddings provider is not wired yet (${options.input.length} inputs)`);
  }

  async *streamChat(options: LlmChatOptions): AsyncIterable<LlmStreamChunk> {
    // TODO: expose native Mistral streaming events.
    throw new Error(`Mistral streaming provider is not wired yet (${options.messages.length} messages)`);
  }
}
