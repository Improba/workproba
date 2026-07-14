# Workproba documentation

Index of **Workproba** project documentation: local-folder work assistant (Claude Cowork style), Tauri 2 desktop app + Python sidecar.

## Installation (end users)

- **[installateurs.md](./installateurs.md)**: download and install Workproba (Windows, macOS, Linux), SmartScreen/Gatekeeper warnings, uninstall

## Product framing

- **[intention.md](./intention.md)**: Product intent, local-first desktop pivot decision, goals
- **[desktop.md](./desktop.md)**: Desktop architecture, phasing, message flow, phase validation

## Technical architecture

- **[architecture.md](./architecture.md)**: Overview, stack, UI shell, chat, LLM models
- **[stack.md](./stack.md)**: Component versions, ports, environment variables, dev commands
- **[workspace-storage.md](./workspace-storage.md)**: Per-workspace storage and global user data
- **[memory.md](./memory.md)**: Scoped memory (user / project), RAG, promotion, cross-session recall
- **[plugins.md](./plugins.md)**: Plugin system, personas, UI integration
- **[browser.md](./browser.md)**: Browser plugin (Playwright, agent tools, live view, security)
- **[web-search.md](./web-search.md)**: Core `web_search` tool (Mistral Conversations API, citations, network guard)

## Design & UI

- **[design.md](./design.md)**: Workproba design system (`--wp-*` tokens, typography, density)
- **[anubis-ui.md](./anubis-ui.md)**: Anubis palette, light / warm charcoal themes, `anubis.config.json`

## Tests

- **[testing.md](./testing.md)**: Front tests (Vitest) and Python sidecar (pytest, live Mistral)

## Quick navigation

- **Install Workproba**: [installateurs.md](./installateurs.md)
- **Start dev**: `make dev` or `yarn dev` (see [root README](../README.md))
- **Understand the product**: [intention.md](./intention.md)
- **Architecture**: [architecture.md](./architecture.md) · [desktop.md](./desktop.md)
- **Memory & plugins**: [memory.md](./memory.md) (scoped memory, RAG, promotion, cross-session recall) · [plugins.md](./plugins.md) · [browser.md](./browser.md) · [web-search.md](./web-search.md)
- **Stack & variables**: [stack.md](./stack.md)
- **AI sidecar**: [services/ai/README.md](../services/ai/README.md)
- **Tauri shell**: [desktop/README.md](../desktop/README.md)

## Legacy

The former NestJS + Docker web stack is archived in `../legacy/` (not used by the desktop product).
