# Workproba AI Core

Sidecar Python de l'application bureau Workproba : loop agent, providers LLM, extraction, RAG, sandbox subprocess.

## Endpoint

- `GET /health` : santé du sidecar (loopback uniquement).
- `POST /agent/turn` : tour agent, flux SSE.

## Développement

```bash
./run_dev.sh
# ou depuis la racine : make dev-ai
```

Port par défaut : `8765` sur `127.0.0.1`.

## Variables

Voir `.env.example`.

## Tests

```bash
# Suite hors-ligne (déterministe, via TestModel — pas de LLM requis)
pytest -q

# Tests live contre Mistral (réseau + clé requis)
WP_LIVE_LLM=1 pytest tests/test_live_mistral.py -q
```

Couverture : `llm/config` (build_model, settings, helpers), `agent/loop`
(conversion messages, mapping events SSE, robustesse échecs outils via ModelRetry),
`/agent/turn` HTTP (SSE bout-en-bout avec TestModel), `rag/store` (chunking),
`documents/extractor` (is_binary_document, .docx).

## Limites V1

- Agent : [Pydantic AI](https://ai.pydantic.dev/) (modèles natifs) pour le chat/agent. Routage unifié via `OpenAIChatModel` + `OpenAIProvider` (OpenAI, Ollama, vLLM, Mistral OpenAI-compat) ; Anthropic via `AnthropicModel` (dép optionnelle `anthropic`).
- Embeddings RAG : LiteLLM (`litellm.aembedding`) conservé pour les embeddings (Ollama, Mistral, OpenAI…).
- `RagStore` : RAG vectoriel local (SQLite + sqlite-vec) dans `memory.db` par workspace. Désactivé si `LLM_EMBEDDING_MODEL` vide → repli recherche substring.
- `LocalExtractor` : extraction légère PDF (pdfplumber), Word .docx (python-docx), Excel .xlsx (openpyxl), PowerPoint .pptx (python-pptx). PDFs scannés / OCR hors V1.
- Docling / Mistral OCR : hors V1.
- Durable (Temporal/Inngest) : reporté.
