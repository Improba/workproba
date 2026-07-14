# Workproba AI Core

Python sidecar for the Workproba desktop application: agent loop, LLM providers, extraction, RAG, scoped memory, plugins, subprocess sandbox.

Listens on `127.0.0.1:8765` (loopback only in production).

## Development

```bash
./run_dev.sh
# or from root: make dev-ai
# or all-in-one: make dev
```

## Security

Most endpoints require the `X-Internal-Secret` header (value `INTERNAL_SECRET` on the sidecar, `DESKTOP_INTERNAL_SECRET` on the front). Agent and personas SSE flows are accessible on loopback without a secret.

## Endpoints

### Health and capabilities

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/health` | no | Sidecar health |
| GET | `/capabilities` | yes | Sidecar capabilities (plugins, OCR, …) |

### LLM and utilities

| Method | Route | Secret | Role |
|---|---|---|---|
| POST | `/llm/test` | yes | Provider connection test |
| POST | `/llm/sets/test` | yes | Provider set test (chat + embeddings) |
| POST | `/util/title` | yes | Conversation title generation |
| POST | `/util/summarize` | yes | Text summarization |

### Agent

| Method | Route | Secret | Role |
|---|---|---|---|
| POST | `/agent/turn` | no (SSE loopback) | Agent turn, SSE stream |
| POST | `/agent/confirm` | yes | Sensitive action confirmation |
| POST | `/agent/plan/approve` | yes | Agent plan approval |
| POST | `/agent/index-workspace` | yes | Bulk project folder RAG indexing |
| POST | `/agent/reprocess-attachment` | yes | Reprocess attachment OCR/vision |

### Documents and versions

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/documents/preview` | yes | File HTML/text preview |
| POST | `/documents/preview-change` | yes | Diff before write |
| GET | `/versions` | yes | List file versions |
| POST | `/versions/restore` | yes | Restore a version |

### Memory

Scopes `user` (global) and `project` (workspace). Full design: [docs/memory.md](../../docs/memory.md).

**Per-turn injection** (dynamic system prompts): `memory_prompt`, `relevant_sessions_prompt`, `project_sessions_prompt`.

**Agent tools**: `remember`, `recall_project_sessions`, `search_kb`.

**Background promotion**: front calls `POST /memory/promote-session` after auto session summary (every 3 turns).

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/memory/items` | yes | List explicit memories |
| GET | `/memory/search` | yes | Search (RAG + explicit on project) |
| POST | `/memory/add` | yes | Manual add (heuristic consolidation) |
| POST | `/memory/promote-session` | yes | Promote session summary → project memory |
| POST | `/memory/forget` | yes | Delete by id |
| DELETE | `/memory` | yes | Wipe (conversations, memories, all) |

### Personas plugin (`workproba.personas`)

| Method | Route | Secret | Role |
|---|---|---|---|
| GET/POST | `/plugins/personas/sets` | yes | List / create sets |
| DELETE | `/plugins/personas/sets/{set_id}` | yes | Delete custom set |
| POST | `/plugins/personas/ask` | no (SSE) | Opinion per persona |
| POST | `/plugins/personas/meeting` | no (SSE) | Simulated meeting |
| POST | `/plugins/personas/discuss` | no (SSE) | Multi-turn discussion |
| POST | `/plugins/personas/estimate-cost` | yes | Token cost estimate |
| GET | `/plugins/personas/meetings` | yes | Meeting history |
| GET | `/plugins/personas/meetings/{id}` | yes | Meeting detail |
| GET | `/plugins/personas/discussions` | yes | Discussion history |
| GET | `/plugins/personas/discussions/{id}` | yes | Discussion detail |

### Project plugin (`workproba.projet`)

| Method | Route | Secret | Role |
|---|---|---|---|
| GET/POST | `/plugins/projet/projects` | yes | Internal projects |
| POST | `/plugins/projet/publish` | yes | Publish artifact |
| GET | `/plugins/projet/artefacts` | yes | List artifacts |

### Browser plugin (`workproba.browser`)

Opt-in, Playwright headless. Agent tools: `browser_navigate`, `browser_click`, `browser_type`, `browser_scroll`, `browser_press`, `browser_extract`, `browser_back`, `browser_forward`.

Screenshots are UI-only (SSE); the model receives YAML snapshots only. See [docs/browser.md](../../docs/browser.md) for wiring, security, and known limitations.

| Method | Route | Role |
|---|---|---|
| POST | `/plugins/browser/navigate` | Navigate + snapshot |
| POST | `/plugins/browser/snapshot` | Current page snapshot |
| POST | `/plugins/browser/action` | click, type, scroll, press, back, forward, extract |
| POST | `/plugins/browser/close` | Close session |
| GET | `/plugins/browser/status` | Session status |

Full documentation: [docs/browser.md](../../docs/browser.md).

### Web search (core tool)

Agent tool: `web_search`. Always registered; **executable** when the active provider set uses **Mistral** and `permissions_network` is true. Delegates to Mistral Conversations API (`POST /v1/conversations` with native `web_search` connector). Not a plugin; no Settings toggle.

Full documentation: [docs/web-search.md](../../docs/web-search.md).

### Cloud plugin

### Audit

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/audit` | yes | Log entries |
| GET | `/audit/export` | yes | CSV export |
| GET/POST | `/audit/config` | yes | Retention configuration |

## Workspace RAG indexing

`POST /agent/index-workspace` walks the project folder, extracts text from eligible files (text + Office: PDF/DOCX/XLSX/PPTX) and indexes them in the workspace `RagStore` (`memory.db`, project scope). Sensitive folders (`.git`, `node_modules`, …) and forbidden paths (`.env`, …) are ignored. Limits: `INDEX_MAX_FILES` / `INDEX_MAX_FILE_BYTES` / `INDEX_MAX_TOTAL_CHARS`. If RAG is disabled (no embedding model), returns `enabled=false` without error.

## Agent tools

Base tooling: document read/write, KB search, sandbox, versions, **`web_search`** (Mistral + network), etc.

Memory tooling: `remember` (user/project scope, heuristic dedup), `recall_project_sessions`, automatic injection via `memory_prompt` + `relevant_sessions_prompt`.

Plugin tooling (if active): `ask_personas`, `simulate_meeting` (personas), project/browser/cloud tools per manifest.

Registry: `app/plugins/registry.py`.

## Variables

See `.env.example`.

## Tests

```bash
# Offline suite (deterministic, via TestModel: no LLM required)
.venv/bin/pytest -q

# Live tests against Mistral (network + key required)
WP_LIVE_LLM=1 .venv/bin/pytest tests/test_live_mistral.py -q
```

Coverage: agent, scoped memory, plugins, documents, audit, attachments, RAG, HTTP SSE. See [docs/testing.md](../../docs/testing.md).

## Current limits

- Agent: [Pydantic AI](https://ai.pydantic.dev/) (native models). Routing via `OpenAIChatModel` + `AnthropicModel`.
- RAG embeddings: LiteLLM (`litellm.aembedding`). Disabled if `LLM_EMBEDDING_MODEL` is empty → substring search fallback.
- Extraction: text PDF, Word, Excel, PowerPoint. OCR / scanned PDFs out of initial scope.
- Durable (Temporal/Inngest): deferred.
