# Documentation Workproba

Index de la documentation du projet **Workproba** — assistant de travail sur dossier local (type Claude Cowork), application bureau Tauri 2 + sidecar Python.

## Cadrage produit

- **[intention.md](./intention.md)** — Intention produit, décision pivot bureau local-first, objectifs
- **[desktop.md](./desktop.md)** — Architecture bureau, phasage, flux d'un message, validation par phase

## Architecture technique

- **[architecture.md](./architecture.md)** — Vue d'ensemble, stack, diagramme, modules actifs
- **[stack.md](./stack.md)** — Versions des composants, ports, variables d'environnement front & sidecar
- **[workspace-storage.md](./workspace-storage.md)** — Stockage par workspace (`{app_data}/workspaces/{id}/.workproba/`)

## Design & UI

- **[design.md](./design.md)** — Système de design Workproba
- **[anubis-ui.md](./anubis-ui.md)** — Framework CSS Anubis UI, couleurs, utilitaires

## Tests

- **[testing.md](./testing.md)** — Tests front (Vitest) et sidecar Python (pytest, live Mistral)

## Navigation rapide

- **Démarrer en dev** : `make dev-ai` puis `make dev-desktop` (voir [README racine](../README.md))
- **Comprendre le produit** : [intention.md](./intention.md)
- **Architecture** : [architecture.md](./architecture.md) · [desktop.md](./desktop.md)
- **Stack & variables** : [stack.md](./stack.md)
- **Sidecar IA** : [services/ai/README.md](../services/ai/README.md)
- **Coque Tauri** : [desktop/README.md](../desktop/README.md)

## Legacy

L'ancien stack web NestJS + Docker est archivé dans `../legacy/` (non utilisé par le produit bureau).
