# Documentation Workproba

Index de la documentation du projet **Workproba** — assistant de travail sur dossier local (type Claude Cowork), application bureau Tauri 2 + sidecar Python.

## Installation (grand public)

- **[installateurs.md](./installateurs.md)** : télécharger et installer Workproba (Windows, macOS, Linux), avertissements SmartScreen/Gatekeeper, désinstallation

## Cadrage produit

- **[intention.md](./intention.md)** — Intention produit, décision pivot bureau local-first, objectifs
- **[desktop.md](./desktop.md)** — Architecture bureau, phasage, flux d'un message, validation par phase

## Architecture technique

- **[architecture.md](./architecture.md)** — Vue d'ensemble, stack, shell UI, chat, modèles LLM
- **[stack.md](./stack.md)** — Versions des composants, ports, variables d'environnement, commandes dev
- **[workspace-storage.md](./workspace-storage.md)** — Stockage par workspace et données globales utilisateur
- **[memory.md](./memory.md)** — Mémoire scopée (user / projet), RAG, outil `remember`
- **[plugins.md](./plugins.md)** — Système de plugins V2, personas, intégration UI

## Design & UI

- **[design.md](./design.md)** — Système de design Workproba (tokens `--wp-*`, typo, densité)
- **[anubis-ui.md](./anubis-ui.md)** — Palette Anubis, thèmes clair / Charbon chaud, `anubis.config.json`

## Tests

- **[testing.md](./testing.md)** — Tests front (Vitest) et sidecar Python (pytest, live Mistral)

## Navigation rapide

- **Installer Workproba** : [installateurs.md](./installateurs.md)
- **Démarrer en dev** : `make dev` ou `yarn dev` (voir [README racine](../README.md))
- **Comprendre le produit** : [intention.md](./intention.md)
- **Architecture** : [architecture.md](./architecture.md) · [desktop.md](./desktop.md)
- **Mémoire & plugins** : [memory.md](./memory.md) · [plugins.md](./plugins.md)
- **Stack & variables** : [stack.md](./stack.md)
- **Sidecar IA** : [services/ai/README.md](../services/ai/README.md)
- **Coque Tauri** : [desktop/README.md](../desktop/README.md)

## Legacy

L'ancien stack web NestJS + Docker est archivé dans `../legacy/` (non utilisé par le produit bureau).
