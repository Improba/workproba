# Browser plugin (`workproba.browser`)

> **Capability (guided UI):** Navigation web — right panel tab when active. Hub Capacités for discovery (**V2.2 PR 2–3**). See [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md).

> **Last updated:** 15 Jul 2026  
> **Status:** shipped (experimental, opt-in, disabled by default), P2 differentiation priority

The Browser plugin lets the AI assistant browse the web (http/https), interact with pages, and show the user what it is doing. It is **not** a primary browser or a native Chrome webview: it runs a **Playwright Chromium headless** session with visual feedback via JPEG screenshots and an accessibility tree.

## Enabling the plugin

1. **Settings → Plugins**: enable `workproba.browser`.
2. **First activation**: onboarding notification (Playwright + Chromium download, ~30 s, network required).
3. **Locked mode (enterprise)**: IT can deny the plugin (`permissions_network: false` → HTTP 403 on browser endpoints and agent tools blocked).

Plugin data: `{app_data}/plugins/workproba.browser/` (isolated Chromium profile).

## Architecture

```
User (chat)
    │
    ▼
useChatStream ──SSE──► POST /agent/turn
    │                      │
    │                      ▼
    │                 Pydantic AI agent
    │                 (browser_* tools if plugin active)
    │                      │
    │                      ▼
    │                 BrowserEngine (Playwright headless)
    │                      │
    ├── onBrowserToolCall ◄┘ tool_call_result (success only)
    │
    ▼
useBrowser.applyToolResult ──► BrowserPanel (screenshot + highlight)

Manual navigation (URL bar):
BrowserPanel ──► aiSidecar ──► POST /plugins/browser/*
                           └──► same BrowserEngine (shared session)
```

**Important:** Tauri/Rust is not in the browser loop (no dedicated commands). The Python sidecar listens on `127.0.0.1:8765`.

## Agent tools (8)

Registered in `manifest.py` and exposed only when `workproba.browser` is in `active_plugins`:

| Tool | Purpose |
|---|---|
| `browser_navigate` | Open a URL (http/https) |
| `browser_click` | Click an accessibility ref from the snapshot (`e42`, …) |
| `browser_type` | Type text into a field (ref) |
| `browser_scroll` | Scroll (direction + optional ref) |
| `browser_press` | Keyboard key (Enter, Tab, …) |
| `browser_extract` | Extract text via CSS selector |
| `browser_back` | Previous page |
| `browser_forward` | Next page |

The model receives the **YAML snapshot** (Playwright a11y tree) only. The **JPEG screenshot** is sent to the front panel via SSE (`enrich_browser_tool_result_for_sse`), never in model history or session persistence.

### Model vs UI payload

| Layer | `screenshot_b64` | Source |
|---|---|---|
| Tool return (model) | **Excluded** | `plugin.py` |
| SSE `tool_call_result` | **Included** on success | `loop.py` + `last_tool_ui_snapshot` |
| Chat history → model | **Stripped** | `toPythonHistory`, `loop._strip_screenshot_from_tool_history_content` |
| Session DB persistence | **Stripped** | `sanitizeChatMessagesForPersistence` in `ChatPage` |

On tool **errors** (`is_error: true`), the front does not call `onBrowserToolCall` and SSE enrichment does not inject a stale screenshot.

## HTTP endpoints (sidecar)

Requires `X-Internal-Secret`. Security context: `settings_locked`, `permissions_network`.

| Method | Route | Description |
|---|---|---|
| POST | `/plugins/browser/navigate` | Navigate + snapshot |
| POST | `/plugins/browser/snapshot` | Capture current state |
| POST | `/plugins/browser/action` | click, type, scroll, press, back, forward, extract |
| POST | `/plugins/browser/close` | Close session (`close_engine_async`) |
| GET | `/plugins/browser/status` | `{ active, url, title }` |

### Enriched snapshot payload (Phases 2–3)

Navigate / snapshot / action responses include:

```json
{
  "title": "...",
  "url": "https://...",
  "snapshot_yaml": "- button \"Buy\" [ref=e9]",
  "screenshot_b64": "...",
  "viewport": { "width": 1280, "height": 720 },
  "action_ref": "e9",
  "action_bbox": { "x": 120, "y": 340, "width": 80, "height": 32 }
}
```

`action_ref` / `action_bbox` are present after click, type, or scroll with ref. Coordinates are viewport-relative (1280×720), aligned with the screenshot.

Screenshot size is capped at 2 MB (`MAX_SCREENSHOT_BYTES`). If a capture exceeds the limit, quality is reduced iteratively; otherwise the screenshot is omitted (no truncated JPEG).

## UI: Browser panel

Files: `BrowserPanel.vue`, `useBrowser.ts`, slot `workproba.browser:right_panel`.

| Feature | Behavior |
|---|---|
| Screenshot | JPEG base64, refreshed on each action |
| Live view | Silent snapshot polling every 1.2 s during an agent turn (`streaming`) |
| Highlight | Accent rectangle on `action_bbox`, 2.5 s fade |
| Action badge | `human_summary` label at bottom of screenshot |
| Pause piloting | “Stop piloting” → `browser_pilotage_paused: true` in `/agent/turn` |
| Manual navigation | URL bar + back/forward/reload (still works when piloting is paused) |

## Critical wiring

### 1. Agent → panel (tool result)

```
SSE tool_call_result (name=browser_*, success)
  → useChatStream.applyEvent
  → ChatPage.onBrowserToolCall
  → useBrowser.applyToolResult (stops live refresh, then restarts)
  → applySnapshotResult + lastAiAction + highlight
  → BrowserPanel (reactive)
```

Recognized tools: `front/src/utils/browserTools.ts` (aligned with `manifest.py` TOOLS).

### 2. Piloting pause

```
BrowserPanel.pausePilotage()
  → pilotagePaused = true
  → buildAgentTurnPayload(..., browserPilotagePaused: true)
  → AgentTurnRequest.browser_pilotage_paused
  → ToolContext.browser_pilotage_paused
  → plugin._assert_browser_allowed → ModelRetry
```

**Manual** HTTP navigation is not blocked (by design).

**Known limitation:** pause takes effect on the **next** agent turn (`browser_pilotage_paused` is read when `/agent/turn` starts). During an in-flight stream, live refresh stops immediately, but `browser_*` tools already queued in the same turn may still run. For a full immediate stop, also use chat **Stop**.

### 3. Live view

```
ChatPage watch(streaming)
  → setAgentTurnActive(isStreaming)
  → syncLiveRefresh() if session active and piloting not paused
  → silentSnapshotFn() every 1.2 s (skipped when !active)
```

Live refresh is paused while `applyToolResult` runs to avoid racing agent actions. SSE enrichment uses `last_tool_ui_snapshot` (frozen at tool execution) instead of the polling snapshot.

### 4. Agent navigation audit

```
browser_navigate tool + workspace_data_dir
  → engine.navigate(audit_app_data, audit_actor="agent")
  → log_event("browser.navigate", ...)
```

## Security

| Guard | Detail |
|---|---|
| URLs | http/https only (`validate_navigation_url`) |
| Sandbox | Headless Chromium, isolated plugin profile |
| Cookies/storage | Not exposed to the model (textual snapshot + JPEG to UI only) |
| Locked mode | HTTP 403 + agent tools denied without `permissions_network` |
| Action timeout | 30 s (`ACTION_TIMEOUT_MS`) |
| Screenshot size | Max 2 MB (`MAX_SCREENSHOT_BYTES`) |

## Source files

| Layer | Files |
|---|---|
| Engine | `services/ai/app/plugins/workproba_browser/browser.py` |
| Agent tools | `services/ai/app/plugins/workproba_browser/plugin.py` |
| Manifest | `services/ai/app/plugins/workproba_browser/manifest.py` |
| HTTP | `services/ai/app/main.py` (routes `/plugins/browser/*`) |
| Registry | `services/ai/app/plugins/registry.py` |
| Front composable | `front/src/composables/useBrowser.ts` |
| Front panel | `front/src/components/browser/BrowserPanel.vue` |
| Front utils | `front/src/utils/browserTools.ts`, `browserHighlight.ts`, `browserActionLabel.ts` |
| Chat stream | `front/src/composables/useChatStream.ts`, `front/src/pages/chat/ChatPage.vue` |
| Tauri (activation) | `desktop/src-tauri/src/commands/plugins.rs` |

## Tests

```bash
# Sidecar (38 browser tests)
cd services/ai && uv run pytest tests/test_plugin_browser.py -q

# Front (composable, highlight, aiSidecar, SSE wiring)
cd front && npm run test:unit -- test/unit/composables/useBrowser.spec.ts \
  test/unit/composables/useChatStream.spec.ts \
  test/unit/utils/browserHighlight.spec.ts \
  test/unit/utils/browserActionLabel.spec.ts \
  test/unit/services/aiSidecar.browser.spec.ts
```

Main coverage: forbidden URLs, locked mode, 8 agent tools, navigate audit, bbox on click, screenshot limits, piloting pause, SSE front wiring, history sanitization, error path (no panel update on `is_error`).

## Known residual risks (non-blocking)

| Risk | Notes |
|---|---|
| Pause mid-turn | Tools already started in the current turn may finish; combine with chat Stop |
| Playwright concurrency | Live polling may overlap manual actions; silent errors are swallowed |
| Phase 4 (CDP / user Chrome SSO) | Not implemented; optional enterprise roadmap |

## Roadmap (residual)

| Item | Status |
|---|---|
| Session navigation history (clearable) | Not shipped (T-V2-20 debt) |
| Native Tauri live webview | Not chosen for MVP (dual engine) |
| CDP / user Chrome session (SSO) | Optional Phase 4 enterprise |
| External MCP browser | Out of scope for non-coder product |

## See also

- [plugins.md](./plugins.md): global plugin system
- [services/ai/README.md](../services/ai/README.md): sidecar endpoint catalog
- Roadmap: `workproba-improba/roadmaps/cibles-vagues.md` (Wave 10)
