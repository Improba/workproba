import OpenAI from 'openai';
import {
  LlmChatOptions,
  LlmChatResult,
  LlmEmbeddingOptions,
  LlmProvider,
  LlmProviderRuntimeConfig,
  LlmStreamChunk,
} from '@core/llm-provider/interfaces/llm-provider.interface';

export class OpenAICompatProvider implements LlmProvider {
  private readonly client: OpenAI;

  constructor(private readonly config: LlmProviderRuntimeConfig) {
    this.client = new OpenAI({
      apiKey: config.apiKey ?? 'not-configured',
      baseURL: config.baseUrl ?? undefined,
    });
  }

  async chat(options: LlmChatOptions): Promise<LlmChatResult> {
    const model = options.model ?? this.config.defaultModel;
    if (!model) {
      throw new Error('OpenAI-compatible provider requires a model');
    }

    const response = await this.client.chat.completions.create({
      model,
      messages: options.messages,
      temperature: options.temperature,
    });

    return {
      content: response.choices[0]?.message.content ?? '',
      model: response.model,
      raw: response,
    };
  }

  async embeddings(options: LlmEmbeddingOptions): Promise<number[][]> {
    const model = options.model ?? this.config.embeddingModel;
    if (!model) {
      throw new Error('OpenAI-compatible provider requires an embedding model');
    }

    const response = await this.client.embeddings.create({
      model,
      input: options.input,
    });

    return response.data.map((item) => item.embedding);
  }

  async *streamChat(options: LlmChatOptions): AsyncIterable<LlmStreamChunk> {
    const model = options.model ?? this.config.defaultModel;
    if (!model) {
      throw new Error('OpenAI-compatible provider requires a model');
    }

    const stream = await this.client.chat.completions.create({
      model,
      messages: options.messages,
      temperature: options.temperature,
      stream: true,
    });

    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content;
      if (!content) {
        continue;
      }

      yield {
        type: 'token',
        content,
        raw: chunk,
      };
    }

    yield { type: 'done' };
  }
}
