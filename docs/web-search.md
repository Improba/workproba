# Core web search (`web_search`)

> **Last updated:** 15 Jul 2026  
> **Status:** implemented (Mistral path); Tavily fallback and provider-set capabilities pending

The **`web_search`** agent tool lets the assistant look up **recent or external facts** on the public web and return **citable sources**. It is a **core agent tool**, not a plugin. The browser plugin (`workproba.browser`) remains separate for page interaction (click, type, auth flows).

## When it is available

The tool is registered on every agent build, but **runtime execution** requires:

| Condition | Effect |
|---|---|
| Active provider set uses **Mistral** chat (`provider_set.chat.provider == "mistral"`) | Backend can call Mistral Conversations |
| **`permissions_network`** is `true` | Network guard passes |
| Both missing | `ModelRetry` with `errors.web_search_unavailable` or `errors.web_search_locked` |

No plugin toggle. No entry in Settings → Plugins. Switching from Mistral to Ollama (or another provider) disables web search until Tavily fallback is implemented (T-V2-WS-3).

## Use cases vs other tools

| Need | Tool |
|---|---|
| Facts, news, prices, external comparison | `web_search` |
| Fill forms, click, read behind login | `workproba.browser` (plugin) |
| Project files and space memory | `search_kb` (core) |

## Architecture

The main chat loop stays on **Pydantic AI + Chat Completions** (Mistral OpenAI-compatible). Each `web_search` call delegates to a **separate Mistral Conversations request** with the native `web_search` connector:

```
User message
  → AgentLoop (Chat Completions, core tools + plugins)
       → web_search(query)
            → search_web() in app/web_search/engine.py
                 └─ mistral → POST /v1/conversations { tools: [{ type: web_search }] }
            ← normalized JSON { query, results[], citations[], usage }
       ← result injected into agent loop
  → model synthesizes answer with sources
```

**Why not move the whole chat to Mistral Conversations?**

- Streaming, thinking, confirmation gates, and plugins are tuned for Chat Completions.
- Mistral Conversations/Agents API is still beta and does not replace the in-house agent loop.
- Delegation isolates search cost and latency (one Conversations call per `web_search`, not per turn).

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
    mistral_backend.py    # POST https://api.mistral.ai/v1/conversations
    errors.py             # WebSearchError, web_search_error_detail
    support.py            # web_search_available(context)
```

Front (unchanged from MVP):

- `front/src/utils/toolCallDetails.ts` — query, count, backend, URLs
- `front/src/utils/toolCallHumanLabel.ts` — fallback label
- i18n keys `toolCalls.webSearch*`

## Agent tool contract

```python
@agent.tool
async def web_search(ctx: RunContext[ToolDeps], query: str) -> dict[str, Any]:
    """Search the public web for up-to-date information."""
```

Guards (in order):

1. `permissions_network` → else `web_search_locked`
2. `web_search_available(context)` (Mistral + network) → else `web_search_unavailable`
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

## Mistral backend (default)

Backends are **pluggable per provider** via `backends.py` (`register_web_search_backend`). Mistral is registered at import time in `engine.py`. A backend may return a finalized payload (`query` + `results`) for tests or alternate connectors.

| Parameter | Value |
|---|---|
| Endpoint | `POST https://api.mistral.ai/v1/conversations` |
| Auth | Provider set `chat.api_key` |
| Tool | `{"type": "web_search"}` (premium variant planned for advanced mode) |
| Model | Active chat model (`mistral-small-latest`, …) |
| Streaming | `false` (sync sidecar call, default timeout 45 s) |

Response parsing walks `outputs`:

1. `tool.execution` with `name == "web_search"` — execution metadata
2. `message.output` chunks — aggregate `type: text` snippets; collect `type: tool_reference` as `{ title, url, source }`

Deduplicate by URL. Cap at `limits.web_search_max_results` (default 8).

Indicative Mistral connector pricing: ~$30 / 1,000 `web_search` calls (+ connector tokens). See [Mistral Websearch docs](https://docs.mistral.ai/agents/connectors/websearch).

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
| `web_search_timeout_s` | 45 | httpx timeout |
| `web_search_max_per_turn` | 3 | `ModelRetry` beyond this |
| `web_search_query_max_chars` | 500 | Query truncation |

## Security

| Rule | Implementation |
|---|---|
| Network permission | `permissions_network` required |
| Provider | Mistral only today (`web_search_available`) |
| Locked / no network | Same network guard pattern as browser tools |
| Outbound data | Query sent to Mistral; disclose in advanced mode |
| No persistent cache | Results not indexed into memory by default |

## Tests

```bash
cd workproba/services/ai
uv run pytest tests/test_web_search_tool.py \
             tests/test_web_search_mistral.py \
             tests/test_web_search_mistral_backend.py \
             tests/test_web_search_backends.py -q
```

| Area | File |
|---|---|
| Tool guards, limits, human_summary | `tests/test_web_search_tool.py` |
| Mistral response parsing | `tests/test_web_search_mistral.py` |
| HTTP backend (mocked httpx) | `tests/test_web_search_mistral_backend.py` |
| Provider registry | `tests/test_web_search_backends.py` |
| Fixture | `tests/fixtures/mistral_web_search_response.py` |

Front: `front/test/unit/utils/toolCallDetails.spec.ts`, `toolCallHumanLabel.spec.ts`.

Optional live test: Mistral Conversations + real key (same pattern as `test_live_mistral.py`).

## Migration note (plugin → core)

An initial implementation shipped as opt-in plugin `workproba.web_search`. Product decision: **always expose the tool when Mistral + network**, without a plugin toggle. The plugin package was removed; logic lives under `app/web_search/`. Tauri builtin plugin manifests are back to four plugins (projet, personas, browser, cloud).

## Backlog

| Task | Description |
|---|---|
| T-V2-WS-3 | Tavily fallback for non-Mistral sets (e.g. Ollama) |
| T-V2-WS-4 | `capabilities.web_search` on provider sets + UI badges |
| T-V2-WS-5 | Audit log + inline citation chips in assistant messages (audit via effect gate partial) |

Full spec and implementation plan: [workproba-improba/roadmaps/web-search.md](../../workproba-improba/roadmaps/web-search.md).

## References

- [Mistral Websearch](https://docs.mistral.ai/agents/connectors/websearch)
- [Mistral Agents & Conversations](https://docs.mistral.ai/studio-api/agents/agents-api)
- Browser plugin (interaction): [browser.md](./browser.md)
