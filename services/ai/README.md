# Workproba AI Core

Python sidecar for the Workproba desktop application: agent loop, LLM providers, extraction, RAG, scoped memory, **builtin plugins only** (local plugin runtime not loaded in V2). `run_code` exists but is **not exposed** in V2.

Listens on `127.0.0.1:8765` (loopback only in production).

## Development

```bash
./run_dev.sh
# or from root: make dev-ai
# or all-in-one: make dev
```

## Packaging (PyInstaller)

Production binary for Tauri `externalBin` (onefile, ~120 Mo Linux) :

```bash
# from repo root
make build-sidecar
# → desktop/src-tauri/binaries/workproba-ai-<host-triple>
```

Spec: `workproba_ai.spec`, entry point: `workproba_ai_entry.py`. Onefile avoids a separate `_internal` folder, which is incompatible with the Tauri sidecar runtime layout. CI builds and smoke-tests the sidecar on every push to `main`/`develop` and on release tags.

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
| POST | `/llm/sets/test` | yes | Provider set test (chat + embeddings). Accepts `provider_set` + `cloud_plugin_data_dir` for Improba Cloud |
| POST | `/util/title` | yes | Conversation title generation (`provider_set` + `cloud_plugin_data_dir` when cloud) |
| POST | `/util/summarize` | yes | Text summarization (`provider_set` + `cloud_plugin_data_dir` when cloud) |

### Agent

| Method | Route | Secret | Role |
|---|---|---|---|
| POST | `/agent/turn` | no (SSE loopback) | Agent turn, SSE stream |
| POST | `/agent/confirm` | yes | Approve or deny a pending `confirmation_request` (`approve` / `deny`) |
| POST | `/agent/plan/approve` | yes | Agent plan approval |
| POST | `/agent/index-workspace` | yes | Bulk project folder RAG indexing |
| POST | `/agent/reprocess-attachment` | yes | Reprocess attachment OCR/vision |

### Human Approval Gate

Sensitive agent tools pause until the user approves via `POST /agent/confirm`.

1. During `/agent/turn`, the sidecar may emit SSE `confirmation_request` with effect-oriented fields: `effect`, `targets`, `headline`, `protection_labels`, `protections`.
2. The front displays `ConfirmationCard` and posts `{ session_id, turn_id, confirmation_id, decision }` to `/agent/confirm`.
3. On deny or timeout (300 s), the tool is not executed; the model receives `ModelRetry` with `workproba:approval_denied` or `workproba:approval_timeout`.

Effect classification: `app/agent/effects.py` (`classify_effect`). Gate: `app/agent/confirmation.py` (`ConfirmationGate.request_effect`). Gated tools include file writes, `publish_artifact`, `web_search`, `browser_*`, `run_code`, `sync_to_cloud`, **`invoke_managed_connector`**. Read-only tools are not gated.

Work events (`work_started`, `work_contribution`, `work_completed`, `work_failed`) are emitted alongside tool events; see `app/agent/work_events.py` and [docs/architecture.md](../../docs/architecture.md#human-approval-and-work-events).

### Documents and versions

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/documents/preview` | yes | File HTML/text preview |
| POST | `/documents/preview-change` | yes | Diff before write |
| GET | `/versions` | yes | List file versions |
| POST | `/versions/restore` | yes | Restore a version |

### Memory

Scopes `user` (global) and `project` (workspace). Full design: [docs/memory.md](../../docs/memory.md).

**Per-turn injection** (dynamic system prompts): `memory_prompt`, `relevant_sessions_prompt`, `project_sessions_prompt`. Ranking uses **hybrid semantic + lexical** scores when an embedding model is configured; vectors are cached in-process (`embedding_cache.py`, see [docs/memory.md](../../docs/memory.md)).

**Agent tools**: `remember`, `recall_project_sessions`, `search_kb`.

**Background promotion**: front calls `POST /memory/promote-session` after auto session summary (every 3 turns).

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/memory/items` | yes | List explicit memories |
| GET | `/memory/search` | yes | Search (RAG + explicit on project) |
| POST | `/memory/add` | yes | Manual add (heuristic consolidation) |
| POST | `/memory/promote-session` | yes | Promote session summary → project memory (`provider_set` + `cloud_plugin_data_dir` when cloud) |
| POST | `/memory/forget` | yes | Delete by id |
| DELETE | `/memory` | yes | Wipe (conversations, memories, all) |

### Personas plugin (`workproba.personas`)

Guided UI: **Regards métier**. SSE routes accept `provider_set` + `cloud_plugin_data_dir` when the active engine is Improba Cloud.

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

### Cloud plugin (`workproba.cloud`) — Mode A MVP

Join org, managed capabilities (API connectors), artefact sync, enterprise regards. Agent tools (if active): `enroll_to_cloud`, `sync_managed_regards`, `sync_to_cloud`, **`invoke_managed_connector`** (Human Approval Gate `external_send`). Product UI: Workproba Cloud capability + nested managed capabilities (e.g. Ihora).

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/plugins/cloud/connectors` | yes | List managed capabilities from control plane |
| POST | `/plugins/cloud/enroll` | yes | Join with `join_token`, or bearer: User JWT is exchanged via control-plane `POST /devices/desktop-bearer` into durable `wp_dev_*` (opaque/`wp_dev_*` stored as-is) |
| GET | `/plugins/cloud/status` | yes | Status + silent migration of a still-valid User JWT to `wp_dev_*` (`ensure_durable_device_bearer`) |
| POST | `/plugins/cloud/sync-regards` | yes | Pull and install managed regards catalog |
| GET/POST | `/plugins/cloud/artefacts` | yes | Shared project list/publish/open/republish |
| POST | `/plugins/cloud/sync` | yes | Mount sync push (blocked when enrolled) |
| POST | `/plugins/cloud/pull` | yes | Mount sync pull (blocked when enrolled) |

Control plane relay: `GET /connectors`, `POST /connectors/{id}/invoke` (builtins `echo`, `ihora.shaped` stub, `ihora` HTTP when org allowlist permits ; payload only, identity derived server-side). Desktop Capabilities hub shows these as managed capabilities under Workproba Cloud. See [architecture-cloud.md](../../../workproba-improba/roadmaps/architecture-cloud.md).

### Improba Cloud LLM (`device_bearer`)

Builtin set `workproba-cloud` (`auth_mode: device_bearer`). The sidecar resolves the DeviceBearer (`wp_dev_*`) from `{app_data}/plugins/workproba.cloud/` via `cloud_plugin_data_dir` and calls `{control_plane}/llm/v1` (chat, embeddings, OCR). Login must not leave a User JWT on disk: enroll/status exchange it for `wp_dev_*`. Cloud LLM auth errors include `invalid_user_jwt` / `invalid_device_token` (mapped, non-retryable). Quota: `GET /llm/v1/quota` (bearer only; no `device_id` in client body).

Routes that honor `provider_set` + `cloud_plugin_data_dir`: `/agent/turn`, `/llm/sets/test`, `/util/title`, `/util/summarize`, `/memory/promote-session`, personas SSE (`/plugins/personas/ask|meeting|discuss`). Details: [docs/provider-sets-reasoning.md](../../docs/provider-sets-reasoning.md).

### Audit

| Method | Route | Secret | Role |
|---|---|---|---|
| GET | `/audit` | yes | Log entries |
| GET | `/audit/export` | yes | CSV export |
| GET/POST | `/audit/config` | yes | Retention configuration |

## Workspace RAG indexing

`POST /agent/index-workspace` walks the project folder, extracts text from eligible files (text + Office: PDF/DOCX/XLSX/PPTX) and indexes them in the workspace `RagStore` (`memory.db`, project scope). Sensitive folders (`.git`, `node_modules`, `vendor`, …) and forbidden paths (`.env`, …) are ignored. Embeddings are sent in batches (`EMBEDDING_BATCH_SIZE`, `EMBEDDING_BATCH_MAX_CHARS`). Limits: `INDEX_MAX_FILES` / `INDEX_MAX_FILE_BYTES` / `INDEX_MAX_TOTAL_CHARS`. If RAG is disabled (no embedding model), returns `enabled=false` without error.

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

# Product eval harness (gated separately from WP_LIVE_LLM)
# Retrieval: recall@k via mistral-embed. Answer judge: remote mistral-small-latest
# grades a fixed golden answer 1-5 against a rubric (LLM-as-judge; not AgentLoop).
# Key: MISTRAL_API_KEY or LLM_DEFAULT_API_KEY (e.g. monorepo root .env).
WP_EVAL=1 .venv/bin/pytest tests/test_eval_live.py -q
```

Coverage: agent, scoped memory, plugins, documents, audit, attachments, RAG, HTTP SSE. See [docs/testing.md](../../docs/testing.md). Eval cases and judge details: [evals/README.md](evals/README.md).

**Provider sets & reasoning:** catalogue-driven model/reasoning routing, Mistral `none`/`high` clamp. Details: [docs/provider-sets-reasoning.md](../../docs/provider-sets-reasoning.md). Focused tests: `tests/test_provider_sets.py`, `tests/test_llm_config.py`.

## Current limits

- Agent: [Pydantic AI](https://ai.pydantic.dev/) (native models). Routing via `OpenAIChatModel` + `AnthropicModel`.
- RAG embeddings: LiteLLM (`litellm.aembedding`). Disabled if `LLM_EMBEDDING_MODEL` is empty → substring search fallback.
- Memory injection ranking: hybrid semantic + lexical (`memory_ranking.py`); LRU embedding cache per sidecar process (`MEMORY_EMBEDDING_CACHE_MAX_ENTRIES`).
- Extraction: text PDF, Word, Excel, PowerPoint. OCR / scanned PDFs out of initial scope.
- Durable (Temporal/Inngest): deferred.
