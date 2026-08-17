# Core web search (`web_search`)

> **Last updated:** 17/08/2026  
> **Status:** implemented (Mistral BYOK + Improba Cloud `/search/v1`); Tavily fallback for Ollama

The **`web_search`** agent tool lets the assistant look up **recent or external facts** on the public web and return **citable sources**. It is a **core agent tool**, not a plugin and **not a managed connector**. The browser plugin (`workproba.browser`) remains separate for page interaction (click, type, auth flows).

Mistral does **not** expose a standalone Search API (`POST /search`). Public web search is a built-in **Conversations/Agents tool** (`web_search` / `web_search_premium`). Workproba wraps a one-shot Conversations call and normalizes citations. On Improba Cloud, that call is made **by the control plane** (org Mistral key), never by the desktop DeviceBearer against `api.mistral.ai`.

## When it is available

The tool is registered on every agent build. Runtime execution requires `permissions_network` **and** a usable backend:

| Active set | Backend | Ready when |
|---|---|---|
| **Improba Cloud** (`auth_mode: device_bearer`) | `POST {control_plane}/search/v1` | Cloud enrolled (DeviceBearer + `base_url`) |
| **Mistral** (API key) | `POST https://api.mistral.ai/v1/conversations` | Chat API key present |
| **Ollama** / other | Tavily `POST /search` | `TAVILY_API_KEY` (or `secrets/tavily`) |

Missing network → `errors.web_search_locked`. Missing backend / not enrolled → `errors.web_search_unavailable`.

No plugin toggle. Not a Capabilities card. Switching engine changes the backend; Cloud users keep search without a Tavily key.

## Use cases vs other tools

| Need | Tool |
|---|---|
| Facts, news, prices, external comparison | `web_search` |
| Fill forms, click, read behind login | `workproba.browser` (plugin) |
| Project files and space memory | `search_kb` (core) |
| Ihora / Pennylane / GazFlow | `invoke_managed_connector` (managed capabilities) |

## Architecture

The main chat loop stays on **Pydantic AI + Chat Completions**. Each `web_search` call is a **delegated retrieval**, not a second agent loop on the desktop:

```
User message
  → AgentLoop (Chat Completions, core tools + plugins)
       → web_search(query)
            → search_web() in app/web_search/engine.py
                 ├─ Cloud (device_bearer) → POST {cp}/search/v1
                 │                            └─ Cloud → POST api.mistral.ai/v1/conversations
                 ├─ Mistral BYOK            → POST api.mistral.ai/v1/conversations
                 └─ Ollama                  → Tavily (if key)
            ← normalized JSON { query, results[], citations[], usage }
       ← result injected into agent loop
  → model synthesizes answer with sources
```

**Why not move the whole chat to Mistral Conversations?**

- Streaming, thinking, confirmation gates, and plugins are tuned for Chat Completions.
- Mistral Conversations/Agents API is still beta and does not replace the in-house agent loop.
- Delegation isolates search cost and latency (one Conversations call per `web_search`, not per turn).
- Cloud `/llm/v1` stays a Chat Completions pass-through (frozen). Search is a **separate** additive surface (`/search/v1`).

**Why not a managed connector?** Search is part of the LLM offering (same DeviceBearer, same org quota). It has no allowlist, secrets org, or `POST /connectors/:id/invoke`. Mixing it with Ihora/Pennylane would break fail-closed connector isolation.

## Code layout

```
workproba/services/ai/app/
  agent/tools.py          # @agent.tool web_search + web_search_note_prompt
  agent/human.py          # build_human_summary branch for web_search
  i18n.py                 # human.web_search.*, errors.web_search_*, tools.web_search_note
  limits.py               # web_search_max_results, timeout, max_per_turn, query_max_chars
  web_search/
    __init__.py
    config.py
    backends.py           # provider registry (register_web_search_backend)
    engine.py             # search_web, parse_mistral_conversation_response, set_search_backend
    mistral_backend.py    # POST https://api.mistral.ai/v1/conversations (BYOK)
    cloud_backend.py      # POST {cp}/search/v1 (DeviceBearer)
    tavily_backend.py     # fallback Ollama / non-Mistral
    errors.py             # WebSearchError, web_search_error_detail
    support.py            # web_search_available(context)
```

Cloud (not a connector):

```
workproba-cloud/api/src/core/search/
  search.controller.ts    # POST /search/v1  DeviceBearer
  search.service.ts       # quota + Conversations one-shot
  search.parse.ts         # same citation contract as the sidecar
  search.dto.ts           # query, max_results?, premium?, model?
```

Front:

- `front/src/utils/toolCallDetails.ts` — query, count, backend, URLs
- `front/src/utils/toolCallHumanLabel.ts` — fallback label
- i18n keys `toolCalls.webSearch*`
- Provider set Improba Cloud: `capabilities.webSearch: true`

## Agent tool contract

```python
@agent.tool
async def web_search(ctx: RunContext[ToolDeps], query: str) -> dict[str, Any]:
    """Search the public web for up-to-date information."""
```

Guards (in order):

1. `permissions_network` → else `web_search_locked`
2. `web_search_available(context)` (Cloud enrolled / Mistral / Tavily) → else `web_search_unavailable`
3. `web_search_max_per_turn` → else `errors.web_search_limit_reached`

Normalized result shape:

```json
{
  "query": "weather Paris tomorrow",
  "count": 3,
  "backend": "mistral",
  "results": [
    { "title": "…", "url": "https://…", "snippet": "…", "source": "brave" }
  ],
  "citations": [
    { "title": "…", "url": "https://…", "source": "brave" }
  ],
  "usage": {
    "connector_calls": 1,
    "connector_tokens": 4200,
    "estimated_cost_usd": 0.03
  }
}
```

`results` are snippets for the model; `citations` are structured sources for the UI (often the same after URL deduplication).

## Mistral BYOK backend

Direct API key sets call Conversations themselves. Backends are **pluggable per provider** via `backends.py`. Mistral, Cloud and Tavily/Ollama are registered at import time in `engine.py`.

| Parameter | Value |
|---|---|
| Endpoint | `POST https://api.mistral.ai/v1/conversations` |
| Auth | Provider set `chat.api_key` |
| Tool | `{"type": "web_search"}` (premium variant planned for advanced mode) |
| Model | Active chat model (`mistral-small-latest`, …) |
| Streaming | `false` (sync sidecar call, default timeout 45 s) |

Response parsing walks `outputs`:

1. `tool.execution` with `name == "web_search"` — execution metadata
2. `message.output` chunks — aggregate `type: text` snippets; collect `type: tool_reference` as `{ title, url, source }` (http/https only)

Deduplicate by URL. Cap at `limits.web_search_max_results` (default 8).

Indicative Mistral connector pricing: ~$30 / 1,000 `web_search` calls (+ connector tokens). See [Mistral Websearch docs](https://docs.mistral.ai/agents/connectors/websearch).

## Improba Cloud backend (`POST /search/v1`)

The desktop **never** sends the DeviceBearer to `api.mistral.ai` and **never** calls `/v1/conversations` through `/llm/v1`.

| Parameter | Value |
|---|---|
| Endpoint | `POST {control_plane}/search/v1` |
| Auth | DeviceBearer (`wp_dev_*`) |
| Body | `{ query, max_results?, premium?, model? }` |
| Response | Same normalized JSON as the agent tool (`backend` from Cloud is `mistral`; sidecar records `cloud`) |
| Quota | Same org LLM quota (`assertAllowed` + `recordUsage` tokens + 1 request) |
| Upstream | Control plane `MISTRAL_API_KEY` → `POST /v1/conversations` |
| Default model | `mistral-small-latest` unless `model` is in the chat allowlist |

Machine codes: `query_empty`, `quota_exceeded`, `search_rate_limit`, `mistral_timeout`, `mistral_unavailable`, `search_bad_response`. Sidecar maps them to `errors.web_search_*`.

Empty result sets are `200` with `count: 0`, not an error.

## SSE and human summaries

No new SSE event types. Reuses `tool_call_start` / `tool_call_result` via `AgentLoop._iter_tool_stream` and `build_human_summary()`.

| i18n key | EN (guided mode) |
|---|---|
| `human.web_search.will` | Searching the web for "{query}" |
| `human.web_search.count.one` | 1 web result for "{query}" |
| `human.web_search.count.many` | {n} web results for "{query}" |
| `human.web_search.empty` | No web results for "{query}" |
| `human.web_search.cannot` | Web search failed for "{query}" |

Guided mode must not expose "connector", "API", or "Mistral" in user-facing strings.

## System prompt

When `web_search_available(context)`, `web_search_note_prompt` injects:

> If the user asks for recent or external information, use `web_search`. For project files and space memory, use `search_kb` instead.

## Limits

Defined in `app/limits.py`:

| Limit | Default | Notes |
|---|---|---|
| `web_search_max_results` | 8 | Truncate after parsing |
| `web_search_timeout_s` | 45 | httpx timeout (Cloud waits +5 s so `/search/v1` can return 504) |
| `web_search_max_per_turn` | 3 | `ModelRetry` beyond this |
| `web_search_query_max_chars` | 500 | Query truncation |

## Security

| Rule | Implementation |
|---|---|
| Network permission | `permissions_network` required |
| Cloud | DeviceBearer + enrolled control plane; query never sent to Mistral from the desktop |
| BYOK Mistral | Direct Conversations with the user API key |
| Ollama / other | Tavily only if a key is configured |
| Locked / no network | Same network guard pattern as browser tools |
| Outbound data | Query sent to Mistral (Cloud org key or BYOK); disclose in advanced mode |
| Not a connector | No allowlist, no `invoke`, no org connector secrets |
| No persistent cache | Results not indexed into memory by default |

## Tests

```bash
cd workproba/services/ai
uv run pytest tests/test_web_search_tool.py \
             tests/test_web_search_mistral.py \
             tests/test_web_search_mistral_backend.py \
             tests/test_web_search_backends.py \
             tests/test_web_search_cloud.py -q

cd workproba-cloud/api
yarn test:unit test/unit/search.parse.spec.ts \
               test/unit/search.service.spec.ts \
               test/unit/search.controller.spec.ts
```

| Area | File |
|---|---|
| Tool guards, limits, human_summary | `tests/test_web_search_tool.py` |
| Mistral response parsing | `tests/test_web_search_mistral.py` |
| HTTP backend (mocked httpx) | `tests/test_web_search_mistral_backend.py` |
| Provider registry + Cloud availability | `tests/test_web_search_backends.py` |
| Cloud `/search/v1` client | `tests/test_web_search_cloud.py` |
| Cloud parse / service / HTTP | `workproba-cloud/api/test/unit/search.*.spec.ts` |
| Fixture | `tests/fixtures/mistral_web_search_response.py` |

Front: `front/test/unit/utils/toolCallDetails.spec.ts`, `toolCallHumanLabel.spec.ts`, `providerSetsCapabilities.spec.ts`.

Optional live test: Mistral Conversations + real key (same pattern as `test_live_mistral.py`).

## Migration note (plugin → core)

An initial implementation shipped as opt-in plugin `workproba.web_search`. Product decision: **always expose the tool when a backend is ready + network**, without a plugin toggle. The plugin package was removed; logic lives under `app/web_search/`. Tauri builtin plugin manifests are back to four plugins (projet, personas, browser, cloud).

## Backlog

| Task | Description |
|---|---|
| T-V2-WS-3 | Tavily fallback for non-Mistral sets (**delivered** for Ollama when a key is present) |
| T-V2-WS-4 | `capabilities.web_search` on provider sets + UI badges (**delivered** including Improba Cloud) |
| T-V2-WS-5 | Audit log + inline citation chips in assistant messages (**delivered**: audit + inline source pills from `web_search` tool results) |
| T-V2-WS-6 | Optional retrieval-only Cloud backend (Brave/Tavily managé) without nested Conversations |

Full spec and implementation plan: [workproba-improba/roadmaps/web-search.md](../../workproba-improba/roadmaps/web-search.md).

## References

- [Mistral Websearch](https://docs.mistral.ai/agents/connectors/websearch)
- [Mistral Agents & Conversations](https://docs.mistral.ai/studio-api/agents/agents-api)
- Browser plugin (interaction): [browser.md](./browser.md)
- Cloud search endpoint: [workproba-cloud/docs/control-plane-mvp-stubs.md](../../workproba-cloud/docs/control-plane-mvp-stubs.md)

