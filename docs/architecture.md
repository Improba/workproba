# Workproba architecture

> **Last updated:** 14/07/2026

## Overview

**Workproba** is a desktop application (macOS, Linux, Windows): the user **opens a space** (a local folder on disk); the agent manipulates files in place, relies on locally indexed memory, and runs code under the hood in an isolated sandbox.

> **Terminology:** The user-facing concept is **Space**. Internal code and `registry.json` still use `workspace_id` / `ws_…` and a `workspaces` array. Metadata paths use `{app_data}/spaces/`.

Detailed documentation: [desktop.md](./desktop.md), [workspace-storage.md](./workspace-storage.md).

## Stack

| Layer | Technology | Role |
|---|---|---|
| Desktop shell | Tauri 2 (Rust) | Window, native filesystem, per-space storage, packaging |
| Frontend | Quasar 2 + Vue 3 | Webview UI (chat, files) |
| AI core | Python 3.12 + FastAPI (sidecar) | Agent loop, extraction, RAG, sandbox |
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
3. Python runs the agent loop (LLM, file tools, subprocess sandbox).
4. Sessions are persisted in `{app_data}/spaces/{id}/.workproba/`.
5. Each turn: explicit memories and relevant prior session summaries are injected; project RAG is available via `search_kb`. Session summaries are promoted to shared project memory in the background (see [memory.md](./memory.md)).

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

Implementation: `app/agent/work_events.py`. Labels are localized (`work.capability.*`, `work.perspective.*`).

## UI shell (desktop layout)

The main layout (`WorkprobaLayout.vue`) organizes the screen:

```
WorkprobaTitleBar
├── WorkspaceSidebar (left, responsive rail mode)
├── central zone (router-view: chat, settings, onboarding)
├── RightPanel (right, Ctrl+B): files · preview · personas · plugins
└── SideChatPanel (Ctrl+Shift+L): lateral personas discussion
```

**Sidebar** (`WorkspaceSidebar.vue`): spaces → conversations tree, renameable display titles, streaming indicator, user profile, memory and model settings access.

**Right panel** (`RightPanel.vue`): file explorer, document preview (`DocumentPreview` + `VersionsPanel`), Personas tab if plugin active, dynamic plugin tabs.

**Chat** (`ChatView.vue`): pill composer, "+" menu (attachments + personas actions), model/reasoning control, file drag-and-drop.

## Attachments and document preview

- **Attachments**: stored in `{workspace_data_dir}/attachments/{session_id}/{attachment_id}/`. Reprocess OCR/vision via `POST /agent/reprocess-attachment`.
- **HTML/text preview**: sidecar `GET /documents/preview` (content rendered in the webview).
- **Image preview**: Tauri `convertFileSrc` with `protocol-asset` feature (`tauri.conf.json` → `assetProtocol`).
- **Diff before write**: `POST /documents/preview-change`.

## Plugins

Four builtin plugins (personas enabled by default). See [plugins.md](./plugins.md).

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

The "AI Models" screen chooses a **provider/preset** (provider, base URL,
key, default model). The **specific model** and **reasoning level** are
chosen **per conversation**, directly in the chat composer, not in
settings.

- **Composer** (`ChatView` + `ChatModelControl`): a compact control shows
  the current model and reasoning level. The menu offers the provider's
  suggested models (`utils/modelCatalog.ts`) and reasoning levels
  supported by the model (`utils/reasoningSupport.ts`), with verbose help per
  option for non-technical users.
- **Per-session persistence**: model and reasoning effort are
  saved **with** the conversation on the Tauri side (`ConversationSession.model` and
  `reasoningEffort`). When loading a session, the saved model is
  restored if still applicable to the active provider; otherwise it falls back to the provider
  default model (`isModelApplicable` logic + watch on active provider).
- **Turn transit**: `buildActiveProviderSet` applies session
  overrides to the active set; `useLlmSessionContext` propagates these overrides to
  personas and attachments while the conversation is active.
  `mergeLlmConfigsWithSessionReasoning` (`utils/llmRouting.ts`) is only used for
  legacy fallback without a set.
- **UI labels**: `None` · `Low` · `Medium` · `High`.

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
