# Workproba tests

Workproba is a desktop application (Tauri + Quasar) with a Python sidecar. Tests are split across three layers.

> **Node required:** ≥ 22.22 (Node 24 recommended). vitest 4 and the Quasar build fail on Node 20.

## Python sidecar (`services/ai/`)

Framework: **pytest** + `pytest-asyncio`. Offline tests are deterministic (no LLM, Pydantic AI `TestModel` replaces the real model).

### Organization

- `tests/conftest.py`: shared fixtures
- `tests/test_llm_config.py`: `build_model`, settings, helpers
- `tests/test_agent_loop.py`: message conversion, SSE events, tool robustness
- `tests/test_agent_remember.py`: `remember` tool, memory injection
- `tests/test_memory_scope.py`, `test_memory_extended.py`: user/project scopes, CRUD
- `tests/test_memory_prompt.py`: `memory_prompt` injection and guardrails
- `tests/test_memory_consolidation.py`, `test_memory_promotion.py`: session promotion pipeline
- `tests/test_memory_ranking.py`, `test_memory_ranking_semantic.py`, `test_memory_embeddings.py`, `test_embedding_cache.py`, `test_memory_mechanics.py`: hybrid ranking, embedding cache, cross-hook behavior
- `tests/test_audit_correlation.py`: audit payload correlation (`turn_id`, `session_id`, `work_id`)
- `tests/test_web_search_backends.py`: pluggable web search backend registry
- `tests/test_recall_project_sessions.py`: cross-session digest builder
- `tests/test_main_http.py`: `/agent/turn`, CORS preflight, HTTP errors
- `tests/test_rag_store.py`: chunking, `RagStore` without network
- `tests/test_compaction.py`: in-conversation history compaction
- `tests/test_plugin_personas.py`, `test_personas_estimate_cost.py`: personas plugin
- `tests/test_plugin_projet.py`, `test_plugin_projet_http.py`: project plugin
- `tests/test_plugin_browser.py`, `test_plugin_cloud.py`: experimental plugins (browser: 38 tests — tools, HTTP, audit, bbox, piloting pause, screenshot limits, history sanitization)
- `tests/test_documents_preview.py`, `test_preview_change.py`: document preview
- `tests/test_attachments.py`, `test_reprocess_attachment.py`: attachments
- `tests/test_audit.py`, `test_audit_export.py`: audit log
- `tests/test_versions.py`: file versions
- `tests/test_extractor.py`: `.docx` extraction, binary
- `tests/test_confirmation_sandbox.py`: write confirmation and sandbox gating
- `tests/test_effect_gate.py`: Human Approval Gate (effect classification, `request_effect`, audit, deny/timeout)
- `tests/test_work_events.py`: Work Event Bus (`work_started`, `work_contribution`, `work_completed`, `work_failed`)
- `tests/test_memory_flow.py`: cross-session memory promotion and recall flows
- `tests/test_live_mistral.py`: **live** (network + Mistral key), skipped by default

### Commands

```bash
cd services/ai

# Offline suite (deterministic)
.venv/bin/pytest -q

# Live tests against Mistral (network + key required)
WP_LIVE_LLM=1 .venv/bin/pytest tests/test_live_mistral.py -q
```

### Current coverage

Run `pytest -q` for the up-to-date count (**634 offline tests** + a few skips, plus 2 live). Covers: agent, approval gate, work events, scoped memory (hybrid ranking + embedding cache), plugins, documents, audit, attachments, RAG, HTTP SSE, web search.

## Frontend (`front/`)

Framework: **Vitest 4** + `@vue/test-utils`, `happy-dom` environment.

### Organization

- Unit: `front/test/unit/**/*.spec.ts`
- Global setup: `front/test/setup.ts` (i18n + Quasar mocks/stubs)
- Config: `front/vitest.config.ts`
- Workproba composables: `useSidecarHealth.spec.ts`, etc.

### Commands

```bash
cd front

yarn test:unit                 # vitest run + coverage (~387 tests)
npx vitest run test/unit --no-coverage   # quick without coverage
yarn test:e2e                  # Playwright (smoke)
```

### Notable unit specs

- `ConfirmationCard.spec.ts`: effect-oriented headline, protection labels, approve/deny.
- `useChatStream.spec.ts`: SSE handling, confirmation flow, approval gate retry detection, `work_*` correlation (`streamCorrelation`), edit/regenerate, retry after failed regenerate, `loadMessages` retry reset.
- `MessageList.spec.ts`: `aria-live` during streaming, sr-only completion announcement, scroll API.
- `Message.spec.ts`: role labels, edit/regenerate actions, copy.
- `MessageTextPart.spec.ts`: markdown sanitization, incremental streaming blocks.
- `markdownStreaming.spec.ts`: block/tail split (fences, paragraphs).
- `spaceTerminology.spec.ts`: Space UX i18n (FR/EN).
- `useUiTheme.spec.ts`, `uiTheme.spec.ts`: theme persistence (Tauri + localStorage boot).
- `useSidecarHealth.spec.ts`: sidecar health polling (connected / error / streaming).
- `providerSetModels.spec.ts`, `providerSetsEnrich.spec.ts`, `llmRouting.spec.ts`: provider set catalogue, reasoning clamp, session overrides (see [provider-sets-reasoning.md](./provider-sets-reasoning.md)).

### Test selection by risk

- **Composables / utils**: Vitest unit with mocks (`vi.fn`, service mocks).
- **Components**: Vitest + Vue Test Utils (props, emits, slots, observable states).
- **Pages**: targeted Vitest render + interactions; Playwright e2e for critical flows.
- Prefer fast deterministic tests; limit e2e to critical business paths.

## Tauri shell (`desktop/`)

Rust unit tests (`cargo test --lib`, 32 tests): workspace migration `workspaces/` → `spaces/`, provider set migration, sidecar status helpers, plugin registry.

```bash
cd desktop/src-tauri && cargo test --lib
cd desktop/src-tauri && cargo check   # compile only
```

## CI

GitHub Actions (since 14/07/2026):

| Workflow | Trigger | Targets |
|---|---|---|
| `desktop-ci.yml` | push/PR `main`, `develop` | `pytest -q`, `cargo fmt --check`, `cargo check`, `cargo test --lib`, `yarn test:unit`, front lint, lint-i18n, sidecar PyInstaller smoke (push only) |
| `desktop-release.yml` | tag `v*.*.*` | Tauri installers (macOS arm64/x64, Linux, Windows) + `SHA256SUMS.txt` |

Local parity: `make build-sidecar`, `bash scripts/smoke-test-sidecar.sh`, `make build-desktop`. Release: `./scripts/create-tag.sh`.

## Reference

- [Vue.js Testing Guide](https://vuejs.org/guide/scaling-up/testing)
- [Pydantic AI testing](https://ai.pydantic.dev/testing/)
