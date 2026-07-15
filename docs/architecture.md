# Workproba architecture

> **Last updated:** 15/07/2026 (V2.2 PR 1–3)

## Overview

**Workproba** is a desktop application (macOS, Linux, Windows): the user **opens a space** (a local folder on disk); the agent manipulates files in place, relies on locally indexed memory, and calls **fixed, controlled tools** (Office writers, file ops, RAG). Workproba V2 **does not execute arbitrary user- or model-generated code** (`run_code` is dormant).

> **Terminology:** The user-facing concept is **Space**. Internal code and `registry.json` still use `workspace_id` / `ws_…` and a `workspaces` array. Metadata paths use `{app_data}/spaces/`.

Detailed documentation: [desktop.md](./desktop.md), [workspace-storage.md](./workspace-storage.md).

## Stack

| Layer | Technology | Role |
|---|---|---|
| Desktop shell | Tauri 2 (Rust) | Window, native filesystem, per-space storage, packaging |
| Frontend | Quasar 2 + Vue 3 | Webview UI (chat, files) |
| AI core | Python 3.12 + FastAPI (sidecar) | Agent loop, extraction, RAG, fixed tool implementations |
| Local data | `{app_data}/` (spaces, user, plugins, audit) | Conversations, versions, memory, plugins |
| Agent | Pydantic AI (native models) | Type-safe chat/agent, tools, streaming |
| LLM | OpenAIChatModel (OpenAI-compat) + AnthropicModel | Local Ollama, Mistral cloud, vLLM, OpenAI, Anthropic |
| RAG embeddings | LiteLLM (`aembedding`) | Ollama, Mistral, OpenAI… |
| RAG | SQLite + sqlite-vec (`memory.db`) | Embeddings + vector search per project; explicit user/project memories |
| Extraction | pdfplumber, python-docx, openpyxl, python-pptx | Digital PDF/Office (OCR out of initial scope) |

## Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Quasar (Tauri webview)                                         │
└──────────────┬─────────────────────────────┬────────────────────┘
               │ HTTP SSE                      │ Tauri invoke
               ▼                               ▼
┌──────────────────────────┐       ┌─────────────────────────────┐
│  Python sidecar :8765    │       │  Tauri / Rust               │
└───────────┬──────────────┘       └──────────────┬──────────────┘
            ▼                                     ▼
┌──────────────────────────┐       ┌─────────────────────────────┐
│  LLM (Ollama / cloud)    │       │  User project folder        │
└──────────────────────────┘       └─────────────────────────────┘
```

## Message flow

1. The user opens a space (folder picker; UI: "Open a space").
2. Quasar sends the message via SSE to `127.0.0.1:8765`.
3. Python runs the agent loop (LLM, fixed file/Office tools; `run_code` not exposed in V2).
4. Sessions are persisted in `{app_data}/spaces/{id}/.workproba/`.
5. Each turn: the sidecar prepares memories and session candidates once, ranks them (hybrid semantic + lexical when an embedding model is configured, with an LRU embedding cache), then injects explicit memories and relevant prior session summaries; project RAG is available via `search_kb`. Session summaries are promoted to shared project memory in the background (see [memory.md](./memory.md)).

## Human approval and work events

### Human Approval Gate (effect-oriented)

Before executing a sensitive tool, the agent classifies the intended **effect** (not the raw tool name) and waits for user approval.

| Effect type | Typical tools | User-facing example |
|---|---|---|
| `create` / `modify` | `write_docx`, `write_pdf`, `generate_document` | "I will modify: Rapport.docx" |
| `publish` | `publish_artifact` | "I will publish: memo.pdf in Project X" |
| `network_access` | `web_search`, `browser_*` | "I will access the network: …" |
| `code_execute` | `run_code` | "I will execute code" |
| `external_send` | `sync_to_cloud` | "I will send externally: …" |

Read-only tools (`read_document`, `list_files`, `remember`, `propose_plan`, personas, etc.) are not gated. Unknown plugin tools are not auto-gated (conservative default).

**Backend flow:**

1. `classify_effect()` (`app/agent/effects.py`) builds an `EffectProposal` (effect, targets, protections).
2. `ConfirmationGate.request_effect()` emits SSE `confirmation_request` with `headline` and `protection_labels` (localized via `app/i18n.py`).
3. The front shows `ConfirmationCard.vue`; the user approves or denies via `POST /agent/confirm`.
4. On **approve**: the tool runs. On **deny** or **timeout** (5 min): `ModelRetry` informs the model (`workproba:approval_denied` / `workproba:approval_timeout` markers).
5. Optional audit: `approval.requested` / `approval.resolved` in `{app_data}/audit/`.

Protections shown on the card include: preview available, automatic version before modify, no network, no external send (when applicable).

### Work Event Bus (`work_*`)

Additive SSE events decoupled from per-tool UI cards. One `work_id` per agent turn (currently = `turn_id`).

| Event | Role |
|---|---|
| `work_started` | Turn begins (objective summary) |
| `work_contribution` | Coarse capability/perspective label while a tool runs |
| `work_completed` | Turn finished successfully |
| `work_failed` | Terminal failure (timeout, unrecoverable error) |

Implementation: `app/agent/work_events.py`. Labels are localized (`work.capability.*`, `work.perspective.*`). Each event carries `turn_id`, `session_id`, and `work_id` (currently equal to `turn_id`) for audit correlation and front-side tracing (`useChatStream.streamCorrelation`).

## UI shell (desktop layout)

The main layout (`WorkprobaLayout.vue`) organizes the screen:

```
WorkprobaTitleBar          ← Capabilities hub button, engine chip, panel toggles
├── WorkspaceSidebar (left, responsive rail mode)
├── central zone (router-view: chat, settings, onboarding, crossed-regards view)
├── RightPanel (right, Ctrl+B): Files · Preview · active capability tabs only
├── SideChatPanel (Ctrl+Shift+L): Regards métier opinion/discussion
└── CapabilitiesDrawer (non-modal, Escape to close): discover / activate capabilities
```

**Sidebar** (`WorkspaceSidebar.vue`): spaces → conversations tree, renameable display titles, streaming indicator, user profile, memory and model settings access.

**Right panel** (`RightPanel.vue`): file explorer, document preview, **plugin tabs for active capabilities only** (Project, Browser when enabled). Cloud tab hidden in guided mode. Inactive modules are discoverable via the Capabilities hub, not as ghost tabs.

**Chat** (`ChatView.vue`): pill composer, "+" menu (attachments only), compact **Regards** chip when personas active, model/reasoning control, file drag-and-drop.

**Capabilities** (`useCapabilities.ts`, `useShellSurfaces.ts`): product catalog maps capabilities to plugin activation (Tauri) and shell navigation (right panel tab, side chat). `activateAndOpen()` activates plugins then opens the documented home surface.

## Attachments and document preview

- **Attachments**: stored in `{workspace_data_dir}/attachments/{session_id}/{attachment_id}/`. Reprocess OCR/vision via `POST /agent/reprocess-attachment`.
- **HTML/text preview**: sidecar `GET /documents/preview` (content rendered in the webview).
- **Image preview**: Tauri `convertFileSrc` with `protocol-asset` feature (`tauri.conf.json` → `assetProtocol`).
- **Diff before write**: `POST /documents/preview-change`.

## Plugins and capabilities

Four builtin plugins; guided UX presents them as **activatable capabilities** (Regards métier, Projets et livrables, Navigation web, Synchronisation). Technical plugin details in advanced Settings → Extensions. See [plugins.md](./plugins.md) and [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md).

**File versions** (T-V2-15): snapshots live under `{space}/versions/`; the sidecar exposes `GET /versions`, `POST /versions/restore`, and optional `POST /versions/purge` (keep last N, default 20, and/or drop entries older than X days). The right-panel **Versions** tab offers restore and manual cleanup.

**Remote plugins** (T-V3-CP-3 scaffold): typed **`RemoteCapabilityGateway`** in the sidecar (`capability:remote`) delegates identity to remote capabilities with payload minimization, timeouts, and audit; local stub rejects unless explicitly allowed.

## Active modules

| Folder | Role |
|---|---|
| `desktop/` | Tauri shell |
| `front/` | Quasar UI |
| `services/ai/` | Python sidecar |
| `legacy/` | Former NestJS web stack (archived) |

## See also

- [desktop.md](./desktop.md)
- [intention.md](./intention.md)
- [stack.md](./stack.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)

## Managing LLM models from the app

Model access (provider, model, base URL, **API key**) is configured from
the app: **"AI Models"** screen (settings icon at sidebar footer, route `/settings/models`).

- **Storage**: `{app_data}/settings.json` (managed by Tauri/Rust, commands
  `get_app_settings` / `save_app_settings`). Key stored in plain text on the local
  machine, like other Workproba metadata. Not in the client folder.
- **Multiple providers** configurable; one active provider for **chat**, one
  for **RAG embeddings** (the key is shared between chat and embeddings for the
  same entry). **Test** button validates the key via `GET /models` (zero cost).
- **Transit**: on each agent turn, the front sends the active **`provider_set`**
  (with session overrides: model and reasoning per conversation) in the
  `/agent/turn` payload. Without a set, fallback to `llm_provider_config` +
  `embedding_config` (legacy). The sidecar always prioritizes `provider_set` in
  `resolve_llm_config`. Environment variables `LLM_DEFAULT_*` /
  `LLM_EMBEDDING_*` serve only as **dev fallback**.
- **API key**: for cloud engines (e.g. Mistral), the key is entered in
  Settings → AI Models and stored in `set.chat.apiKey`. If missing, the
  front blocks send and the sidecar returns `api_key_missing`. The
  `api_key_ref` field on builtin sets is an internal marker; only `api_key`
  matters at runtime.
- The key can be changed at any time from the app, without touching `.env`.

## Model and reasoning per conversation

The "AI Models" screen chooses a **provider preset** (provider set: provider, base URL,
key, default model). The **specific model** and **reasoning level** are
chosen **per conversation**, directly in the chat composer, not in
settings.

- **Composer** (`ChatView` + `ChatModelControl`): a compact control shows
  the current model and reasoning level. The menu reads the **active provider
  set catalogue** (`provider_set.chat.models[]`: labels, context window,
  `reasoningEfforts`). Legacy providers without a catalogue fall back to
  `utils/modelCatalog.ts` and `utils/reasoningSupport.ts`.
- **Per-session persistence**: model and reasoning effort are
  saved **with** the conversation on the Tauri side (`ConversationSession.model` and
  `reasoningEffort`). When loading a session, the saved model is
  restored if still applicable to the active provider set; otherwise it falls back to the set
  default model (`isModelApplicableForSet` + watch on active provider).
  On session switch, overrides are cleared immediately before async load.
- **Turn transit**: `buildActiveProviderSet` → `applySessionOverridesToSet`
  (reconciles reasoning after model change) → `providerSetToSidecar` in
  `/agent/turn`. The sidecar reclamps via `build_model_settings(config,
  provider_set)`. See [provider-sets-reasoning.md](./provider-sets-reasoning.md).
- **Mistral**: small/medium models expose **None** and **High** only in the UI;
  large has no adjustable reasoning. Legacy values (`medium`, `low`) are
  clamped to `high` before API call.
- **UI labels**: `None` · `Low` · `Medium` · `High` (subset shown per model).

## Chat UX (composer & reasoning)

- **Pill composer**: when empty, the field and actions (model/reasoning,
  send) fit on one line. As soon as you type, the field expands to multiple lines
  and actions move to a bar below, with the field taking full width.
- **Send**: the field clears, the user message appears immediately
  (pushed synchronously in `useChatStream.send`) and the view scrolls to the bottom.
  `MessageList.getScrollTarget` detects the actually scrollable container
  (double `q-scroll-area` + `DynamicScroller` container) to target the right one.
- **Reasoning in progress**: a **spinner** plus label "Reasoning in
  progress…" appears in the reasoning zone (`ThinkingCard`) during
  streaming. A "The model is thinking…" placeholder covers the startup delay
  between send and the first event (`thinking_start` or token).

### Message list and streaming performance

- **Virtualized list** (`MessageList.vue` + `vue-virtual-scroller`): long
  conversations stay responsive. During streaming, `_contentRev` on
  `ChatMessage` throttles re-measurement (~50 ms token flush in
  `useChatStream`, ~80 ms markdown throttle in `MessageTextPart`).
- **Scroll pinning** (`ChatView.vue`): auto-scroll to bottom while the user
  stays at the bottom; wheel/touch-up detaches until they return or tap the
  scroll-down FAB. `scrollToBottomStable()` retries until `scrollHeight`
  stabilizes (virtual scroller layout).
- **Expansion state** (`useToolCallExpansion.ts`): tool-call and reasoning
  card expand/collapse survives `DynamicScroller` item recycling via module-level
  maps + `expansionEpoch` in scroller `size-dependencies`.

### Markdown rendering

Assistant text is rendered by `MessageTextPart.vue` with shared utilities:

| Module | Role |
|---|---|
| `utils/markdownRender.ts` | markdown-it, DOMPurify, KaTeX (final only), Shiki highlighting, copy buttons |
| `utils/markdownStreaming.ts` | Splits content into **complete blocks** (paragraph/fence boundaries) + **tail** during SSE |

During streaming, complete blocks are parsed once and cached; only the tail
is re-rendered on each throttle tick. KaTeX and Shiki run once the message
finishes (`streaming: false`). Code-block copy labels are i18n (`chat.codeCopy`,
etc.).

### Edit and regenerate

Per-message actions in `Message.vue`, wired through `ChatPage` →
`useChatStream`:

| Action | Composable | Behaviour |
|---|---|---|
| **Edit** (user messages) | `editAndResend(id, text)` | Truncates from the edited user message onward, sends the new text |
| **Regenerate** (assistant messages) | `regenerateFrom(assistantId)` | Removes the assistant and everything after, re-runs the turn reusing the existing user message (`regenerateFromUserId` in turn payload) |

Guards: blocked while `streaming`, while a confirmation or plan is pending
(`hasActiveHumanGate()`), or while the global composer stream is active
(`interactionLocked` prop from `MessageList`). Header **Retry** after a failed
turn uses `lastUserText` / `lastRegenerateUserId`; these are reset on
`loadMessages()` (session switch).

**Known limitation:** edit/regenerate resend text only; original attachment
bytes are not re-injected (attachment snapshots remain in persisted history but
are not replayed on resend).

### Accessibility (chat)

- Message log: `role="log"`, `aria-live="off"` during streaming,
  `"polite"` otherwise (avoids screen-reader spam on every token).
- Stream completion: sr-only status region announces when generation ends
  (`chat.streamCompleteAria`).
- Message actions, reasoning cards, and confirmation regions use
  `aria-expanded`, `aria-label`, and `role="alert"` where appropriate.
- Streaming cursor respects `prefers-reduced-motion`.

### Key front files (chat)

```
front/src/
├── components/chat/
│   ├── ChatView.vue          # composer, scroll pinning, drag-drop
│   ├── MessageList.vue       # virtual scroller, a11y live region
│   ├── Message.vue           # interleaved parts, edit/regenerate actions
│   ├── MessageTextPart.vue   # markdown (incremental + final)
│   ├── ThinkingCard.vue      # reasoning block
│   ├── ToolCallCard.vue      # tool call human/tech views
│   ├── ConfirmationCard.vue  # human approval gate UI
│   └── PlanCard.vue          # multi-step plan approval
├── composables/useChatStream.ts   # SSE, send, edit, regenerate, retry
└── utils/markdownRender.ts        # shared markdown pipeline
    markdownStreaming.ts           # block split for streaming
```
