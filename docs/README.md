# Workproba documentation

Index of **Workproba** project documentation: local-folder work assistant (Claude Cowork style), Tauri 2 desktop app + Python sidecar.

## CI / CD

Operational since **14/07/2026** (commit `1155d2d`). **Voie B** (Work Event Bus + Human Approval Gate) shipped **15/07/2026**.

| Workflow | Trigger | Role |
|---|---|---|
| [`.github/workflows/desktop-ci.yml`](../.github/workflows/desktop-ci.yml) | push/PR `main`, `develop` | pytest, Rust, front lint/tests, lint-i18n, sidecar packaging |
| [`.github/workflows/desktop-release.yml`](../.github/workflows/desktop-release.yml) | tag `v*.*.*` | multi-OS installers + `SHA256SUMS.txt`, draft release |

Publish: `./scripts/create-tag.sh`. Installers are **unsigned**; see [signing.md](./signing.md). Next ops step: validate first tagged release on all 4 platforms.

## Installation (end users)

- **[installateurs.md](./installateurs.md)**: download and install Workproba (Windows, macOS, Linux), SmartScreen/Gatekeeper warnings, uninstall
- **[signing.md](./signing.md)**: future code signing procedure (Windows Authenticode, macOS notarization)

## Product framing

- **[intention.md](./intention.md)**: Product intent, desktop pivot, Improba Cloud scope (see roadmaps)
- **[desktop.md](./desktop.md)**: Desktop architecture, phasing, message flow, phase validation

## Technical architecture

- **[architecture.md](./architecture.md)**: Overview, stack, UI shell, Office writers (PPTX + HTML/Chromium visual path), **per-space capabilities**, managed tools, chat, LLM models, human approval gate, work events, Improba Cloud desktop auth UX
- **[provider-sets-reasoning.md](./provider-sets-reasoning.md)**: Provider set catalog, reasoning effort clamping (Mistral none/high), front/back alignment, cloud login vs device enroll
- **[stack.md](./stack.md)**: Component versions, ports, environment variables, dev commands
- **[workspace-storage.md](./workspace-storage.md)**: Per-space storage and global user data (Space UX, `{app_data}/spaces/`, `capabilities.json`, migration from legacy `workspaces/`)
- **[capacites.md](./capacites.md)**: Activatable capabilities hub + **per-space profile** (guided mode, FR/EN UI)
- **[memory.md](./memory.md)**: Scoped memory (user / project), RAG, hybrid ranking, embedding cache, promotion, cross-session recall
- **[plugins.md](./plugins.md)**: Plugin system, capabilities, Regards métier — honest implementation status
- **[browser.md](./browser.md)**: Browser plugin (Playwright, agent tools, live view, security)
- **[web-search.md](./web-search.md)**: Core `web_search` tool (Mistral Conversations API, citations, network guard)

## Product specs (roadmaps)

- **[capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md)**: Capabilities hub (**PR 1–3 delivered**), product catalog, V2.2 spec + PR 4 backlog
- **[contrat-plugin.md](../../workproba-improba/roadmaps/contrat-plugin.md)**: Plugin contract + implementation matrix

## Design & UI

- **[design.md](./design.md)**: Workproba design system (`--wp-*` tokens, typography, density, `WorkprobaBrand` assets)
- **[anubis-ui.md](./anubis-ui.md)**: Anubis palette, light / warm charcoal themes, `anubis.config.json`

## Desktop onboarding & cloud auth

- **[architecture.md § Improba Cloud desktop auth UX](./architecture.md#improba-cloud-desktop-auth-ux)**: `EngineOnboardingWizard`, `CloudLoginModal`, `EnrollCloudModal`, `cloudWebUrls`
- **[architecture.md § Office writers](./architecture.md#office-writers)**: `write_pptx`, layouts, themes, `MAX_PPTX_SLIDES`, HTML/Chromium visual path
- **[architecture.md § Per-space capabilities](./architecture.md#per-space-capabilities-profile)**: `capabilities.json`, turn freeze, managed tools
- **[capacites.md](./capacites.md)**: hub + space profile (product view)

## Tests

- **[testing.md](./testing.md)**: Front tests (Vitest) and Python sidecar (pytest, live Mistral)

## Quick navigation

- **Install Workproba**: [installateurs.md](./installateurs.md)
- **Start dev**: `make dev` or `yarn dev` (see [root README](../README.md))
- **Understand the product**: [intention.md](./intention.md)
- **Architecture**: [architecture.md](./architecture.md) · [desktop.md](./desktop.md) · [provider-sets-reasoning.md](./provider-sets-reasoning.md)
- **Memory & plugins**: [memory.md](./memory.md) (scoped memory, RAG, promotion, cross-session recall) · [plugins.md](./plugins.md) · [browser.md](./browser.md) · [web-search.md](./web-search.md)
- **Stack & variables**: [stack.md](./stack.md)
- **AI sidecar**: [services/ai/README.md](../services/ai/README.md)
- **Tauri shell**: [desktop/README.md](../desktop/README.md)

## Legacy

The former NestJS + Docker web stack is archived in `../legacy/` (not used by the desktop product).
